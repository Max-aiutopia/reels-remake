# -*- coding: utf-8 -*-
"""組片（簡易版）：每一場放一張圖或一段影片，可以好幾個素材輪流，長度跟著配音走，輸出無字的成片。
用法：python3 assemble.py [專案資料夾]
讀：scenes.json、build/timing.json、build/vo.wav、reels-config.json（video）
寫：out/無字_無聲.mp4、out/無字_含配音.mp4、build/scenes_timing.json

scenes.json：
{"scenes": [
  {"line": 1, "media": "media/01.jpg"},
  {"line": 3, "media": ["media/03a.mp4", "media/03b.png"], "weights": [3, 7]},
  {"line": 15, "media": {"src": "media/end.png", "zoom": [1, 1]}}
]}
- 一場從那一句第一個字出來的那一刻開始，到下一場開始為止；沒寫到的句子沿用上一場。第一場一律從 0 秒開始。
- media 可以放一個或好幾個（圖：jpg/png/webp；影片：mp4/mov）。好幾個就照 weights 分這一場的時間，沒寫就平分。
  照原片節奏換：analysis/拆片.md 列了原片每句裡換畫面的位置（例如 30%、70%），weights 就寫 [3, 4, 3]。
- 素材寫成物件可以調細節：{"src": "...", "from": 2.5, "fit": "contain", "zoom": [1.05, 1.0], "focus": [0.5, 0.3]}
  from：影片從第幾秒開始用　fit：cover 裁滿（預設）／contain 整張放進去、空的地方補模糊底
  zoom：這段開頭→結尾的放大倍率（圖預設 [1.0, 1.06] 慢慢推近，影片預設不推）　focus：推近時對準哪裡（0～1，預設正中間）
- 對嘴影片加 "lipsync": true：對嘴影片的第 0 秒是那句配音檔的開頭，但這一場從第一個字出來才開始（晚約 0.15 秒），
  不校正嘴會快半拍。lipsync 會自動算 from 對齊。對嘴影片用的是另一句的配音就寫那句的號碼，例如 "lipsync": 5。
特殊畫面（假介面、打字、對照、講者去背疊在上面…）這支做不到，請 Claude 另外寫一支產生影片的程式，輸出的影片再當素材放進來。"""
import os, subprocess, sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def ease(u):
    u = min(max(u, 0.0), 1.0); return u * u * (3 - 2 * u)


def norm_item(m):
    if isinstance(m, str): m = {"src": m}
    m = dict(m); ext = os.path.splitext(m["src"])[1].lower()
    if ext in common.IMAGE_EXT: m["kind"] = "image"
    elif ext in common.VIDEO_EXT: m["kind"] = "video"
    else: sys.exit(f"不認得這個素材的格式：{m['src']}（圖用 jpg/png/webp，影片用 mp4/mov）")
    m.setdefault("fit", "cover"); m.setdefault("zoom", [1.0, 1.06] if m["kind"] == "image" else [1.0, 1.0])
    m.setdefault("focus", [0.5, 0.5]); m.setdefault("from", 0.0)
    return m


def crop_box(iw, ih, W, H, z, focus):
    """cover 模式：放大 z 倍時，原圖上要裁哪一塊。"""
    s0 = max(W / iw, H / ih); cw0, ch0 = W / s0, H / s0; fx, fy = focus
    x0, y0 = (iw - cw0) * fx, (ih - ch0) * fy; cw, ch = cw0 / z, ch0 / z
    x0 += (cw0 - cw) * fx; y0 += (ch0 - ch) * fy
    return (x0, y0, x0 + cw, y0 + ch)


def contain_base(im, W, H):
    s = min(W / im.width, H / im.height); fg = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    sb = max(W / im.width, H / im.height); bg = im.resize((max(1, round(im.width * sb)), max(1, round(im.height * sb))), Image.BILINEAR)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.55))
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2)); return bg


class ImageSource:
    def __init__(self, project, m, W, H):
        im = Image.open(os.path.join(project, m["src"])).convert("RGB"); self.m, self.W, self.H = m, W, H
        if m["fit"] == "contain": im = contain_base(im, W, H)
        zmax = max(m["zoom"]); need = max(W / im.width, H / im.height) * zmax
        if need < 1.0: im = im.resize((max(W, round(im.width * need)), max(H, round(im.height * need))), Image.LANCZOS)
        self.im = im

    def frame(self, u):
        z0, z1 = self.m["zoom"]; z = z0 + (z1 - z0) * ease(u)
        box = crop_box(self.im.width, self.im.height, self.W, self.H, z, self.m["focus"])
        return self.im.resize((self.W, self.H), Image.BICUBIC, box=box)

    def close(self): pass


class VideoSource:
    def __init__(self, project, m, W, H, fps):
        self.m, self.W, self.H, self.last = m, W, H, None; src = os.path.join(project, m["src"]); fx, fy = m["focus"]
        if m["fit"] == "contain":
            vf = (f"fps={fps},split=2[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.2[bg];"
                  f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
            args = ["-filter_complex", vf]
        else:
            args = ["-vf", f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:(in_w-{W})*{fx}:(in_h-{H})*{fy}"]
        self.p = subprocess.Popen([common.need("ffmpeg"), "-v", "error", "-ss", str(m["from"]), "-i", src, *args, "-an",
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)      # 這段用完會直接關掉解碼，不要讓 Broken pipe 的訊息嚇到人

    def frame(self, u):
        buf = self.p.stdout.read(self.W * self.H * 3)
        if len(buf) == self.W * self.H * 3: self.last = Image.frombuffer("RGB", (self.W, self.H), buf, "raw", "RGB", 0, 1)
        if self.last is None: self.last = Image.new("RGB", (self.W, self.H))
        z0, z1 = self.m["zoom"]
        if abs(z0 - 1) < 1e-3 and abs(z1 - 1) < 1e-3: return self.last
        z = z0 + (z1 - z0) * ease(u); box = crop_box(self.W, self.H, self.W, self.H, z, self.m["focus"])
        return self.last.resize((self.W, self.H), Image.BICUBIC, box=box)

    def close(self):
        try: self.p.stdout.close(); self.p.kill()
        except Exception: pass


def grain_layer(W, H, amount, rng):
    """粗顆粒：先在 1/3 解析度做雜訊再放大，看起來像底片顆粒而不是數位雜點。"""
    n = rng.standard_normal((H // 3, W // 3)).astype(np.float32)
    g = np.asarray(Image.fromarray(n).resize((W, H), Image.BICUBIC), np.float32)   # float32 陣列 → F 模式
    return g / (g.std() + 1e-6) * amount


def plan_segments(project, scenes, lines, total):
    starts = {ln["line"]: (0.0 if i == 0 else ln["onset"]) for i, ln in enumerate(lines)}; by_no = {ln["line"]: ln for ln in lines}
    sc = sorted(scenes, key=lambda s: s["line"]); out = []
    for k, s in enumerate(sc):
        if s["line"] not in starts: sys.exit(f"scenes.json 第 {k + 1} 場寫 line {s['line']}，但台詞只有 {len(lines)} 句。")
        t0 = 0.0 if k == 0 else starts[s["line"]]; t1 = starts[sc[k + 1]["line"]] if k + 1 < len(sc) else total
        if t1 <= t0: sys.exit(f"第 {k + 1} 場（line {s['line']}）長度是 0，檢查 scenes.json 的 line 有沒有重複。")
        items = [norm_item(m) for m in (s["media"] if isinstance(s["media"], list) else [s["media"]])]
        for m in items:
            if not os.path.exists(os.path.join(project, m["src"])): sys.exit(f"找不到素材：{m['src']}")
        w = s.get("weights") or [1] * len(items)
        if len(w) != len(items): sys.exit(f"第 {k + 1} 場的 weights 有 {len(w)} 個，素材有 {len(items)} 個，要一樣多。")
        acc = np.cumsum([0] + list(w)) / float(sum(w)); segs = []
        for j, m in enumerate(items):
            a, b = t0 + (t1 - t0) * acc[j], t0 + (t1 - t0) * acc[j + 1]
            if m.get("lipsync"):                      # 對嘴：影片第 0 秒＝那句配音檔開頭（timing 的 start）
                n = s["line"] if m["lipsync"] is True else int(m["lipsync"])
                if n not in by_no: sys.exit(f"第 {k + 1} 場的 lipsync 寫第 {n} 句，但台詞沒有這一句。")
                if not by_no[n].get("raw"): print(f"  ! 第 {n} 句拿去對嘴，但 script.json 沒標 raw：配音被壓過，嘴型可能對不上。")
                m["from"] = float(m["from"]) + max(0.0, a - by_no[n]["start"])
            segs.append((a, b, m))
        out.append({"scene": k + 1, "line": s["line"], "start": round(t0, 3), "end": round(t1, 3), "segments": segs})
    return out


def main():
    project = common.project_dir(sys.argv[1] if len(sys.argv) > 1 else ".")
    cfg = common.load_config(project); V = cfg["video"]; W, H, fps = int(V["width"]), int(V["height"]), int(V["fps"])
    timing = common.load_json(os.path.join(project, "build", "timing.json"), "先跑 vo.py")
    scenes = common.load_json(os.path.join(project, "scenes.json"), "哪一場用哪個素材，格式見 assemble.py 開頭")["scenes"]
    total = float(timing["total"]); plan = plan_segments(project, scenes, timing["lines"], total)
    segs = [sg for sc in plan for sg in sc["segments"]]; N = int(round(total * fps))
    out_dir = os.path.join(project, "out"); os.makedirs(out_dir, exist_ok=True)
    silent = os.path.join(out_dir, "無字_無聲.mp4"); voiced = os.path.join(out_dir, "無字_含配音.mp4")
    enc = subprocess.Popen([common.need("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                            *common.encoder_args(V["crf"]), "-movflags", "+faststart", silent], stdin=subprocess.PIPE)
    rng = np.random.default_rng(7); amount = float(V.get("grain") or 0); cur, src = -1, None
    print(f"組片：{len(plan)} 場、{len(segs)} 段素材、{N} 格（{total:.2f} 秒）…")
    for i in range(N):
        t = i / fps; k = cur if cur >= 0 and segs[cur][0] <= t < segs[cur][1] else next((j for j, s in enumerate(segs) if s[0] <= t < s[1]), len(segs) - 1)
        if k != cur:
            if src: src.close()
            m = segs[k][2]; src = ImageSource(project, m, W, H) if m["kind"] == "image" else VideoSource(project, m, W, H, fps); cur = k
        a, b = segs[k][0], segs[k][1]; im = src.frame((t - a) / max(b - a, 1e-6))
        if amount > 0:
            arr = np.asarray(im, np.float32) + grain_layer(W, H, amount, rng)[..., None]
            enc.stdin.write(np.clip(arr, 0, 255).astype(np.uint8).tobytes())
        else: enc.stdin.write(im.tobytes())
    if src: src.close()
    enc.stdin.close(); enc.wait()
    vo = os.path.join(project, "build", "vo.wav")
    subprocess.run([common.need("ffmpeg"), "-v", "error", "-y", "-i", silent, "-i", vo, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", voiced], check=True)
    common.save_json([{k: v for k, v in sc.items() if k != "segments"} | {"media": [s[2]["src"] for s in sc["segments"]]} for sc in plan],
                     os.path.join(project, "build", "scenes_timing.json"))
    print("→", silent); print("→", voiced)


if __name__ == "__main__":
    main()
