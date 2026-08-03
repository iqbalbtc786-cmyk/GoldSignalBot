# GoldSignalBot

XAUUSD (gold) trading signal bot — multi-timeframe technical analysis
(EMA/RSI/Bollinger Bands/ATR + DXY bias) sent to Telegram every 30
minutes — plus a **social media auto-posting workflow** that turns
every signal into ready-to-publish content automatically.

## اردو میں مختصر تعارف

یہ بوٹ گولڈ (XAUUSD) کے ٹریڈنگ سگنلز خود بخود تیار کرتا ہے، اور اب اس میں
ایک **مکمل سوشل میڈیا آٹو ورک فلو** بھی شامل ہے جو ہر سگنل کے لیے:

1. ایک زبردست "ہک" (hook) کے ساتھ کیپشن لکھتا ہے،
2. ایک برانڈڈ پوسٹ امیج (تصویر) بناتا ہے،
3. ایک مختصر ریل/ویڈیو (9:16) بناتا ہے،
4. اور Telegram، Facebook، Instagram اور Twitter/X پر خود بخود پوسٹ کرتا ہے
   (جن پلیٹ فارمز کی API keys آپ نے سیٹ کی ہوں)۔

نیچے مکمل سیٹ اپ گائیڈ انگریزی میں موجود ہے۔

## 1. Trading signal bot

```
pip install -r requirements.txt
export TELEGRAM_TOKEN=...
export TELEGRAM_CHAT_ID=...
python bot.py
```

Runs `analyze_xauusd()` every 30 minutes; sends a formatted signal to
Telegram whenever confidence >= `CONFIDENCE_THRESHOLD` (70% by
default), and always sends a "no trade" update otherwise.

## 2. Social media auto-posting workflow

After every signal, `bot.py` calls `social/pipeline.py`, which:

1. **Writes a hook + caption** (`social/hooks.py`, `social/captions.py`)
   — a curated bank of proven trading-content hooks (e.g. *"🚨 Gold just
   flashed a BUY signal at $2,415.32 — here's the setup"*), filled in
   with live numbers. If `OPENAI_API_KEY` is set, it asks an LLM to
   write a fresh one instead; otherwise it works fully offline.
2. **Renders a branded image card** (`social/image_card.py`, Pillow) —
   direction badge, price, confidence bar, entry/SL/TP levels, on a
   gold/navy theme with a decorative candlestick background.
3. **Renders a short vertical reel** (`social/video_reel.py`, MoviePy)
   — the same information revealed in sequence (hook → badge → price →
   confidence bar filling → TP/SL rows → CTA), sized for Instagram
   Reels/TikTok/YouTube Shorts (1080x1920). No system `ffmpeg` install
   needed — `imageio-ffmpeg` ships a portable binary.
4. **Publishes** to every channel that has credentials configured
   (`social/publishers/`) — a channel with no keys set is skipped, so
   you can start with Telegram only and add the others later.

### Enabling channels

Copy `.env.example` to `.env` (or set these as real environment
variables) and fill in only the channels you want:

| Channel | Needs | Notes |
|---|---|---|
| **Telegram** | `TELEGRAM_TOKEN`, `TELEGRAM_SOCIAL_CHANNEL_ID` (falls back to `TELEGRAM_CHAT_ID`) | Works immediately — direct file upload, no extra setup. |
| **Facebook Page** | `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN` | Direct file upload via Graph API. Create a Meta app + Page token with `pages_manage_posts`. |
| **Instagram** | `IG_BUSINESS_ACCOUNT_ID`, `IG_ACCESS_TOKEN`, `MEDIA_PUBLIC_BASE_URL` | Instagram's API only accepts a **public URL** for media, not a file upload. Deploy `media_server.py` (the `web` process in the `Procfile`) somewhere with a public hostname and point `MEDIA_PUBLIC_BASE_URL` at it. |
| **Twitter/X** | `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET` | Needs a developer app with read+write access. |

Other useful settings:

- `SOCIAL_AUTOPOST_ENABLED=false` — generate content but don't publish
  anywhere (useful for previewing).
- `SOCIAL_CONFIDENCE_THRESHOLD` — minimum confidence before posting
  (default 70, matches the trading signal threshold).
- `POST_REEL_ON_NEUTRAL` — also render/post a reel for "no trade"
  market updates (default: image only for those).
- `BRAND_NAME`, `BRAND_HANDLE`, `BRAND_PRIMARY_COLOR`, `BRAND_GOLD_COLOR`
  — reskin the generated image/reel.
- `REEL_MUSIC_PATH` — local path to an mp3 to use as background music.

### Generating content without a live signal

```python
from social.pipeline import run

run({
    'id': 'preview-1',
    'direction': 'BUY',
    'price': 2415.32,
    'confidence': 85,
    'targets': {'entry': 2415.32, 'stop_loss': 2405.10, 'tp1': 2420.50, 'tp2': 2425.70, 'tp3': 2430.90},
})
```

Generated files are saved to `output/` (configurable via
`SOCIAL_OUTPUT_DIR`) regardless of which channels are configured.

## Deployment

`Procfile` declares two process types:

- `worker` — the trading/social bot (`bot.py`), always needed.
- `web` — `media_server.py`, only needed if you're posting to
  Instagram (it serves `output/` publicly so Instagram's API can fetch
  the media). Skip/disable it if you're not using Instagram.

`Dockerfile` installs `fonts-dejavu-core` for the image/reel text
rendering.
