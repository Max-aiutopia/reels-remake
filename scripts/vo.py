# -*- coding: utf-8 -*-
"""配音接緊：每句切掉頭尾空白、句中停頓壓短（氣口切掉），再一句接一句排成一條，句子之間不留空白。
用法：python3 vo.py [專案資料夾]
讀：script.json（台詞）、voice/01.mp3、02.mp3…（每句一個音檔，wav／m4a 也可以）、reels-config.json 的 pacing。
寫：build/vo.wav、build/timing.json（每句 start＝音檔放在第幾秒，onset／end＝第一個／最後一個聽得到的字）。

句子怎麼接：前一句最後一個聽得到的字，到下一句第一個字，只隔 pacing.gap（預設 0.12 秒）。
只把音檔頭尾接起來不夠：字前的鼻音、句尾的尾音很小聲，會讓實際聽到的空白多出 0.1～0.2 秒。
script.json 裡標 "raw": true 的句子（拿去做對嘴的）不切不壓，原檔照放，對嘴影片才會對得上。"""
import glob, os, subprocess, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
SR = common.SR


def tighten(x, thr_db=-38, keep=0.07, pad=0.02):
    """切頭尾空白，句中超過 keep 秒的停頓壓成 keep 秒。頭尾各淡入淡出 8ms，接起來不會有爆音。"""
    fr = int(SR * 0.01); n = len(x) // fr
    if n < 3: return x
    e = np.sqrt((x[:n * fr].reshape(n, fr) ** 2).mean(axis=1) + 1e-12)
    sp = 20 * np.log10(e / e.max()) > thr_db; idx = np.where(sp)[0]
    if len(idx) == 0: return x
    a, b = max(idx[0] - int(pad * 100), 0), min(idx[-1] + int(pad * 100) + 1, n)
    out, i = [], a
    while i < b:
        if sp[i]: out.append(x[i * fr:(i + 1) * fr]); i += 1; continue
        j = i
        while j < b and not sp[j]: j += 1
        if (j - i) * 0.01 > keep:
            k = int(round(keep * 100)); out.append(x[i * fr:(i + k // 2) * fr]); out.append(x[(j - (k - k // 2)) * fr:j * fr])
        else: out.append(x[i * fr:j * fr])
        i = j
    y = np.concatenate(out).copy(); f = min(int(SR * 0.008), len(y) // 2)
    if f > 0: y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
    return y


def atempo(x, f):
    if abs(f - 1) < 0.005: return x
    chain, r = [], f
    while r > 2.0: chain.append("atempo=2.0"); r /= 2.0
    while r < 0.5: chain.append("atempo=0.5"); r /= 0.5
    chain.append(f"atempo={r:.4f}")
    p = subprocess.run([common.need("ffmpeg"), "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-af", ",".join(chain), "-f", "f32le", "-"],
                       input=x.tobytes(), capture_output=True, check=True).stdout
    return np.frombuffer(p, np.float32).copy()


def edges(y, edge_db):
    """這句第一個、最後一個聽得到的字在第幾秒（從這個音檔開頭算）。"""
    db = common.envelope_db(y); on = np.where(db > edge_db)[0]
    if len(on) == 0: return 0.0, len(y) / SR
    return on[0] * 0.01, (on[-1] + 1) * 0.01


def audible_gaps(mix, plan, thr=-35):
    """實際聽得到的句間空白（整條配音的音量，低於最大聲 35dB 算沒聲音）。"""
    db = common.envelope_db(mix); out = []
    for a, b in zip(plan, plan[1:]):
        i0, i1 = int(a["onset"] * 100), min(int(a["end"] * 100) + 3, len(db))
        j0, j1 = max(int(b["onset"] * 100) - 3, 0), min(int(b["end"] * 100), len(db))
        la = np.where(db[i0:i1] > thr)[0]; fb = np.where(db[j0:j1] > thr)[0]
        if len(la) == 0 or len(fb) == 0: out.append(None); continue
        out.append(round(max(0.0, (j0 + fb[0] - (i0 + la[-1]) - 1) * 0.01), 2))
    return out


def find_voice(project, i):
    hits = [p for p in glob.glob(os.path.join(project, "voice", f"{i:02d}.*")) if p.lower().endswith(common.AUDIO_EXT)]
    return sorted(hits)[0] if hits else None


def main():
    project = common.project_dir(sys.argv[1] if len(sys.argv) > 1 else ".")
    cfg = common.load_config(project); pc = cfg["pacing"]
    lines = common.load_json(os.path.join(project, "script.json"), "台詞")["lines"]
    missing = [i + 1 for i in range(len(lines)) if not find_voice(project, i + 1)]
    if missing: sys.exit("voice/ 少了這幾句的音檔：" + "、".join(f"{i:02d}" for i in missing))

    plan, segs, prev = [], [], None
    for i, ln in enumerate(lines):
        path = find_voice(project, i + 1); x = common.load_audio(path); raw = bool(ln.get("raw"))
        f = float(ln.get("tempo", 1.0))
        if raw and abs(f - 1) > 0.005: sys.exit(f"第 {i + 1} 句標了 raw（對嘴用），不能再加速。")
        y = x if raw else atempo(tighten(x, pc["silence_db"], pc["keep_pause"]), f)
        a, b = edges(y, pc["edge_db"])
        start = 0.0 if prev is None else max(prev + pc["gap"] - a, 0.0)
        plan.append({"line": i + 1, "text": ln.get("sub", ln.get("say", "")), "say": ln.get("say", ""), "start": round(start, 3),
                     "onset": round(start + a, 3), "end": round(start + b, 3), "tempo": f, "raw": raw, "no_sub": bool(ln.get("no_sub")),
                     "sub_y": ln.get("sub_y"), "file": os.path.relpath(path, project)})
        segs.append((start, y)); prev = start + b

    total = plan[-1]["end"] + pc["end_hold"]
    mix = np.zeros(int((max(s + len(y) / SR for s, y in segs) + 1.0) * SR), np.float32)
    for s, y in segs: k = int(round(s * SR)); mix[k:k + len(y)] += y
    peak = float(np.abs(mix).max()) or 1.0; mix = mix / peak * 0.89
    mix = mix[:int(round(total * SR))]
    common.save_wav(mix, os.path.join(project, "build", "vo.wav"))
    common.save_json({"total": round(total, 3), "gap": pc["gap"], "lines": plan}, os.path.join(project, "build", "timing.json"))

    gaps = audible_gaps(mix, plan)
    print(f"{'句':>3} {'開始':>7} {'開口':>7} {'結束':>7}  語速  台詞")
    for p in plan: print(f"{p['line']:>3} {p['start']:7.2f} {p['onset']:7.2f} {p['end']:7.2f}  {p['tempo']:.2f}  {p['text']}")
    real = [g for g in gaps if g is not None]
    print(f"\n總長 {total:.2f} 秒。句間實際聽得到的空白：{min(real):.2f}～{max(real):.2f} 秒" if real else f"\n總長 {total:.2f} 秒。")
    bad = [(i + 2, g) for i, g in enumerate(gaps) if g is not None and g > pc["max_gap"]]
    if bad: print("⚠ 這幾句前面的空白超過", pc["max_gap"], "秒：", "、".join(f"第 {n} 句 {g:.2f}s" for n, g in bad), "（多半是音檔頭尾有雜音或換氣聲，聽一下那幾個音檔）")
    print("→ build/vo.wav、build/timing.json")


if __name__ == "__main__":
    main()
