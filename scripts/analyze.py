# -*- coding: utf-8 -*-
"""拆片：逐字稿（每句幾秒開始、幾秒結束）、每一次換畫面、每顆鏡頭一張縮圖、縮圖總表，
再整理成 拆片.md：每一句講什麼、這句裡原片換了幾次畫面、換在這句的哪個位置。
用法：python3 analyze.py <影片> [--out 資料夾] [--threshold 11] [--no-transcript] [--language zh] [--model 模型]

換畫面的算法：影片縮成 270 寬的灰階，算前後兩格平均差多少，取超過門檻的高峰，0.1 秒內只留一個。
畫面裡換圖、卡片跳出來也抓得到（只抓大剪接的話會漏一半）。門檻 11 是在 9:16 Reels 上試出來的：
抓太多就調高，漏掉就調低。"""
import argparse, json, os, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def frame_diffs(path, fps, w=270):
    info = common.video_info(path); h = max(2, round(w * info["height"] / info["width"] / 2) * 2)
    p = subprocess.Popen([common.need("ffmpeg"), "-v", "error", "-i", path, "-vf", f"fps={fps},scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    prev, d, n = None, [], w * h
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n: break
        f = np.frombuffer(buf, np.uint8).astype(np.int16)
        if prev is not None: d.append(float(np.abs(f - prev).mean()))
        prev = f
    p.wait()
    return np.array(d)


def peaks(d, thr, min_gap):
    cuts = []
    for i in range(1, len(d) - 1):
        if d[i] > thr and d[i] >= d[i - 1] and d[i] >= d[i + 1]:
            if cuts and i - cuts[-1] < min_gap:
                if d[i] > d[cuts[-1]]: cuts[-1] = i
                continue
            cuts.append(i)
    return cuts


def to_traditional(segs):
    try:
        import opencc
        try: cc = opencc.OpenCC("s2twp")
        except Exception: cc = opencc.OpenCC("s2twp.json")
        for s in segs: s["text"] = cc.convert(s["text"])
        return True
    except Exception:
        return False


def transcribe(path, language, model):
    lang = language or None          # 不要給 initial_prompt：給了中文提示句，Whisper 會把整支片吐成一整段，切不出句子
    try:
        import mlx_whisper
        r = mlx_whisper.transcribe(path, path_or_hf_repo=model or "mlx-community/whisper-large-v3-turbo", language=lang)
        segs, name = r["segments"], "mlx-whisper"
    except ImportError:
        try:
            from faster_whisper import WhisperModel
            m = WhisperModel(model or "large-v3-turbo", device="auto", compute_type="int8")
            it, _ = m.transcribe(path, language=lang)
            segs, name = [{"start": s.start, "end": s.end, "text": s.text} for s in it], "faster-whisper"
        except ImportError:
            try:
                import whisper
                m = whisper.load_model(model or "turbo")
                segs, name = m.transcribe(path, language=lang, fp16=False)["segments"], "openai-whisper"
            except ImportError:
                return None, None
    out = [{"start": round(float(s["start"]), 2), "end": round(float(s["end"]), 2), "text": s["text"].strip()} for s in segs if s["text"].strip()]
    cjk = any("一" <= c <= "鿿" for s in out for c in s["text"])
    if cjk and not to_traditional(out): name += "（沒裝 opencc，如果出來是簡體：python3 -m pip install opencc-python-reimplemented）"
    return out, name


def label_font(size=16):
    try: return common.load_font(common.find_font(""), size)
    except SystemExit: return ImageFont.load_default()


def contact_sheet(paths, labels, out, cols=7, cw=135, ch=240):
    rows = (len(paths) + cols - 1) // cols; pad, lab = 4, 22
    im = Image.new("RGB", (cols * (cw + pad) + pad, rows * (ch + lab + pad) + pad), (14, 14, 16)); d = ImageDraw.Draw(im); f = label_font()
    for k, (p, t) in enumerate(zip(paths, labels)):
        x = pad + (k % cols) * (cw + pad); y = pad + (k // cols) * (ch + lab + pad)
        try: a = Image.open(p).convert("RGB")
        except Exception: continue
        s = max(cw / a.width, ch / a.height); a = a.resize((max(1, round(a.width * s)), max(1, round(a.height * s))))
        a = a.crop(((a.width - cw) // 2, (a.height - ch) // 2, (a.width - cw) // 2 + cw, (a.height - ch) // 2 + ch))
        im.paste(a, (x, y)); d.text((x + 2, y + ch + 2), t, font=f, fill=(210, 210, 215))
    im.save(out, quality=86)


def main():
    ap = argparse.ArgumentParser(description="拆片")
    ap.add_argument("video"); ap.add_argument("--out"); ap.add_argument("--threshold", type=float, default=11.0)
    ap.add_argument("--no-transcript", action="store_true"); ap.add_argument("--language", default=None); ap.add_argument("--model", default=None)
    a = ap.parse_args()
    if not os.path.exists(a.video): sys.exit(f"找不到影片：{a.video}")
    out = os.path.abspath(a.out or os.path.join(os.path.dirname(os.path.abspath(a.video)), "analysis"))
    os.makedirs(os.path.join(out, "shots"), exist_ok=True)
    proj = os.path.dirname(out); cfg = common.load_config(proj) if os.path.exists(os.path.join(proj, "reels-config.json")) else common.DEFAULTS
    language = a.language if a.language is not None else (cfg["transcribe"].get("language") or "")
    model = a.model or cfg["transcribe"].get("model") or None

    info = common.video_info(a.video); fps = round(info["fps"]) if 20 <= info["fps"] <= 61 else 30
    print(f"影片 {info['width']}×{info['height']}，{info['duration']:.2f} 秒，{fps} fps。抓剪點中…")
    d = frame_diffs(a.video, fps); idx = peaks(d, a.threshold, max(1, round(0.1 * fps)))
    cuts = [round((i + 1) / fps, 3) for i in idx]; dur = round(info["duration"], 3)
    bounds = [0.0] + cuts + [dur]; shots = []
    for k in range(len(bounds) - 1):
        s, e = bounds[k], bounds[k + 1]; p = os.path.join(out, "shots", f"{k:02d}.jpg")
        subprocess.run([common.need("ffmpeg"), "-v", "error", "-y", "-ss", f"{(s + e) / 2:.3f}", "-i", a.video, "-frames:v", "1", "-vf", "scale=270:-2", p])
        shots.append({"k": k, "start": round(s, 3), "end": round(e, 3), "thumb": f"shots/{k:02d}.jpg"})
    contact_sheet([os.path.join(out, s["thumb"]) for s in shots], [f"{s['k']:02d} · {s['start']:.2f}s" for s in shots], os.path.join(out, "縮圖總表.jpg"))
    np.save(os.path.join(out, "diff.npy"), d)

    segs, backend = (None, None)
    if not a.no_transcript:
        print("出逐字稿中（第一次會下載模型，要等一下）…")
        segs, backend = transcribe(a.video, language, model)
        if segs is None: print("沒有裝 Whisper，跳過逐字稿（跑 doctor.py 看怎麼裝）。")
    lines = []
    for i, s in enumerate(segs or []):
        inside = [c for c in cuts if s["start"] <= c < s["end"]]; L = max(s["end"] - s["start"], 1e-6)
        lines.append({"n": i + 1, "start": s["start"], "end": s["end"], "text": s["text"], "cuts_inside": inside,
                      "cut_positions": [round((c - s["start"]) / L, 2) for c in inside]})
    common.save_json({"video": os.path.abspath(a.video), "duration": dur, "fps": fps, "size": [info["width"], info["height"]],
                      "threshold": a.threshold, "cuts": cuts, "shots": shots, "transcript_backend": backend, "lines": lines},
                     os.path.join(out, "analysis.json"))
    if segs is not None: common.save_json(segs, os.path.join(out, "transcript.json"))

    md = [f"# 拆片：{os.path.basename(a.video)}", "",
          f"- 片長 {dur:.2f} 秒，{fps} fps，{info['width']}×{info['height']}",
          f"- 換畫面 {len(cuts)} 次，{len(shots)} 顆鏡頭，平均一顆 {dur / max(1, len(shots)):.2f} 秒（門檻 {a.threshold:g}）",
          f"- 逐字稿：{len(segs)} 句（{backend}）" if segs is not None else "- 逐字稿：沒有", "",
          "縮圖總表：`縮圖總表.jpg`。每顆鏡頭的縮圖在 `shots/`。", ""]
    if lines:
        md += ["## 每一句", "", "| # | 開始 | 結束 | 長度 | 這句講什麼 | 句中換畫面 | 換在這句的哪裡 |", "|---|---|---|---|---|---|---|"]
        for l in lines:
            pos = "、".join(f"{int(p * 100)}%" for p in l["cut_positions"]) or "—"
            md.append(f"| {l['n']} | {l['start']:.2f} | {l['end']:.2f} | {l['end'] - l['start']:.2f} | {l['text']} | {len(l['cuts_inside'])} | {pos} |")
        md.append("")
    md += ["## 每一顆鏡頭", "", "| # | 開始 | 結束 | 長度 | 縮圖 |", "|---|---|---|---|---|"]
    md += [f"| {s['k']} | {s['start']:.2f} | {s['end']:.2f} | {s['end'] - s['start']:.2f} | `{s['thumb']}` |" for s in shots]
    open(os.path.join(out, "拆片.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"換畫面 {len(cuts)} 次、{len(shots)} 顆鏡頭" + (f"、{len(segs)} 句" if segs else "") + f" → {out}")


if __name__ == "__main__":
    main()
