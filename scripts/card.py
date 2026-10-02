# -*- coding: utf-8 -*-
"""字卡：做一張 1080×1920 的大字卡（結尾卡、開頭標題卡），存成 PNG，再當素材放進 scenes.json。
用法：python3 card.py media/end.png --bg "#163CC4" --color "#0A0E22" --line "留　言:60" --line "CUT:320" --line "這套拆片流程給你:72"
每個 --line 是「字:字級」，由上往下排，整組垂直置中。字級省略就是 80。"""
import argparse, os, sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--bg", default="#163CC4"); ap.add_argument("--color", default="#0A0E22")
ap.add_argument("--line", action="append", required=True); ap.add_argument("--gap", type=int, default=40)
ap.add_argument("--width", type=int, default=1080); ap.add_argument("--height", type=int, default=1920); ap.add_argument("--font", default="")
a = ap.parse_args()
spec = common.find_font(a.font); W, H = a.width, a.height
items = []
for ln in a.line:
    text, _, size = ln.rpartition(":")
    if not text or not size.isdigit(): text, size = ln, "80"
    f = common.load_font(spec, int(size)); box = f.getbbox(text); items.append((text, f, box))
total = sum(b[3] - b[1] for _, _, b in items) + a.gap * (len(items) - 1)
im = Image.new("RGB", (W, H), common.hex_rgb(a.bg)); d = ImageDraw.Draw(im); y = (H - total) / 2
for text, f, b in items:
    w = b[2] - b[0]; d.text(((W - w) / 2 - b[0], y - b[1]), text, font=f, fill=common.hex_rgb(a.color)); y += (b[3] - b[1]) + a.gap
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True); im.save(a.out); print("→", a.out)
