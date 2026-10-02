# reels-config.json 每個欄位

每支片的專案資料夾裡一份（`new_project.py` 會從 `config.example.json` 複製）。只改你要的欄位，沒寫的用預設值。

## subtitle（字幕）

| 欄位 | 預設 | 意思 |
|---|---|---|
| `font` | 空白 | 字型檔路徑。空白＝自動找思源黑體（Noto Sans TC）Bold，沒裝就用系統黑體（Mac 蘋方、Windows 微軟正黑體） |
| `size` | 56 | 字的大小（1080×1920 畫面上的像素） |
| `spacing` | 16 | 字距 |
| `color` | `#DFBA21` | 字的顏色（金黃） |
| `stroke` | 4 | 描邊粗細 |
| `stroke_color` | `#000000` | 描邊顏色 |
| `center_y` | 1336 | 字的中心在畫面第幾列（1920 高的 70%）。整支都要改高度就改這裡；只改某一句用 script.json 的 `sub_y` |
| `max_width` | 960 | 一行最寬（左右各留 60px），超過就切成兩段輪流出現 |
| `hold` | 0.25 | 講完字幕多留幾秒，不會蓋到下一句 |

預設樣式換算自剪映／CapCut 的設定：思源黑體粗、字級 10、字距 3、顏色 #DFBA21、黑色描邊、位置 Y −755。

## pacing（節奏）

| 欄位 | 預設 | 意思 |
|---|---|---|
| `gap` | 0.12 | 前一句最後一個聽得到的字 → 下一句第一個字，隔幾秒 |
| `edge_db` | -30 | 比這句最大聲低多少 dB 以下算「沒在講」，用來找每句第一個、最後一個字 |
| `silence_db` | -38 | 切頭尾空白、壓句中停頓用的門檻 |
| `keep_pause` | 0.07 | 句中的停頓（逗號那種）壓到幾秒 |
| `end_hold` | 0.3 | 最後一句講完，畫面再停幾秒 |
| `max_gap` | 0.2 | `check.py` 檢查用：句間空白超過這個就報錯 |

## video（影片）

| 欄位 | 預設 | 意思 |
|---|---|---|
| `width`、`height` | 1080、1920 | 直式 9:16 |
| `fps` | 30 | |
| `crf` | 18 | 畫質（數字越小越好、檔案越大），用 libx264 時才有作用 |
| `grain` | 0 | 底片顆粒強度，0 是關掉。AI 圖太乾淨時可以試 4～8 |

## voice（配音，給 Higgsfield 用）

| 欄位 | 預設 | 意思 |
|---|---|---|
| `model` | `text2speech_v2` | |
| `variant` | `seed_speech` | |
| `voice_type` | `element` | 自己克隆的聲音是 element |
| `voice_id` | 空白 | 你的聲音 id（`list_voices` 查得到） |

## transcribe（逐字稿）

| 欄位 | 預設 | 意思 |
|---|---|---|
| `language` | 空白 | 空白＝自動偵測；中文片填 `zh` 比較穩 |
| `model` | 空白 | 空白＝whisper-large-v3-turbo（mlx-whisper）／large-v3-turbo（faster-whisper）／turbo（openai-whisper） |
