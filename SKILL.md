---
name: reels-remake
description: 照一支爆紅短影音（IG Reels／TikTok／YouTube Shorts）的節奏，用自己的聲音和畫面重做一支直式短影音：拆片（逐字稿、每一次換畫面、縮圖總表）→ 寫台詞 → 配音一句接一句不留空白 → 組片 → 燒字幕（也輸出 SRT 給 CapCut）→ 交片檢查。觸發詞：「重做這支片」「照這支 Reels 的節奏做我的版本」「拆這支片」「拆片」「配音接緊」「句子之間不要有空白」「燒字幕」「出 SRT」「remake this reel」。不適用：長影片剪輯、多機位、直播切片、橫式影片。
---

# reels-remake：照爆款的節奏，做你自己的版本

下面的 `$SKILL` 指這個 skill 的資料夾（載入時顯示的 Base directory）。每一步都是跑 `python3 "$SKILL/scripts/<腳本>.py"`，腳本只用 Python 3.9+、numpy、Pillow、ffmpeg。
`<專案>` 是這支片的資料夾（第 1 步建）。腳本的說明都在各支檔案開頭，參數不確定就先讀那段。

## 規則（每支片都照做）

1. **原片只拿來學節奏。** 原作者的畫面、圖、prompt 包不要直接用或轉貼；台詞用自己的話寫，不要逐字翻譯。發文時標「流程參考 @原作者」。原片要使用者自己提供（他有權使用的檔案）。
2. **句子之間不能有空白。** 每個句間（前一句最後一個字到下一句第一個字）不超過 0.2 秒，句中的氣口也切掉。重做的句子通常比原片短：讓那一場畫面跟著縮，**不要為了對齊原片的秒數留空白**。`vo.py` 已經照這條接，`check.py` 會量。
3. **一句一場。** 換場放在每句第一個字出來的那一刻。原片在這句裡又換了幾次畫面，這一場就用幾個素材，照比例換（`拆片.md` 有位置）。
4. **字幕**一次一行、不放標點；頓號清單一次只出現一個詞（`subs.py` 自動處理）。字幕和畫面上的字不能擋到臉，也不能擋到畫面重點（輸入框、數字、產品）。擋到就用 `sub_y` 改那一句的高度。
5. **留言觸發詞用一個英文單字**（例如 CUT、STYLE），結尾卡、配音、字幕、貼文、私訊都用同一個。配音那欄（`say`）英文寫小寫，TTS 才會念成單字；數字寫國字（「二十一秒」），字幕那欄（`sub`）再寫阿拉伯數字。
6. **對嘴講話的畫面**：prompt 不要寫「最後微笑」這類收尾（看起來很怪）；臉要是畫面最亮的地方；鏡頭用一般 1x、手機距離，不要廣角貼臉。
7. **花點數之前先問。** 配音、生圖、對嘴都要點數：先跟使用者講要生成什麼、大概幾點，他說好才送。圖上的字一律後製疊上去，不為改字重生圖。
8. **每一步做完給使用者看**（拆片重點、台詞表、檢查總表），他確認再往下。

## 第一次用

```bash
python3 "$SKILL/scripts/doctor.py"
```
缺什麼照印出來的指令裝。安裝要在使用者自己的終端機跑的，把指令給他。逐字稿需要 Whisper（Apple 晶片的 Mac 裝 mlx-whisper，其他電腦裝 faster-whisper），沒有也能做，只是拆片少了逐字稿。

## 流程

### 1. 開專案
```bash
python3 "$SKILL/scripts/new_project.py" <專案> --ref <原片.mp4>
```
建好 `ref/ analysis/ voice/ media/ build/ out/` 和 `reels-config.json`（樣式、節奏，說明見 `reference/settings.md`）。

### 2. 拆原片
```bash
python3 "$SKILL/scripts/analyze.py" <專案>/ref/<原片.mp4> --out <專案>/analysis --language zh
```
讀 `analysis/拆片.md`，用 Read 看 `analysis/縮圖總表.jpg`。跟使用者講這支片的結構：前 3 秒講什麼、畫面怎麼抓人，總共幾句、每句在做什麼（鋪陳、示範、轉折、CTA），平均幾秒換一次畫面，結尾怎麼要留言。
剪點抓太多就把 `--threshold` 調高（預設 11），漏掉就調低。英文片 `--language en`。

### 3. 寫台詞 → `<專案>/script.json`
- 照原片的結構寫，句數可以不同，但段落要對上：開頭鉤子、鋪陳、示範、轉折、CTA。
- 每句短。中文一秒大約念 4.5～6 個字，原片那句幾秒，就抓差不多的字數（寧可短，不要長）。
- 給使用者看台詞表（# ｜原片這句｜我們這句），他確認後才配音。

```json
{"lines": [
  {"say": "我一直覺得，AI遲早會進到剪接", "sub": "我一直覺得，AI 遲早會進到剪接"},
  {"say": "這支二十一秒的片，四十八次換畫面", "sub": "這支 21 秒的片，48 次換畫面", "tempo": 1.05},
  {"say": "留言cut，這套流程給你", "sub": "留言 CUT，這套流程給你", "no_sub": true}
]}
```
欄位：`say` 給 TTS 念的字；`sub` 字幕的字（沒寫就用 say）；`tempo` 這句加速（最多 1.3）；`raw: true` 這句要拿去做對嘴，配音不切不壓；`no_sub: true` 不上字幕（結尾卡上已經有字）；`sub_y` 這句字幕的高度（字的中心在第幾列，1920 高的畫面）。

### 4. 配音 → `<專案>/voice/01.mp3`、`02.mp3`…
一句一個檔，檔名是兩位數編號（wav、m4a 也可以）。三種來源：
- **Higgsfield**（有接 Higgsfield MCP）：用使用者自己的克隆聲音，做法見 `reference/higgsfield.md`。
- **其他 TTS**（例如 ElevenLabs）：一句生一個檔，照編號存。
- **自己錄**：一句一個檔。安靜的房間，每句前後留一點空白就好，頭尾的空白 `vo.py` 會切。

### 5. 配音接成一條 → `build/vo.wav`、`build/timing.json`
```bash
python3 "$SKILL/scripts/vo.py" <專案>
```
看印出來的表：句間空白要在 0.2 秒內，超過會標 ⚠。通常是那句音檔的頭尾有雜音或換氣聲，聽一下、修掉或重生那一句。整支想快一點，就給幾句加 `tempo`（1.05～1.15 聽不太出來）。

### 6. 畫面 → `<專案>/media/`、`<專案>/scenes.json`
- 一句一場。`scenes.json` 的格式寫在 `scripts/assemble.py` 開頭，先讀那段。
- 素材來源：使用者自己的影片、截圖、螢幕錄影；生成的圖（做法見 `reference/higgsfield.md`，有人臉的用使用者的臉）；`card.py` 做的字卡。
- 原片這句裡換了幾次畫面，這一場就放幾個素材，`weights` 照 `拆片.md` 的位置分。
- 結尾 CTA 卡：
  ```bash
  python3 "$SKILL/scripts/card.py" <專案>/media/end.png --bg "#163CC4" --color "#0A0E22" --line "留　言:60" --line "CUT:320" --line "這套流程給你:72"
  ```
  結尾那句在 script.json 標 `"no_sub": true`（卡上已經有字）。
- **特殊畫面**（假介面、打字動畫、上下對照、講者去背疊在畫面上）`assemble.py` 做不到：另外寫一支 Python，用 Pillow／numpy 一格一格畫、用 ffmpeg 輸出 1080×1920、30fps 的 mp4，再當素材放進 scenes.json。字幕那一條（預設字的中心 y=1336，上下各留 100px）不要放重要的東西。

### 7. 組片 → `out/無字_無聲.mp4`、`out/無字_含配音.mp4`
```bash
python3 "$SKILL/scripts/assemble.py" <專案>
```

### 8. 字幕 → `out/有字_含配音.mp4`、`out/字幕.srt`
```bash
python3 "$SKILL/scripts/subs.py" <專案>
```
使用者想在 CapCut 自己上字：加 `--srt-only`，只出 SRT。

### 9. 交片檢查
```bash
python3 "$SKILL/scripts/check.py" <專案>
```
有 ✗ 先修。用 Read 看 `out/檢查_每場頭尾.jpg`：換場對不對、字幕有沒有擋到臉或重點、結尾卡上有沒有多一行字幕。

### 10. 交給使用者
- 直接發：`out/有字_含配音.mp4`。
- 想在 CapCut 微調：把 `out/無字_含配音.mp4` 拉進時間軸，從字幕的「匯入字幕」選 `out/字幕.srt`，再套自己的字幕樣式。CapCut 桌面版能匯入 SRT，手機版不行。
- 貼文文案：開頭跟影片的鉤子同一句；結尾「留言 ＜英文觸發詞＞」；標「流程參考 @原作者」。

## 改樣式、改節奏

都在 `<專案>/reels-config.json`，每個欄位的意思見 `reference/settings.md`。改完從受影響的那一步重跑：只改字幕樣式 → `subs.py`；改節奏（gap 等）→ `vo.py` 之後全部重跑；改畫面 → `assemble.py` 之後重跑。

## 出問題

| 狀況 | 怎麼辦 |
|---|---|
| vo.py 說少了音檔 | 檔名要兩位數：01.mp3，不是 1.mp3 |
| 逐字稿是簡體 | `python3 -m pip install opencc-python-reimplemented`，再跑一次 analyze.py |
| 逐字稿整支黏成一句 | 不要給 Whisper 加 initial_prompt |
| 字幕字型不對 | 裝 Noto Sans TC（思源黑體），或在 reels-config.json 的 `subtitle.font` 寫字型檔路徑 |
| 剪點抓太多／太少 | analyze.py 的 `--threshold` 調高／調低 |
| 句間空白超過 0.2 秒 | 那句音檔頭尾有雜音或換氣聲，修掉或重生那句；不要把 `pacing.max_gap` 調大 |
| 對嘴嘴型快半拍 | scenes.json 那個對嘴影片加 `"lipsync": true`，script.json 那句標 `"raw": true` |
