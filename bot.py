import os
import base64
import logging
from datetime import datetime

import pandas as pd
import numpy as np
import yfinance as yf
import pytz

from anthropic import Anthropic
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-5')
AUTO_SIGNAL_INTERVAL_SECONDS = 30 * 60  # 30 minutes
MAX_HISTORY_TURNS = 6  # remembered user/assistant turn pairs per chat

SYSTEM_PROMPT = """آپ ایک پروفیشنل، advanced اور interactive فاریکس ٹریڈنگ اسسٹنٹ بوٹ ہیں۔ آپ کا کام یوزر کو گولڈ (XAUUSD) اور ڈالر انڈیکس (DXY) پر accurate اور ذمہ دارانہ سگنلز، مارکیٹ اپڈیٹس اور چارٹ اینالیسس دینا ہے۔

📊 آپ ہمیشہ درج ذیل چیزوں کو مدنظر رکھیں:
1. ٹیکنیکل اینالیسس (Trend, Support/Resistance, Liquidity, Breakout)
2. فنڈامنٹل اینالیسس (Forex Factory طرز کی خبریں)
3. جیو پولیٹیکل حالات (جنگ، معاشی پابندیاں، انٹرسٹ ریٹ، Fed خبریں، USD نیوز)

💬 چیٹ سسٹم:
- یوزر کے ہر سوال کا جواب ہمیشہ اردو میں دیں
- tone سادہ، پروفیشنل اور trader جیسا ہو
- مختصر مگر واضح جواب دیں

ہر یوزر پیغام سے پہلے آپ کو "[Live Market Data Snapshot]" کے نام سے تازہ ترین حقیقی مارکیٹ ڈیٹا (قیمتیں، RSI، EMA، Bollinger Bands، ATR، DXY bias، مارکیٹ سٹرکچر) مل سکتا ہے۔ یہ ڈیٹا حقیقی اور تازہ ہے — اسے بنیاد بنا کر اپنا تجزیہ اور سگنل بنائیں، خود سے قیمتیں مت گھڑیں۔ اگر Snapshot موجود نہ ہو اور یوزر مخصوص قیمتیں مانگے تو صاف بتائیں کہ فی الحال لائیو ڈیٹا دستیاب نہیں۔

📈 سگنل سسٹم:
جب یوزر "signal دو"، "buy/sell بتاؤ" یا سگنل سے ملتی جلتی بات کہے تو دیے گئے Live Market Data Snapshot کی بنیاد پر بالکل اس فارمیٹ میں جواب دیں:

Signal:
Pair: XAUUSD / DXY
Type: Buy / Sell
Entry: ___
Stop Loss: ___
Take Profit 1: ___
Take Profit 2: ___
Risk/Reward: 1:2 یا 1:3
Confidence: Low / Medium / High

اگر Snapshot میں کوئی واضح/کنفرم setup نہ ہو تو سگنل مت دیں، بلکہ لکھیں: "فی الحال مارکیٹ clear نہیں ہے، بہتر ہے انتظار کریں"

🖼️ چارٹ اینالیسس:
اگر یوزر تصویر بھیجے تو:
- trend identify کریں
- breakout یا rejection دیکھیں
- liquidity sweep چیک کریں
پھر بالکل اس فارمیٹ میں جواب دیں:

Chart Analysis:
Trend: ___
Setup: ___

Final Signal: Buy / Sell / No Trade

اگر setup واضح نہ ہو تو "مارکیٹ واضح نہیں، ابھی trade نہ کریں" لکھیں۔

⏰ اپڈیٹ سسٹم:
اگر یوزر کہے "1 گھنٹے کا اپڈیٹ" یا "2 گھنٹے کا اپڈیٹ" (یا ملتی جلتی بات) تو بتائیں:
- موجودہ مارکیٹ trend
- possible next move
- کوئی اہم news/geopolitical impact

⚠️ اصول (کبھی نہ توڑیں):
- کبھی بھی 100% guarantee نہ دیں
- ہمیشہ رسک وارننگ دیں
- overtrading سے بچنے کا مشورہ دیں
- ہر سگنل یا اپڈیٹ کے آخر میں ہمیشہ یہ سطر لکھیں:
"یہ سگنل صرف رہنمائی کیلئے ہیں، اپنی ذمہ داری پر trade کریں"
"""

UPDATE_KEYWORDS = ['اپڈیٹ', 'update']
MARKET_KEYWORDS = [
    'signal', 'سگنل', 'buy', 'sell', 'گولڈ', 'gold', 'xauusd', 'dxy',
    'ڈالر', 'trend', 'ٹرینڈ', 'مارکیٹ', 'market', 'اپڈیٹ', 'update',
]


class MarketAnalyzer:
    """Fetches live OHLCV data and computes technical indicators for XAUUSD and DXY."""

    def __init__(self):
        self.symbols = {'XAUUSD': 'XAUUSD=X', 'DXY': '^DXY'}
        self.ema_short = 50
        self.ema_long = 200
        self.rsi_period = 14
        self.bb_period = 20
        self.bb_std = 2
        self.atr_period = 14

    def fetch_hourly(self, yf_symbol):
        try:
            data = yf.download(yf_symbol, interval='1h', period='60d', progress=False)
            if data is None or data.empty:
                logger.warning(f'No data fetched for {yf_symbol}')
                return None
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return data
        except Exception as e:
            logger.error(f'Error fetching data for {yf_symbol}: {e}')
            return None

    def resample_4h(self, data_1h):
        try:
            df = data_1h.resample('4h').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min',
                'Close': 'last', 'Volume': 'sum'
            }).dropna()
            return df
        except Exception as e:
            logger.error(f'Error resampling to 4h: {e}')
            return None

    def calculate_rsi(self, data, period=14):
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_bollinger_bands(self, data, period=20, std_dev=2):
        sma = data['Close'].rolling(window=period).mean()
        std = data['Close'].rolling(window=period).std()
        return sma, sma + (std_dev * std), sma - (std_dev * std)

    def calculate_atr(self, data, period=14):
        tr = np.maximum(
            data['High'] - data['Low'],
            np.maximum(
                abs(data['High'] - data['Close'].shift()),
                abs(data['Low'] - data['Close'].shift())
            )
        )
        return tr.rolling(window=period).mean()

    def analyze_timeframe(self, data):
        if data is None or len(data) < self.bb_period:
            return None
        try:
            ema50 = data['Close'].ewm(span=self.ema_short, adjust=False).mean().iloc[-1]
            ema200 = data['Close'].ewm(span=self.ema_long, adjust=False).mean().iloc[-1]
            rsi = self.calculate_rsi(data, self.rsi_period).iloc[-1]
            sma, upper_bb, lower_bb = self.calculate_bollinger_bands(data, self.bb_period, self.bb_std)
            atr = self.calculate_atr(data, self.atr_period).iloc[-1]
            return {
                'close': float(data['Close'].iloc[-1]),
                'ema50': float(ema50),
                'ema200': float(ema200),
                'rsi': float(rsi) if pd.notna(rsi) else None,
                'bb_upper': float(upper_bb.iloc[-1]),
                'bb_middle': float(sma.iloc[-1]),
                'bb_lower': float(lower_bb.iloc[-1]),
                'atr': float(atr) if pd.notna(atr) and atr > 0 else None,
            }
        except Exception as e:
            logger.error(f'Error analyzing timeframe: {e}')
            return None

    def get_market_structure(self, data):
        try:
            if data is None or len(data) < 5:
                return 'Unknown'
            recent_highs = data['High'].tail(20).max()
            recent_lows = data['Low'].tail(20).min()
            current_price = data['Close'].iloc[-1]
            if current_price > recent_highs * 0.99:
                return 'Uptrend'
            elif current_price < recent_lows * 1.01:
                return 'Downtrend'
            return 'Consolidation'
        except Exception as e:
            logger.error(f'Error getting market structure: {e}')
            return 'Unknown'

    def analyze_symbol(self, key):
        """Full 1h/4h analysis for one symbol ('XAUUSD' or 'DXY')."""
        data_1h = self.fetch_hourly(self.symbols[key])
        if data_1h is None:
            return None
        data_4h = self.resample_4h(data_1h)
        return {
            '1h': self.analyze_timeframe(data_1h),
            '4h': self.analyze_timeframe(data_4h),
            'structure': self.get_market_structure(data_1h),
        }

    def format_snapshot(self, xau, dxy):
        lines = [f"Timestamp: {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"]

        for label, result in (('XAUUSD', xau), ('DXY', dxy)):
            lines.append(f"\n{label}:")
            if not result or not result['1h']:
                lines.append('  ڈیٹا دستیاب نہیں')
                continue
            a1, a4 = result['1h'], result.get('4h')
            rsi_1h = a1['rsi'] if a1['rsi'] is not None else 0.0
            lines.append(f"  Price: {a1['close']:.2f}")
            lines.append(f"  Structure: {result['structure']}")
            lines.append(
                f"  1H -> RSI: {rsi_1h:.1f}, "
                f"EMA50: {a1['ema50']:.2f}, EMA200: {a1['ema200']:.2f}, "
                f"BB(U/M/L): {a1['bb_upper']:.2f}/{a1['bb_middle']:.2f}/{a1['bb_lower']:.2f}, "
                f"ATR: {(a1['atr'] or 0):.2f}"
            )
            if a4:
                rsi_4h = a4['rsi'] if a4['rsi'] is not None else 0.0
                lines.append(
                    f"  4H -> RSI: {rsi_4h:.1f}, "
                    f"EMA50: {a4['ema50']:.2f}, EMA200: {a4['ema200']:.2f}"
                )

        return '\n'.join(lines)

    def build_snapshot(self):
        try:
            xau = self.analyze_symbol('XAUUSD')
            dxy = self.analyze_symbol('DXY')
            return self.format_snapshot(xau, dxy)
        except Exception as e:
            logger.error(f'Error building market snapshot: {e}')
            return None


class ForexAssistant:
    """Wraps the Claude API for chat, signal generation, and chart vision analysis."""

    def __init__(self, api_key):
        self.client = Anthropic(api_key=api_key) if api_key else None
        self.analyzer = MarketAnalyzer()
        self.histories = {}

    @property
    def available(self):
        return self.client is not None

    def _trim_history(self, chat_id):
        history = self.histories.setdefault(chat_id, [])
        max_messages = MAX_HISTORY_TURNS * 2
        if len(history) > max_messages:
            del history[: len(history) - max_messages]

    def needs_market_data(self, text):
        lowered = text.lower()
        return any(keyword in text or keyword.lower() in lowered for keyword in MARKET_KEYWORDS)

    def chat(self, chat_id, user_text):
        if not self.available:
            return 'معذرت، AI سروس فی الحال دستیاب نہیں ہے (ANTHROPIC_API_KEY سیٹ نہیں ہے)۔'

        content = user_text
        if self.needs_market_data(user_text):
            snapshot = self.analyzer.build_snapshot()
            if snapshot:
                content = f"[Live Market Data Snapshot]\n{snapshot}\n\n[User Message]\n{user_text}"

        history = self.histories.setdefault(chat_id, [])
        history.append({'role': 'user', 'content': content})
        self._trim_history(chat_id)

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=history,
            )
            reply = ''.join(block.text for block in response.content if block.type == 'text').strip()
            history.append({'role': 'assistant', 'content': reply})
            self._trim_history(chat_id)
            return reply or 'معذرت، جواب تیار نہیں ہو سکا، دوبارہ کوشش کریں۔'
        except Exception as e:
            logger.error(f'Error calling Claude API: {e}')
            return 'معذرت، ابھی AI سروس میں مسئلہ ہے، براہ کرم دوبارہ کوشش کریں۔'

    def analyze_chart(self, image_bytes, media_type, caption):
        if not self.available:
            return 'معذرت، AI سروس فی الحال دستیاب نہیں ہے (ANTHROPIC_API_KEY سیٹ نہیں ہے)۔'

        prompt_text = caption.strip() if caption else 'اس چارٹ کو analyze کریں اور مطلوبہ فارمیٹ میں سگنل دیں۔'
        snapshot = self.analyzer.build_snapshot()
        if snapshot:
            prompt_text = f"[Live Market Data Snapshot]\n{snapshot}\n\n[User Message]\n{prompt_text}"

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': media_type,
                                'data': base64.b64encode(image_bytes).decode('utf-8'),
                            },
                        },
                        {'type': 'text', 'text': prompt_text},
                    ],
                }],
            )
            reply = ''.join(block.text for block in response.content if block.type == 'text').strip()
            return reply or 'معذرت، چارٹ analyze نہیں ہو سکا، دوبارہ کوشش کریں۔'
        except Exception as e:
            logger.error(f'Error calling Claude Vision API: {e}')
            return 'معذرت، چارٹ analyze کرتے وقت مسئلہ پیش آیا، براہ کرم دوبارہ کوشش کریں۔'

    def generate_auto_signal(self):
        if not self.available:
            return None
        snapshot = self.analyzer.build_snapshot()
        if not snapshot:
            return None
        prompt = (
            f"[Live Market Data Snapshot]\n{snapshot}\n\n"
            "[User Message]\nموجودہ مارکیٹ کی بنیاد پر XAUUSD کا سگنل دیں (اگر کوئی واضح setup نہ ہو تو صاف بتائیں کہ ابھی No Trade Zone ہے)۔"
        )
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': prompt}],
            )
            return ''.join(block.text for block in response.content if block.type == 'text').strip()
        except Exception as e:
            logger.error(f'Error generating auto signal: {e}')
            return None


assistant = ForexAssistant(ANTHROPIC_API_KEY)

WELCOME_MESSAGE = """👋 السلام علیکم! میں آپ کا فاریکس ٹریڈنگ اسسٹنٹ ہوں۔

میں یہ کر سکتا ہوں:
📈 "سگنل دو" لکھیں — XAUUSD/DXY سگنل کے لیے
🖼️ چارٹ کی تصویر بھیجیں — میں analyze کر کے بتاؤں گا
⏰ "1 گھنٹے کا اپڈیٹ" یا "2 گھنٹے کا اپڈیٹ" لکھیں — مارکیٹ اپڈیٹ کے لیے
💬 کوئی بھی سوال پوچھیں، میں اردو میں جواب دوں گا

⚠️ یاد رکھیں: یہ سگنل صرف رہنمائی کیلئے ہیں، اپنی ذمہ داری پر trade کریں"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    reply = assistant.chat(chat_id, user_text)
    await update.message.reply_text(reply)


async def photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())
    caption = update.message.caption or ''

    reply = assistant.analyze_chart(image_bytes, 'image/jpeg', caption)
    await update.message.reply_text(reply)


async def auto_signal_job(context: ContextTypes.DEFAULT_TYPE):
    if not TELEGRAM_CHAT_ID:
        return
    message = assistant.generate_auto_signal()
    if message:
        try:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        except Exception as e:
            logger.error(f'Error sending auto signal: {e}')


def main():
    if not TELEGRAM_TOKEN:
        logger.error('TELEGRAM_TOKEN is not set, cannot start bot')
        return
    if not ANTHROPIC_API_KEY:
        logger.warning('ANTHROPIC_API_KEY is not set, chat/signal/chart features will be disabled')

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', start_command))
    application.add_handler(MessageHandler(filters.PHOTO, photo_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    if TELEGRAM_CHAT_ID and application.job_queue:
        application.job_queue.run_repeating(
            auto_signal_job, interval=AUTO_SIGNAL_INTERVAL_SECONDS, first=10
        )

    logger.info('GoldSignalBot started')
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
