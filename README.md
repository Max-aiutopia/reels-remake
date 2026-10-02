# reels-remake（照爆款節奏重做短影音）

A [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin for remaking a vertical short video (Instagram Reels, TikTok, YouTube Shorts) in your own voice and footage, following the rhythm of a video that already works. The scripts handle the parts that repeat on every video; Claude handles the judgment calls: reading the breakdown, writing your script, choosing visuals, and writing custom scenes when a video needs them.

It is built for Traditional Chinese videos, but the scripts work for any language.

[中文說明在下面](#中文說明)

## What it does

- **Breaks down the reference video.** A transcript with a start and end time for every line (Whisper), every visual change including swaps inside the same shot (frame differencing), one thumbnail per shot, a contact sheet, and a table showing where the original cuts inside each line.
- **Joins your voiceover with no dead air.** It trims silence at both ends of each line, shortens pauses inside a line to 0.07 s, and starts each line 0.12 s after the last audible sound of the previous one. Measuring the audible edges matters: joining the files end to end still leaves 0.1–0.2 s of quiet breath and decay between lines.
- **Assembles a 1080×1920 video**, one scene per line, from your images and clips: slow zoom, fit or letterbox with a blurred background, optional film grain, and automatic offset for lip-sync clips.
- **Burns subtitles** one line at a time, split at real pauses in the voice, with list items shown one at a time, and exports an SRT you can import into CapCut desktop and restyle there.
- **Checks the result before you post:** gaps between lines, the longest silence, overlapping subtitles, subtitles on the end card, and a frame from the start and end of every scene on one sheet.

## How it fits together

```
ref.mp4 ── analyze.py ──▶ analysis/  transcript, cuts, shots/, contact sheet, 拆片.md
                             │  Claude writes script.json with you
voice/01.mp3… ── vo.py ──▶ build/vo.wav + timing.json
media/ + scenes.json ── assemble.py ──▶ out/無字_含配音.mp4
                        subs.py ──▶ out/有字_含配音.mp4 + out/字幕.srt
                        check.py ──▶ pass / fail + out/檢查_每場頭尾.jpg
```

`SKILL.md` is the workflow Claude follows, including the rules. `reference/higgsfield.md` covers voice cloning, images and lip-sync through the Higgsfield MCP connector. `reference/settings.md` explains every field in `reels-config.json`.

## Install

Inside Claude Code:

```
/plugin marketplace add Max-aiutopia/reels-remake
/plugin install reels-remake@max-aiutopia
```

Or clone it as a skill:

```bash
git clone https://github.com/Max-aiutopia/reels-remake ~/.claude/skills/reels-remake
```

Then check your setup:

```bash
python3 ~/.claude/skills/reels-remake/scripts/doctor.py
```

You need Python 3.9+, numpy, Pillow and ffmpeg. For transcripts, install mlx-whisper on Apple Silicon Macs or faster-whisper elsewhere. The default subtitle style uses Noto Sans TC Bold. Voice and image generation are optional: use your own Higgsfield account through its MCP connector, any TTS that gives you one file per line, or record yourself.

## Use

Tell Claude: `用 reels-remake 重做這支片：~/Downloads/ref.mp4` (or "remake this reel with reels-remake"). It walks through the steps, shows you the breakdown and the script before going on, and asks before anything that spends credits.

Every step also runs on its own:

```bash
python3 scripts/new_project.py my-video --ref ref.mp4
python3 scripts/analyze.py my-video/ref/ref.mp4 --out my-video/analysis --language zh
python3 scripts/vo.py my-video
python3 scripts/assemble.py my-video
python3 scripts/subs.py my-video          # --srt-only for just the SRT
python3 scripts/check.py my-video
```

Tested on macOS (Apple Silicon), Python 3.9 and ffmpeg 8.1. Windows hasn't been tested yet.

## Please use it responsibly

Use the reference video to study its rhythm, not as material. Don't reuse other creators' footage, images or prompt packs, write your own script instead of translating theirs, and credit the creator whose structure you followed. Only work with files you have the right to use.

## How it was built

I designed this workflow while remaking short videos for my own Instagram account, and the timing rules come from that work, for example no gaps between lines and one item at a time when the voice reads a list. This repo packages the parts that repeat on every video. The code was written with Claude Code.

## 中文說明

Claude Code 的外掛：拿一支已經爆的直式短影音（IG Reels、TikTok、YouTube Shorts）當參考，照它的節奏，用你自己的聲音和畫面重做一支。每支片都要重複做的部分交給程式，要判斷的部分（看懂拆片、寫台詞、挑畫面、需要時寫特殊畫面）交給 Claude。

### 做什麼

- **拆原片**：逐字稿（每句幾秒開始、幾秒結束）、每一次換畫面（連同一個鏡位裡換圖都抓得到）、每顆鏡頭一張縮圖、縮圖總表，再整理成 `拆片.md`：每一句講什麼、這句裡原片換了幾次畫面、換在這句的哪個位置。
- **配音接緊**：每句切掉頭尾空白、句中停頓壓到 0.07 秒，再一句接一句，前一句最後一個聽得到的字到下一句第一個字只隔 0.12 秒。只把音檔頭尾接起來不夠，字前的鼻音、句尾的尾音會讓實際空白多出 0.1～0.2 秒。
- **組片**：一句一場，用你的圖和影片組成 1080×1920 的片。可以慢慢推近、整張放進去配模糊底、加底片顆粒；對嘴影片會自動對齊。
- **燒字幕**：一次一行，在配音真的停頓的地方換行，頓號清單一次只出現一個詞。同時輸出 SRT，可以匯入 CapCut 桌面版再改樣式。
- **交片檢查**：句間空白、全片最長的靜音、字幕重疊、字幕壓到結尾卡，再把每一場的頭尾各抓一格排成一張圖。

### 安裝

在 Claude Code 裡打：

```
/plugin marketplace add Max-aiutopia/reels-remake
/plugin install reels-remake@max-aiutopia
```

或用終端機：

```bash
git clone https://github.com/Max-aiutopia/reels-remake ~/.claude/skills/reels-remake
```

裝好先檢查環境，缺什麼它會印出怎麼裝：

```bash
python3 ~/.claude/skills/reels-remake/scripts/doctor.py
```

要有 Python 3.9 以上、numpy、Pillow、ffmpeg。逐字稿要 Whisper：Apple 晶片的 Mac 裝 mlx-whisper，其他電腦裝 faster-whisper。預設字幕用思源黑體（Noto Sans TC）Bold。配音和生圖可以接你自己的 Higgsfield（MCP），也可以用其他 TTS、或自己錄，一句一個檔就好。

### 怎麼用

跟 Claude 說：「用 reels-remake 重做這支片：~/Downloads/ref.mp4」。它會一步一步做，拆片重點和台詞先給你看，要花點數之前會先問你。

成品在專案的 `out/`：
- `有字_含配音.mp4`：可以直接發。
- `無字_含配音.mp4`＋`字幕.srt`：想在 CapCut 自己微調的話，把影片拉進時間軸，字幕選「匯入字幕」載入 SRT，再套你自己的字幕樣式（CapCut 桌面版可以匯入，手機版不行）。

字幕樣式、句間空白這些都在專案的 `reels-config.json` 改，每個欄位的意思見 `reference/settings.md`。

目前在 macOS（Apple 晶片）、Python 3.9、ffmpeg 8.1 測過，Windows 還沒測。

### 使用前請注意

參考片只拿來學節奏。原作者的畫面、圖、prompt 包不要直接拿來用；台詞用自己的話寫，不要逐字翻譯；發文時標出你參考的創作者。只處理你有權使用的檔案。

### 想學更多

想學更多 AI 影音的做法，來我的 Skool 社群 A&I Utopia 一起練：每週一個主題教學，有作業也有回饋。
https://www.skool.com/ai-utopia-2694/about

## License

MIT
