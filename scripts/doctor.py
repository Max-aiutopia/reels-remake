# -*- coding: utf-8 -*-
"""環境檢查：Python、numpy、Pillow、ffmpeg、Whisper、中文字型。缺什麼就印出怎麼裝。
用法：python3 doctor.py"""
import importlib, os, platform, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OK, BAD, WARN = "✓", "✗", "!"
problems = 0; mac = platform.system() == "Darwin"; win = platform.system() == "Windows"
apple_silicon = mac and platform.machine() == "arm64"

def line(mark, what, note=""):
    print(f"  {mark} {what}" + (f"　{note}" if note else ""))

print("reels-remake 環境檢查\n")
v = sys.version_info
if v >= (3, 9): line(OK, f"Python {v.major}.{v.minor}")
else: line(BAD, f"Python {v.major}.{v.minor}", "要 3.9 以上"); problems += 1

for mod, pipname in (("numpy", "numpy"), ("PIL", "Pillow")):
    try: m = importlib.import_module(mod); line(OK, f"{pipname} {getattr(m, '__version__', '')}")
    except ImportError: line(BAD, pipname, f"安裝：python3 -m pip install {pipname}"); problems += 1

for tool in ("ffmpeg", "ffprobe"):
    if shutil.which(tool):
        ver = subprocess.run([tool, "-version"], capture_output=True, text=True).stdout.split("\n")[0]
        line(OK, ver[:60])
    else:
        how = "brew install ffmpeg" if mac else ("winget install Gyan.FFmpeg" if win else "sudo apt install ffmpeg")
        line(BAD, tool, f"安裝：{how}"); problems += 1

if shutil.which("ffmpeg"):
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if " libx264 " in enc: line(OK, "H.264 編碼器 libx264")
    elif any(e in enc for e in (" h264_videotoolbox ", " h264_mf ", " libopenh264 ")): line(WARN, "沒有 libx264，會改用系統內建的 H.264 編碼器", "畫質稍差、檔案稍大，可以用")
    else: line(WARN, "找不到 H.264 編碼器，會輸出 MPEG-4", "建議裝完整版 ffmpeg")

backend = None
for mod, name in (("mlx_whisper", "mlx-whisper"), ("faster_whisper", "faster-whisper"), ("whisper", "openai-whisper")):
    try: importlib.import_module(mod); backend = name; break
    except Exception: pass
if backend: line(OK, f"逐字稿：{backend}")
else:
    how = "python3 -m pip install mlx-whisper" if apple_silicon else "python3 -m pip install faster-whisper"
    line(WARN, "逐字稿：沒有 Whisper", f"拆片還是能抓剪點跟縮圖，只是沒有逐字稿。要的話：{how}")

try:
    import common
    spec = common.find_font("")
    if spec[0] and "思源" in spec[3]: line(OK, f"字幕字型：{spec[3]}")
    elif spec[0]: line(WARN, f"字幕字型：{spec[3]}", "想跟預設樣式一樣，裝 Noto Sans TC：https://fonts.google.com/noto/specimen/Noto+Sans+TC")
    else: line(BAD, "字幕字型：找不到中文字型", "裝 Noto Sans TC：https://fonts.google.com/noto/specimen/Noto+Sans+TC"); problems += 1
except SystemExit as e: line(BAD, "字型檢查", str(e)); problems += 1
except Exception as e: line(WARN, "字型檢查沒跑完", str(e))

print()
if problems: print(f"有 {problems} 項要先裝好。裝完再跑一次 doctor.py。"); sys.exit(1)
print("可以開始了。")
