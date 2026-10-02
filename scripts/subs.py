# -*- coding: utf-8 -*-
"""字幕：照配音把每句切成一行一行（在真的停頓處換行），燒進影片；同時輸出 SRT，CapCut 桌面版可以匯入再自己改。
用法：python3 subs.py [專案資料夾] [--srt-only]
讀：build/timing.json、build/vo.wav、out/無字_無聲.mp4、reels-config.json（subtitle）
寫：build/cues.json、out/字幕.srt、out/有字_含配音.mp4

規則：一次一行、不放標點（逗號、句號拿掉，引號「」留著，網址的英文句點留著）；頓號清單一次只出現一個詞；
一行太長就在中間的空白處切開。script.json 標 "no_sub": true 的句子（例如結尾卡上已經有字）不上字幕，
前一句講完多留的時間也不會蓋到它。"sub_y" 可以改那一句字幕的高度（字的中心在第幾列），字會擋到臉時用。
預設樣式（思源黑體粗 56px、字距 16、金黃 #DFBA21、黑描邊 4px、畫面 70% 高）在 reels-config.json 改。"""
import argparse, os, re, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

STRONG = "，。：；！？…—,!?;"      # 一定換段、字幕上不留（英文句點、冒號不算，網址要完整）
SOFT = "、"                          # 頓號清單：一律拆開，一次一個詞


class Style:
    def __init__(self, sc, W, H):
        k = H / 1920.0; self.W, self.H = W, H
        self.size, self.spacing = round(sc["size"] * k), round(sc["spacing"] * k)
        self.stroke, self.cy, self.maxw = max(1, round(sc["stroke"] * k)), round(sc["center_y"] * k), round(sc["max_width"] * k)
        self.color, self.stroke_color = common.hex_rgb(sc["color"]), common.hex_rgb(sc["stroke_color"])
        self.font = common.load_font(common.find_font(sc.get("font", "")), self.size); self.k = k
        self.band = int(self.size * 3.6)

    def width(self, text):
        return sum(self.font.getlength(c) for c in text) + self.spacing * max(0, len(text) - 1)

    def render(self, text):
        """一條 W×band 的 RGBA，字的中心在正中間那一列。"""
        im = Image.new("RGBA", (self.W, self.band), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x = (self.W - self.width(text)) / 2; top, bot = self.font.getbbox("國")[1], self.font.getbbox("國")[3]
        y = self.band / 2 - (top + bot) / 2
        for c in text:
            d.text((x, y), c, font=self.font, fill=self.color + (255,), stroke_width=self.stroke, stroke_fill=self.stroke_color + (255,))
            x += self.font.getlength(c) + self.spacing
        return np.array(im)


def clean(text):
    t = re.sub(f"[{re.escape(STRONG + SOFT)}]+", " ", text).strip(); return re.sub(r"\s+", " ", t)


def split_long(p, st):
    out = []
    while st.width(p) > st.maxw and " " in p:
        k = len(p) // 2
        for j in range(k, 0, -1):
            if p[j] == " ": k = j; break
        out.append(p[:k].strip()); p = p[k:].strip()
    while st.width(p) > st.maxw and len(p) > 1:                     # 沒有空白可以切（全中文長句）：從中間切
        k = len(p) // 2; out.append(p[:k]); p = p[k:]
    return out + [p]


def chunks(text, st):
    out = []
    for q in [q for q in re.split(f"[{re.escape(STRONG)}]+", text) if q.strip()]:
        for it in [r.strip() for r in q.split(SOFT) if r.strip()]: out += split_long(clean(it), st)
    return [c for c in out if c]


def envelope(wav, a, b):
    raw = subprocess.run([common.need("ffmpeg"), "-v", "error", "-ss", str(max(0, a)), "-t", str(max(0.05, b - a)), "-i", wav,
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.float32)
    if len(x) < 400: return np.array([])
    e = np.array([np.sqrt((x[i:i + 160] ** 2).mean() + 1e-12) for i in range(0, len(x) - 160, 160)])
    e = np.convolve(e, np.ones(5) / 5, mode="same"); return 20 * np.log10(e / max(e.max(), 1e-9) + 1e-9)


def pauses(env):
    """停頓：局部最低點，而且前後 250ms 內都有比它大聲 8dB 以上的字。回傳 [(格, 深度)]，一格 10ms。"""
    out = []
    for i in range(3, len(env) - 3):
        if env[i] <= env[max(0, i - 8):i + 9].min() + 1e-6:
            d = min(env[max(0, i - 25):i].max(), env[i + 1:i + 26].max()) - env[i]
            if d > 8 and (not out or i - out[-1][0] > 8): out.append((i, d))
    return out


def cues_from_lines(lines, wav, st, hold):
    """lines: [(開始, 結束, 字, y)] → [[開始, 結束, 一行字, y]]。一句拆成幾段時，先照字數估換行時間，再對到最近的真停頓。"""
    cues = []
    for a, b, text, y in lines:
        cs = chunks(text, st)
        if not cs: continue
        if len(cs) == 1: cues.append([a, b, cs[0], y]); continue
        w = np.cumsum([len(c) for c in cs])[:-1] / sum(len(c) for c in cs); bounds = [a]
        env = envelope(wav, a, b); cand = [(a + i / 100, d) for i, d in pauses(env)] if len(env) > 20 else []
        for f in w:
            tg = a + (b - a) * f; ok = [(t, d) for t, d in cand if bounds[-1] + 0.2 < t < b - 0.2 and abs(t - tg) < 0.7]
            if ok: tg = min(ok, key=lambda x: abs(x[0] - tg) - 0.01 * x[1])[0]
            bounds.append(max(tg, bounds[-1] + 0.2))
        bounds.append(b)
        for i, c in enumerate(cs): cues.append([bounds[i], bounds[i + 1], c, y])
    cues.sort(key=lambda c: c[0])
    for i in range(len(cues)):
        nxt = cues[i + 1][0] if i + 1 < len(cues) else cues[i][1] + hold
        cues[i][1] = min(cues[i][1] + hold, nxt)
    return cues


def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def burn(src, cues, st, out, audio):
    info = common.video_info(src); W, H = info["width"], info["height"]
    if (W, H) != (st.W, st.H): sys.exit(f"影片是 {W}×{H}，設定檔是 {st.W}×{st.H}，兩邊要一樣。")
    fps = round(info["fps"]); imgs = {c[2]: st.render(c[2]) for c in cues}; half = st.band // 2
    dec = subprocess.Popen([common.need("ffmpeg"), "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    tmp = out + ".v.mp4"
    enc = subprocess.Popen([common.need("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                            *common.encoder_args(18), "-movflags", "+faststart", tmp], stdin=subprocess.PIPE)
    i = 0
    while True:
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: break
        fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy(); t = i / fps
        for a, b, text, y in cues:
            if a <= t < b:
                s = imgs[text]; y0 = int((y if y else st.cy)) - half; y1 = y0 + st.band
                ya, yb = max(0, y0), min(H, y1); sa = s[ya - y0:yb - y0]; al = sa[..., 3:4].astype(np.float32) / 255
                reg = fr[ya:yb].astype(np.float32); fr[ya:yb] = (reg * (1 - al) + sa[..., :3] * al).astype(np.uint8)
        enc.stdin.write(fr.tobytes()); i += 1
    enc.stdin.close(); enc.wait(); dec.wait()
    subprocess.run([common.need("ffmpeg"), "-v", "error", "-y", "-i", tmp, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    os.remove(tmp); return i


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project", nargs="?", default="."); ap.add_argument("--srt-only", action="store_true")
    a = ap.parse_args(); project = common.project_dir(a.project); cfg = common.load_config(project)
    timing = common.load_json(os.path.join(project, "build", "timing.json"), "先跑 vo.py"); L = timing["lines"]
    wav = os.path.join(project, "build", "vo.wav"); V = cfg["video"]; st = Style(cfg["subtitle"], int(V["width"]), int(V["height"]))
    k = st.k; lines = [(l["onset"], l["end"], l["text"], round(l["sub_y"] * k) if l.get("sub_y") else None) for l in L if not l.get("no_sub")]
    cues = cues_from_lines(lines, wav, st, float(cfg["subtitle"]["hold"]))
    for l in L:                                   # 不上字幕的句子（結尾卡）：前面的字幕最晚在它開口時收掉
        if l.get("no_sub"): cues = [[c0, min(c1, l["onset"]) if c0 < l["onset"] else c1, t, y] for c0, c1, t, y in cues]
    cues = [c for c in cues if c[1] - c[0] > 0.05]
    common.save_json([[round(c[0], 3), round(c[1], 3), c[2], c[3]] for c in cues], os.path.join(project, "build", "cues.json"))
    os.makedirs(os.path.join(project, "out"), exist_ok=True); srt = os.path.join(project, "out", "字幕.srt")
    with open(srt, "w", encoding="utf-8") as fh:
        for n, (c0, c1, t, _) in enumerate(cues, 1): fh.write(f"{n}\n{srt_time(c0)} --> {srt_time(c1)}\n{t}\n\n")
    print(f"字幕 {len(cues)} 條 → {srt}")
    if a.srt_only: return
    src = os.path.join(project, "out", "無字_無聲.mp4")
    if not os.path.exists(src): sys.exit("找不到 out/無字_無聲.mp4，先跑 assemble.py（或把你自己的無字影片放在這個位置）。")
    out = os.path.join(project, "out", "有字_含配音.mp4"); n = burn(src, cues, st, out, wav); print(f"燒好 {n} 格 → {out}")


if __name__ == "__main__":
    main()
