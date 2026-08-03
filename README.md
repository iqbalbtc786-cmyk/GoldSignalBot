# Gold Signal Bot (XAUUSD)

Telegram bot that analyzes XAUUSD (Gold) using EMA/RSI/Bollinger Bands/ATR
across multiple timeframes, combines it with DXY (US Dollar Index) bias,
and sends BUY/SELL signals with entry, stop loss and take-profit levels
to a Telegram chat.

## Bot ko live activate karne ke liye zaroori cheezein

Yeh code khud se hamesha chalta nahi rehta — isay kisi hosting par
deploy karna hoga jo `python bot.py` ko 24/7 chalati rahe.

### 1. Telegram Bot Token aur Chat ID lena

1. Telegram par `@BotFather` ko message karein, `/newbot` ya apne existing
   bot (`@GoldDXYSignalBot`) ka token lein.
2. Apne bot ko jis chat/channel par signal bhejne hain, wahan add karein.
3. Chat ID nikalne ke liye us chat mein ek message bhejein, phir yeh URL
   browser mein khol kar `chat.id` dekhein:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`

**In dono values ko kabhi bhi chat/message mein paste na karein** — yeh
secrets hain. Inhe seedha apne hosting platform ke Environment Variables
mein `TELEGRAM_TOKEN` aur `TELEGRAM_CHAT_ID` ke naam se set karein.

### 2. Hosting options (koi hosting maujood nahi to)

Bot ek chhota "worker" hai (koi website/UI nahi), isliye background-worker
hosting chahiye jo `python bot.py` ko 24/7 chalati rahe:

| Platform | Free tier | Notes |
|---|---|---|
| **Railway.app** | Haan (trial credit) | Sabse aasan, GitHub se ek-click deploy, `Dockerfile`/`Procfile` khud detect karta hai |
| **Render.com** | Background worker free nahi (2025 se), Web Service free hai | Free rakhne ke liye chhoti tabdeeli chahiye (health-check endpoint) |
| **Fly.io** | Chhota free allowance | Thoda zyada CLI/technical setup |
| **PythonAnywhere** | Free "Always-on task" nahi milta free plan mein | Paid plan chahiye |
| **Apna VPS** (DigitalOcean/Contabo/Hetzner) | Nahi, ~$4-6/month | Poora control, `systemd`/`Docker` se chalayein |

**Recommendation:** Railway.app se shuru karein (steps neeche) — sabse
kam setup, aur GitHub repo already ready hai.

1. GitHub account se Railway par sign up karein.
2. "New Project" → "Deploy from GitHub repo" → is repo (`GoldSignalBot`)
   ko select karein.
3. Railway khud `Dockerfile`/`Procfile` detect kar ke worker start kar dega.
4. Project → Variables mein neeche di gayi env variables add karein,
   redeploy karein.
5. Logs mein "GoldSignalBot started" dikhega, aur aapke Telegram group
   mein turant "🟢 Gold Signal Bot is now LIVE" welcome message aa
   jayega — har baar jab bot start/restart hota hai yeh message bhejta
   hai.

### 3. Apna Exness MT5 account link karna (optional, behtar accuracy)

Aapka Exness account (`#472155889`, MT5, Standard) seedha is bot se
connect nahi ho sakta kyunki `MetaTrader5` Python package sirf
**Windows** par, MT5 terminal ke saath kaam karta hai — Railway/Render
jaisi Linux hosting is par nahi chalti.

Iska hal — **[MetaApi.cloud](https://metaapi.cloud)** (cloud bridge,
free tier maujood hai):

1. MetaApi.cloud par sign up karein.
2. Dashboard mein apna Exness MT5 account add karein (login `472155889`,
   password, server — yeh sirf MetaApi ke apne dashboard mein daalein,
   kisi aur ko na dein).
3. MetaApi account ko "deploy" karein, uska **Account ID** copy karein.
4. Apna **API token** generate karein (Dashboard → API keys).
5. In dono ko hosting platform (Railway) ke Environment Variables mein
   set karein:
   - `METAAPI_TOKEN`
   - `METAAPI_ACCOUNT_ID`
   - `METAAPI_SYMBOL` (default `XAUUSD` — apne Exness account mein gold
     ka exact symbol name check kar lein, kabhi `XAUUSDm` ya `GOLD` bhi
     hota hai)

Bot khud detect kar lega ke yeh variables set hain aur automatically
Exness ke real price feed par switch ho jayega (agar MetaApi se data na
milay to us cycle ke liye Yahoo Finance par fallback kar dega, taake
bot kabhi crash na ho).

Jab tak yeh setup nahi karte, bot `yfinance` (Yahoo Finance) data aur
DXY bias par hi chalta rahega — yeh free hai aur kisi extra account ki
zaroorat nahi.

### 4. Bot se chat karna (on-demand signal + chart screenshot analysis)

Bot ab sirf har 30 minute wali scheduled alerts hi nahi bhejta — aap
usay seedha message bhi kar saktay hain:

- Koi bhi message (`/signal`, "market update do", ya sirf "hi") bhejein
  → bot turant current XAUUSD analysis nikaal kar reply karega, chahe
  confidence threshold se kam ho.
- Kisi gold/XAUUSD chart ka **screenshot bhej dein** → bot Claude
  (Anthropic) ke vision model se us chart ko "dekh" kar trend,
  support/resistance aur ek tentative BUY/SELL/NEUTRAL read de dega.

Chart-screenshot feature ke liye ek extra env variable chahiye:

1. [console.anthropic.com](https://console.anthropic.com) par account
   banayein, ek **API key** generate karein.
2. Hosting platform (Railway) ke Environment Variables mein add karein:
   - `ANTHROPIC_API_KEY`

Agar yeh set nahi hai, bot bina crash huay chal raha hai — bas photo
bhejne par bot bata dega ke yeh feature abhi configure nahi hai. Text
messages (`/signal`) ke liye yeh key zaroori nahi.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | Yes | BotFather se mila bot token |
| `TELEGRAM_CHAT_ID` | Yes | Jis chat/channel ko scheduled signal jayega |
| `METAAPI_TOKEN` | Optional | MetaApi.cloud API token (Exness/MT5 real feed ke liye) |
| `METAAPI_ACCOUNT_ID` | Optional | MetaApi mein deploy kiye gaye Exness account ka ID |
| `METAAPI_REGION` | Optional | MetaApi region (default `new-york`) |
| `METAAPI_SYMBOL` | Optional | Broker par gold ka symbol name (default `XAUUSD`) |
| `ANTHROPIC_API_KEY` | Optional | Chart-screenshot analysis ke liye (console.anthropic.com) |

## Local test

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN=xxx
export TELEGRAM_CHAT_ID=xxx
python bot.py
```
