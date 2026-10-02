# -*- coding: utf-8 -*-
"""開一個新專案資料夾（一支片一個）。
用法：python3 new_project.py <專案資料夾> [--ref 原片.mp4]

專案/
  reels-config.json  你的樣式和節奏（從 config.example.json 複製，改這份就好）
  ref/               原片（參考用，不會出現在成片裡）
  analysis/          analyze.py 的輸出：逐字稿、剪點、縮圖總表、拆片.md
  script.json        台詞（Claude 寫、你確認）
  voice/             每句一個音檔：01.mp3、02.mp3…
  media/             每一場要用的圖或影片
  scenes.json        哪一場用哪個素材
  build/             程式產生的中間檔（vo.wav、timing.json、cues.json）
  out/               成片和檢查圖"""
import argparse, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--ref")
a = ap.parse_args()
p = os.path.abspath(a.project)
for d in ("ref", "analysis", "voice", "media", "build", "out"): os.makedirs(os.path.join(p, d), exist_ok=True)
cfg = os.path.join(p, "reels-config.json")
if not os.path.exists(cfg): shutil.copy(os.path.join(ROOT, "config.example.json"), cfg)
if a.ref:
    if not os.path.exists(a.ref): sys.exit(f"找不到原片：{a.ref}")
    dst = os.path.join(p, "ref", os.path.basename(a.ref))
    if os.path.abspath(a.ref) != dst: shutil.copy(a.ref, dst)
    print("原片：", dst)
print("專案建好了：", p)
print("下一步：python3 analyze.py", os.path.join(p, "ref", os.path.basename(a.ref)) if a.ref else "<原片>", "--out", os.path.join(p, "analysis"))
