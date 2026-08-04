# 🤖 GoldSignalBot (@gold_signal_pk_bot)

یہ ایک Telegram bot ہے جو Gold (XAUUSD) پر خالصتاً ٹیکنیکل انڈیکیٹرز (EMA, RSI, Bollinger Bands, ATR) اور DXY bias کی بنیاد پر سگنلز اور مارکیٹ اپڈیٹس اردو میں دیتا ہے۔ کوئی AI/LLM استعمال نہیں ہوتا — تمام جوابات rule-based تکنیکی تجزیے سے generate ہوتے ہیں۔

---

## ⚙️ Setup Instructions

### 1️⃣ BotFather سے Telegram Token حاصل کریں
- Telegram میں `@BotFather` کھولیں
- `/newbot` کمانڈ دیں اور ہدایات کے مطابق اپنا bot بنائیں (مثلاً `gold_signal_pk_bot`)
- آپ کو ملنے والا token ہی `TELEGRAM_TOKEN` ہے

### 2️⃣ Environment Variables سیٹ کریں

| Variable | تفصیل |
|---|---|
| `TELEGRAM_TOKEN` | BotFather سے ملا ہوا token (لازمی) |
| `TELEGRAM_CHAT_ID` | ہر 30 منٹ بعد خودکار سگنل بھیجنے کے لیے (اختیاری) |

### 3️⃣ Bot چلائیں

**مقامی طور پر (لوکل/VPS/Replit):**
```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN=آپکا_ٹیلیگرام_ٹوکن
export TELEGRAM_CHAT_ID=آپکا_چیٹ_ID   # اختیاری
python bot.py
```

**Docker کے ذریعے:**
```bash
docker build -t gold-signal-bot .
docker run -e TELEGRAM_TOKEN=... -e TELEGRAM_CHAT_ID=... gold-signal-bot
```

**Heroku/Railway جیسی worker-based hosting:** ریپو میں موجود `Procfile` (`worker: python bot.py`) خودکار طور پر استعمال ہوگا، بس اوپر دیے گئے environment variables سیٹ کریں۔

---

## 💬 Available Commands

| Command | تفصیل |
|---|---|
| `/start`, `/help` | bot کا تعارف اور استعمال کا طریقہ |
| `/signal` | موجودہ تکنیکی تجزیے کی بنیاد پر XAUUSD سگنل (Buy/Sell/No Trade Zone)، اعتماد کی سطح اور وجہ سمیت |
| `/1h` | 1 گھنٹے کا مارکیٹ اپڈیٹ |
| `/2h` | 2 گھنٹے کا مارکیٹ اپڈیٹ |

> نوٹ: `/1h` اور `/2h` ہندسے سے شروع ہوتے ہیں اس لیے یہ Telegram کے command-menu (autocomplete) میں نظر نہیں آئیں گے، لیکن ٹائپ کر کے بھیجنے پر معمول کے مطابق کام کریں گے۔ چونکہ کوئی پیشگوئی ماڈل استعمال نہیں ہوتا، `/1h` اور `/2h` دونوں موجودہ تکنیکی صورتحال کا ایک ہی جائزہ دیتے ہیں (رجحان، RSI، DXY bias، ممکنہ اگلا رخ) — یہ کسی الگ "1 گھنٹے بمقابلہ 2 گھنٹے" پیشگوئی کی نمائندگی نہیں کرتے۔

---

## 🧠 یہ بوٹ کیسے کام کرتا ہے

1. `GoldSignalBot.run_analysis()` yfinance سے XAUUSD کا 1H ڈیٹا لیتا ہے اور اسی سے 4H کینڈلز resample کرتا ہے (yfinance میں native `4h` انٹرول موجود نہیں)۔
2. دونوں ٹائم فریمز پر EMA(50/200)، RSI، Bollinger Bands اور ATR calculate ہوتے ہیں، ساتھ ہی DXY کا bias (1H ڈیٹا سے) اور مارکیٹ سٹرکچر (Uptrend/Downtrend/Consolidation)۔
3. `calculate_confidence()` انہی انڈیکیٹرز پر پوائنٹ بیسڈ سکورنگ کرتا ہے (0-100%) اور ہر شامل ہونے والے پوائنٹ کے ساتھ اردو میں وجہ (reason) بھی ریکارڈ کرتا ہے۔
4. سکور کو Low/Medium/High میں لیبل کیا جاتا ہے؛ 70%+ پر ہی Buy/Sell سگنل (Entry/SL/TP1-3/RR) دکھایا جاتا ہے، ورنہ "No Trade Zone" پیغام۔
5. `TELEGRAM_CHAT_ID` سیٹ ہونے کی صورت میں ہر 30 منٹ بعد ایک background job خودکار طور پر یہی تجزیہ چلا کر سگنل اسی چیٹ پر بھیجتا رہتا ہے۔

---

## ⚠️ نوٹ
- یہ bot صرف رہنمائی کے لیے ہے، مالیاتی مشورہ نہیں
- کبھی بھی 100% accuracy کی guarantee نہیں دی جاتی
- ہمیشہ اپنے رسک مینجمنٹ کے ساتھ خود ذمہ داری پر trade کریں

---

## 📌 Bot Username
[@gold_signal_pk_bot](https://t.me/gold_signal_pk_bot)
