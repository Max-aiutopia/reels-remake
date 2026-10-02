# 用 Higgsfield 配音、生圖、對嘴

先確認有接 Higgsfield 的 MCP：工具清單裡有 `generate_audio`、`generate_image`、`generate_video`、`list_voices`。沒有的話，請使用者在 Claude 的連接器設定裡接上 Higgsfield，或改用其他方式配音（SKILL.md 第 4 步）。

**點數會變動。** 下面是 2026-09 實際扣的點數，只當參考。每次送出前先用同樣的參數加 `get_cost: true` 查一次，跟使用者講總共幾點，他說好再送。

## 用自己的聲音配音

1. 還沒有克隆聲音：呼叫 `create_voice`，會跳出錄音／上傳的視窗，讓使用者自己錄一段（安靜的房間、平常講話的速度）。
2. 用 `list_voices` 找到那個聲音，記下 `voice_id`（`voice_type` 是 `element`），填進 `reels-config.json` 的 `voice.voice_id`。
3. 一句送一次 `generate_audio`（2026-09 一句約 0.1 點）：
   ```json
   {"model": "text2speech_v2", "variant": "seed_speech", "voice_type": "element", "voice_id": "<voice_id>", "prompt": "<script.json 這句的 say>"}
   ```
4. 等它跑完（`jobs_wait` 或 `job_display`），把每句的音檔網址下載成 `voice/01.mp3`、`voice/02.mp3`…：
   ```bash
   curl -L -o "<專案>/voice/01.mp3" "<第 1 句的音檔網址>"
   ```
5. 哪一句念得不好，就只重生那一句。

念法：英文觸發詞寫小寫（「留言cut」才會念成單字）；數字寫國字；一句不要太長，太長就拆兩句。

## 生每一場的圖

- 有人臉、要像使用者本人：用他自己的臉建一個 element，生圖時帶進去。
- 模型 `nano_banana_pro`（2026-09 一張 1K 約 2 點）或 `nano_banana_2`。比例 9:16，一次一張（`count: 1`）。
- 要放字的畫面，生沒有字的底圖，字之後用 `card.py` 或另外疊。不為了改字重生圖。
- 避免一看就是 AI：手機隨手拍的感覺、自然光、真實的場景和雜物；不要棚拍打光、純白背景、完美對稱。

## 對嘴講話（進階，點數最貴）

- **起始圖**：用使用者的臉 element 生一張講者的圖。臉要是畫面最亮的地方（先打一盞亮的主光，色光只當側邊點綴），鏡頭一般 1x、手機距離，不要廣角貼臉。
- **配音**：要對嘴的句子在 script.json 標 `"raw": true`，`vo.py` 會照原檔放、不切不壓，嘴型才對得上。這句的音檔用 `media_import_url`（type 填 audio）匯入，拿到 media id。
- **生影片**：`generate_video`，模型 `wan2_7`，起始圖＋這句配音當 audio reference（2026-09 720p 一秒約 1.5 點，5 秒就是 7.5 點）。prompt 寫「看著鏡頭講話，手機距離不變，不推近」。**不要寫「最後微笑」（ending with a smile 之類）**，講完就自然收尾。
- **放進 scenes.json**：`{"src": "media/talk_05.mp4", "lipsync": true}`。`assemble.py` 會自動對齊（對嘴影片的第 0 秒是配音檔開頭，這一場從第一個字出來才開始，不校正嘴會快半拍）。
- 講者要疊在別的畫面上（去背）：生圖時用綠幕背景，另外寫一支程式去背再疊，見 SKILL.md 第 6 步的「特殊畫面」。
