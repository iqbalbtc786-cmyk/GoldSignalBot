# 🤖 Forex Trading Assistant Bot (@gold_signal_pk_bot)

یہ ایک انٹرایکٹو Telegram bot ہے جو Gold (XAUUSD) اور Dollar Index (DXY) پر لائیو ٹیکنیکل ڈیٹا کی بنیاد پر سگنلز اور مارکیٹ اپڈیٹس دیتا ہے، چارٹ کی تصاویر analyze کرتا ہے، اور Claude AI کے ذریعے اردو میں trader جیسے انداز میں جواب دیتا ہے۔

---

## ⚙️ Setup Instructions

### 1️⃣ BotFather سے Telegram Token حاصل کریں
- Telegram میں `@BotFather` کھولیں
- `/newbot` کمانڈ دیں اور ہدایات کے مطابق اپنا bot بنائیں (مثلاً `gold_signal_pk_bot`)
- آپ کو ملنے والا token ہی `TELEGRAM_TOKEN` ہے

### 2️⃣ Claude API Key حاصل کریں
- [console.anthropic.com](https://console.anthropic.com) پر account بنائیں
- ایک API key generate کریں
- یہ `ANTHROPIC_API_KEY` ہوگی

### 3️⃣ Environment Variables سیٹ کریں

| Variable | تفصیل |
|---|---|
| `TELEGRAM_TOKEN` | BotFather سے ملا ہوا token (لازمی) |
| `ANTHROPIC_API_KEY` | Claude API key — چیٹ، سگنل اور چارٹ analysis کے لیے لازمی |
| `TELEGRAM_CHAT_ID` | ہر 30 منٹ بعد خودکار سگنل بھیجنے کے لیے (اختیاری) |
| `CLAUDE_MODEL` | استعمال ہونے والا Claude model (اختیاری، ڈیفالٹ: `claude-sonnet-5`) |

### 4️⃣ Bot چلائیں

**مقامی طور پر (لوکل/VPS/Replit):**
```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN=آپکا_ٹیلیگرام_ٹوکن
export ANTHROPIC_API_KEY=آپکی_Claude_API_Key
export TELEGRAM_CHAT_ID=آپکا_چیٹ_ID   # اختیاری
python bot.py
```

**Docker کے ذریعے:**
```bash
docker build -t gold-signal-bot .
docker run -e TELEGRAM_TOKEN=... -e ANTHROPIC_API_KEY=... -e TELEGRAM_CHAT_ID=... gold-signal-bot
```

**Heroku/Railway جیسی worker-based hosting:** ریپو میں موجود `Procfile` (`worker: python bot.py`) خودکار طور پر استعمال ہوگا، بس اوپر دیے گئے environment variables سیٹ کریں۔

---

## 💬 Available Commands

| Command | تفصیل |
|---|---|
| `/start`, `/help` | bot کا تعارف اور استعمال کا طریقہ |
| `/signal` | فوری XAUUSD/DXY سگنل حاصل کریں |
| `/update` | موجودہ مارکیٹ اپڈیٹ دیکھیں |
| `/1h` | 1 گھنٹے کا مارکیٹ اپڈیٹ |
| `/2h` | 2 گھنٹے کا مارکیٹ اپڈیٹ |

اس کے علاوہ آپ عام زبان میں بھی بات کر سکتے ہیں — جیسے "سگنل دو"، "1 گھنٹے کا اپڈیٹ بتاؤ" — اور چارٹ کی تصویر بھیج کر تجزیہ منگوا سکتے ہیں۔

> نوٹ: `/1h` اور `/2h` ہندسے سے شروع ہوتے ہیں اس لیے یہ Telegram کے command-menu (autocomplete) میں نظر نہیں آئیں گے، لیکن ٹائپ کر کے بھیجنے پر معمول کے مطابق کام کریں گے۔

---

## 🧠 یہ بوٹ کیسے کام کرتا ہے

1. `MarketAnalyzer` کلاس yfinance سے XAUUSD اور DXY کا 1H/4H ڈیٹا لے کر EMA(50/200)، RSI، Bollinger Bands، ATR اور مارکیٹ سٹرکچر calculate کرتی ہے۔
2. جب بھی پیغام سگنل/اپڈیٹ سے متعلق ہو، یہ لائیو ڈیٹا ایک "Market Data Snapshot" کے طور پر Claude کو بھیجا جاتا ہے تاکہ جواب حقیقی نمبروں پر مبنی ہو۔
3. `ForexAssistant` کلاس اردو trading-persona سسٹم پرامپٹ کے ساتھ Claude کو کال کرتی ہے — چیٹ، سگنل جنریشن، اور چارٹ امیج کے لیے Claude Vision۔
4. `TELEGRAM_CHAT_ID` سیٹ ہونے کی صورت میں ہر 30 منٹ بعد ایک background job خودکار XAUUSD سگنل اسی چیٹ پر بھیجتا رہتا ہے۔

---

## ⚠️ نوٹ
- یہ bot صرف رہنمائی کے لیے ہے، مالیاتی مشورہ نہیں
- کبھی بھی 100% accuracy کی guarantee نہیں دی جاتی
- ہمیشہ اپنے رسک مینجمنٹ کے ساتھ خود ذمہ داری پر trade کریں

---

## 📌 Bot Username
[@gold_signal_pk_bot](https://t.me/gold_signal_pk_bot)
