# -*- coding: utf-8 -*-
"""reels-remake 共用：讀設定、找 ffmpeg、讀寫音訊、找字型、選影片編碼器。其他腳本都 import 這支。"""
import copy, glob, json, os, platform, shutil, subprocess, sys

import numpy as np

SR = 48000
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv")

DEFAULTS = {
    "subtitle": {
        "font": "",              # 空白＝自動找思源黑體（Noto Sans TC）Bold，找不到就用系統黑體
        "size": 56,              # 字高（1080×1920 畫面上的像素）
        "spacing": 16,           # 字距
        "color": "#DFBA21",
        "stroke": 4,             # 描邊粗細
        "stroke_color": "#000000",
        "center_y": 1336,        # 字的中心在畫面第幾列（1920 高的 70%）
        "max_width": 960,        # 一行最寬，超過就在中間切開
        "hold": 0.25,            # 講完字幕多留幾秒（不會蓋到下一句）
    },
    "pacing": {
        "gap": 0.12,             # 前一句最後一個聽得到的字 → 下一句第一個字
        "edge_db": -30,          # 比這句最大聲低多少 dB 以下算「沒在講」（算句子頭尾用）
        "silence_db": -38,       # 切頭尾空白、壓句中停頓用的門檻
        "keep_pause": 0.07,      # 句中停頓壓到幾秒
        "end_hold": 0.3,         # 最後一句講完再停幾秒
        "max_gap": 0.2,          # check.py：句間空白超過這個就報錯
    },
    "video": {"width": 1080, "height": 1920, "fps": 30, "crf": 18, "grain": 0},
    "voice": {"model": "text2speech_v2", "variant": "seed_speech", "voice_type": "element", "voice_id": ""},
    "transcribe": {"language": "", "model": ""},
}


def merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict): out[k] = merge(out[k], v)
        else: out[k] = v
    return out


def load_config(project):
    p = os.path.join(project, "reels-config.json")
    user = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    return merge(DEFAULTS, {k: v for k, v in user.items() if not k.startswith("_")})


def load_json(path, what):
    if not os.path.exists(path): sys.exit(f"找不到 {path}（{what}）")
    return json.load(open(path, encoding="utf-8"))


def save_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def need(tool):
    p = shutil.which(tool)
    if not p: sys.exit(f"找不到 {tool}。先跑 scripts/doctor.py 看怎麼安裝。")
    return p


def load_audio(path, sr=SR):
    raw = subprocess.run([need("ffmpeg"), "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def save_wav(x, path, sr=SR):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    subprocess.run([need("ffmpeg"), "-v", "error", "-y", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-", "-c:a", "pcm_s16le", path],
                   input=np.asarray(x, np.float32).tobytes(), check=True)


def video_info(path):
    out = subprocess.run([need("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,avg_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out); s = j["streams"][0]; num, den = s.get("avg_frame_rate", "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return {"width": int(s["width"]), "height": int(s["height"]), "fps": fps, "duration": float(j["format"]["duration"])}


def duration(path):
    out = subprocess.run([need("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def hex_rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def envelope_db(x, sr=SR, hop=0.01):
    """每 10ms 一格的音量（dB，相對整段最大聲）。"""
    fr = int(sr * hop); n = len(x) // fr
    if n == 0: return np.array([-120.0])
    e = np.sqrt((x[:n * fr].reshape(n, fr) ** 2).mean(axis=1) + 1e-12)
    return 20 * np.log10(e / e.max())


# ---------- 字型 ----------
def _font_dirs():
    home = os.path.expanduser("~"); sysname = platform.system()
    if sysname == "Darwin": return [home + "/Library/Fonts", "/Library/Fonts", "/System/Library/Fonts"]
    if sysname == "Windows":
        win = os.environ.get("WINDIR", r"C:\Windows")
        return [os.path.join(win, "Fonts"), os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]
    return [home + "/.local/share/fonts", home + "/.fonts", "/usr/share/fonts", "/usr/local/share/fonts"]


def _pick_face(path, want_family, want_style):
    """.ttc 裡有好幾個字型，挑 family／style 對的那一個。"""
    from PIL import ImageFont
    for i in range(32):
        try: f = ImageFont.truetype(path, 20, index=i)
        except Exception: break
        fam, sty = f.getname()
        if want_family.lower() in fam.lower() and (not want_style or want_style.lower() in sty.lower()): return i
    return None


def find_font(configured=""):
    """回傳 (路徑, ttc index, 可變字型要設的粗細名稱或 None, 說明)。"""
    if configured:
        if not os.path.exists(configured): sys.exit(f"reels-config.json 指定的字型不存在：{configured}")
        return configured, 0, None, "設定檔指定"
    names = ["NotoSansTC-Bold.ttf", "NotoSansTC-Bold.otf", "NotoSansCJKtc-Bold.otf", "SourceHanSansTC-Bold.otf"]
    for d in _font_dirs():
        for n in names:
            for p in glob.glob(os.path.join(d, "**", n), recursive=True): return p, 0, None, "思源黑體 Bold"
        for p in glob.glob(os.path.join(d, "**", "NotoSansTC*VariableFont*.ttf"), recursive=True): return p, 0, "Bold", "思源黑體（可變字型，設成 Bold）"
        for p in glob.glob(os.path.join(d, "**", "NotoSansCJK-Bold.ttc"), recursive=True):
            i = _pick_face(p, "Noto Sans CJK TC", "Bold")
            if i is not None: return p, i, None, "思源黑體 CJK Bold"
    sysname = platform.system()
    if sysname == "Darwin":
        cands = glob.glob("/System/Library/Fonts/PingFang.ttc") + glob.glob("/System/Library/AssetsV2/*/*/AssetData/PingFang.ttc")
        for p in cands:
            i = _pick_face(p, "PingFang TC", "Semibold")
            if i is not None: return p, i, None, "蘋方-繁 Semibold（系統字型；裝思源黑體會更接近預設樣式）"
        for p in glob.glob("/System/Library/Fonts/STHeiti Medium.ttc"): return p, 0, None, "華文黑體（系統字型）"
    if sysname == "Windows":
        p = os.path.join(_font_dirs()[0], "msjhbd.ttc")
        if os.path.exists(p): return p, 0, None, "微軟正黑體 Bold（系統字型）"
    return None, 0, None, "找不到中文字型"


def load_font(spec, size):
    from PIL import ImageFont
    path, index, variation, _ = spec
    if not path: sys.exit("找不到中文字型。裝思源黑體（Noto Sans TC）或在 reels-config.json 的 subtitle.font 填字型檔路徑。")
    f = ImageFont.truetype(path, size, index=index)
    if variation:
        try: f.set_variation_by_name(variation)
        except Exception: pass
    return f


# ---------- 影片編碼 ----------
_ENC = None
def encoder_args(crf=18):
    """有 libx264 用 libx264，沒有就用系統內建的 H.264 編碼器。"""
    global _ENC
    if _ENC is None:
        out = subprocess.run([need("ffmpeg"), "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        if " libx264 " in out: _ENC = "libx264"
        elif " h264_videotoolbox " in out: _ENC = "h264_videotoolbox"
        elif " h264_mf " in out: _ENC = "h264_mf"
        elif " libopenh264 " in out: _ENC = "libopenh264"
        else: _ENC = "mpeg4"
    if _ENC == "libx264": return ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if _ENC == "h264_videotoolbox": return ["-c:v", "h264_videotoolbox", "-b:v", "12M", "-pix_fmt", "yuv420p"]
    if _ENC in ("h264_mf", "libopenh264"): return ["-c:v", _ENC, "-b:v", "12M", "-pix_fmt", "yuv420p"]
    return ["-c:v", "mpeg4", "-q:v", "3", "-pix_fmt", "yuv420p"]


def project_dir(argv_value):
    p = os.path.abspath(argv_value or ".")
    if not os.path.isdir(p): sys.exit(f"找不到專案資料夾：{p}")
    return p
