# -*- coding: utf-8 -*-
"""交片前檢查：句間空白、全片最長的靜音、字幕有沒有重疊或壓到結尾卡、影片和配音長度對不對，
再把每一場的頭尾各抓一格排成 out/檢查_每場頭尾.jpg（換場、字幕位置一眼看完）。
用法：python3 check.py [專案資料夾]　　有 ✗ 就先修再交。"""
import json, os, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from vo import audible_gaps

bad = 0
def report(ok, what, note=""):
    global bad
    print(f"  {'✓' if ok else '✗'} {what}" + (f"　{note}" if note else "")); bad += 0 if ok else 1


def grab(video, t, path, w=216, dur=None):
    if dur: t = min(t, dur - 0.1)                  # 太靠近片尾 ffmpeg 抓不到格
    if os.path.exists(path): os.remove(path)
    subprocess.run([common.need("ffmpeg"), "-v", "error", "-y", "-ss", f"{max(0, t):.3f}", "-i", video, "-frames:v", "1", "-vf", f"scale={w}:-2", path],
                   stderr=subprocess.DEVNULL)
    return os.path.exists(path)


def main():
    project = common.project_dir(sys.argv[1] if len(sys.argv) > 1 else "."); cfg = common.load_config(project); pc = cfg["pacing"]
    timing = common.load_json(os.path.join(project, "build", "timing.json"), "先跑 vo.py"); L = timing["lines"]; total = float(timing["total"])
    out = os.path.join(project, "out"); final = next((os.path.join(out, f) for f in ("有字_含配音.mp4", "無字_含配音.mp4") if os.path.exists(os.path.join(out, f))), None)
    print("reels-remake 交片檢查\n")

    wav = os.path.join(project, "build", "vo.wav"); mix = common.load_audio(wav)      # 量配音本身；成片的聲音就是它
    if final and os.path.getmtime(final) < os.path.getmtime(wav):
        report(False, "成片比配音舊", "改過台詞、配音或節奏之後要重跑 assemble.py、subs.py")
    gaps = [g for g in audible_gaps(mix, L) if g is not None]
    if gaps: report(max(gaps) <= pc["max_gap"], f"句間空白 {min(gaps):.2f}～{max(gaps):.2f} 秒", f"上限 {pc['max_gap']} 秒")
    db = common.envelope_db(mix); sp = db > -40; idx = np.where(sp)[0]; longest, i = 0.0, (idx[0] if len(idx) else 0)
    while len(idx) and i < idx[-1]:
        if sp[i]: i += 1; continue
        j = i
        while j < idx[-1] and not sp[j]: j += 1
        longest = max(longest, (j - i) * 0.01); i = j
    report(longest <= pc["max_gap"] + 0.05, f"全片最長的靜音 {longest:.2f} 秒", "句中的停頓也算")

    if final:
        vd = common.duration(final); report(abs(vd - total) < 0.15, f"成片 {vd:.2f} 秒，配音時間表 {total:.2f} 秒", os.path.basename(final))
    else: report(False, "還沒有成片", "先跑 assemble.py")

    cp = os.path.join(project, "build", "cues.json")
    if os.path.exists(cp):
        cues = json.load(open(cp, encoding="utf-8"))
        over = [(c[2], d[2]) for c, d in zip(cues, cues[1:]) if c[1] > d[0] + 1e-3]
        report(not over, f"字幕 {len(cues)} 條沒有重疊" if not over else f"字幕重疊 {len(over)} 處", "、".join(f"{a}／{b}" for a, b in over[:3]))
        caps = [l["onset"] for l in L if l.get("no_sub")]
        late = [c[2] for c in cues for o in caps if c[0] < o < c[1]]
        if caps: report(not late, "字幕沒有壓到不上字幕的那句（結尾卡）" if not late else "字幕壓到結尾卡", "、".join(late[:3]))
        long_ = [c[2] for c in cues if len(c[2]) > 16]
        if long_: print(f"  ! 有 {len(long_)} 條字幕超過 16 個字，手機上可能太擠：{long_[0]}")
    else: print("  ! 還沒有字幕（subs.py 還沒跑）")

    sp_path = os.path.join(project, "build", "scenes_timing.json")
    if final and os.path.exists(sp_path):
        scenes = json.load(open(sp_path, encoding="utf-8")); tmp = os.path.join(project, "build", "_check"); os.makedirs(tmp, exist_ok=True)
        cells = []
        for s in scenes:
            for lab, t in (("頭", s["start"] + 0.1), ("尾", min(s["end"] - 0.06, total - 0.12))):
                p = os.path.join(tmp, f"{s['scene']:02d}{lab}.jpg")
                if grab(final, t, p, dur=vd): cells.append((f"場{s['scene']} {lab} {t:.2f}s", p))
        if cells:
            cols = 8; cw, ch, lab = 216, 384, 26; rows = (len(cells) + cols - 1) // cols
            im = Image.new("RGB", (cols * (cw + 4) + 4, rows * (ch + lab + 4) + 4), (255, 255, 255)); d = ImageDraw.Draw(im)
            try: f = common.load_font(common.find_font(cfg["subtitle"].get("font", "")), 18)
            except SystemExit: f = None
            for k, (t, p) in enumerate(cells):
                x, y = 4 + (k % cols) * (cw + 4), 4 + (k // cols) * (ch + lab + 4)
                a = Image.open(p).convert("RGB"); im.paste(a.resize((cw, round(a.height * cw / a.width))), (x, y + lab)); d.text((x + 2, y + 2), t, font=f, fill=(0, 0, 0))
            sheet = os.path.join(out, "檢查_每場頭尾.jpg"); im.save(sheet, quality=86); print(f"\n每場頭尾：{sheet}（看換場有沒有對、字幕有沒有擋到臉或重點）")
    print()
    if bad: print(f"有 {bad} 項沒過，先修再交。"); sys.exit(1)
    print("全部通過。")


if __name__ == "__main__":
    main()
