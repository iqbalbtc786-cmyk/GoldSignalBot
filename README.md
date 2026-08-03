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

### 2. Free hosting (koi hosting maujood nahi to)

Sabse aasan free option: [Railway.app](https://railway.app)

1. GitHub account se Railway par sign up karein.
2. "New Project" → "Deploy from GitHub repo" → is repo (`GoldSignalBot`)
   ko select karein.
3. Railway khud `Dockerfile`/`Procfile` detect kar ke worker start kar dega.
4. Project → Variables mein `TELEGRAM_TOKEN` aur `TELEGRAM_CHAT_ID` add
   karein, redeploy karein.
5. Logs mein "GoldSignalBot started" dikhega — bot ab live hai, har 30
   minute mein XAUUSD analyze kar ke signal bhejega.

Render.com aur ek chhota Linux VPS (DigitalOcean/Contabo) bhi isi tarah
kaam karte hain.

### 3. MetaTrader 5 (MT5) data — limitation

`MetaTrader5` Python package sirf **Windows** par, MT5 terminal ke saath
kaam karta hai — yeh Railway/Render/Docker jaisi Linux hosting par nahi
chalta. Do practical raastay hain:

- **Windows VPS** par MT5 terminal login rakh kar `MetaTrader5` package
  use karein (zyada control, lekin VPS cost aur maintenance khud dekhna
  hoga).
- **[MetaApi.cloud](https://metaapi.cloud)** jaisi cloud bridge service
  use karein — yeh MT5 account se REST/WebSocket ke zariye data deti hai,
  Linux hosting par bhi chalti hai (free tier available). Iske liye apna
  MT5 login/password/server MetaApi account mein connect karna hoga, aur
  humein sirf unka API token env variable ke through dena hoga.

Jab tak in mein se koi setup nahi hota, bot maujooda `yfinance` (Yahoo
Finance) data aur DXY bias par hi chalta rahega — yeh free hai aur
kisi extra account ki zaroorat nahi.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | Yes | BotFather se mila bot token |
| `TELEGRAM_CHAT_ID` | Yes | Jis chat/channel ko signal jayega |

## Local test

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN=xxx
export TELEGRAM_CHAT_ID=xxx
python bot.py
```
