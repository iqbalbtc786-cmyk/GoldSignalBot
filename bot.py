import os
import logging
from datetime import datetime

import pandas as pd
import numpy as np
import yfinance as yf
import pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
CONFIDENCE_THRESHOLD = 70
SIGNAL_CHECK_INTERVAL_SECONDS = 30 * 60  # 30 minutes

DISCLAIMER = 'یہ سگنل صرف رہنمائی کیلئے ہیں، اپنی ذمہ داری پر trade کریں'


class GoldSignalBot:
    def __init__(self):
        self.symbol = 'XAUUSD=X'
        self.dxy_symbol = '^DXY'
        self.ema_short = 50
        self.ema_long = 200
        self.rsi_period = 14
        self.bb_period = 20
        self.bb_std = 2
        self.atr_period = 14
        self.confidence_threshold = CONFIDENCE_THRESHOLD

        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning('Telegram credentials not configured')

    def fetch_data(self, symbol, interval, period):
        """Fetch OHLCV data from yfinance"""
        try:
            data = yf.download(symbol, interval=interval, period=period, progress=False)
            if data is None or data.empty:
                logger.warning(f'No data fetched for {symbol} {interval}')
                return None
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return data
        except Exception as e:
            logger.error(f'Error fetching data for {symbol}: {e}')
            return None

    def resample_4h(self, data_1h):
        """Build 4H candles from 1H data (yfinance has no native '4h' interval)"""
        try:
            if data_1h is None:
                return None
            data_4h = data_1h.resample('4h').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min',
                'Close': 'last', 'Volume': 'sum'
            }).dropna()
            return data_4h
        except Exception as e:
            logger.error(f'Error resampling to 4h: {e}')
            return None

    def calculate_ema(self, data, period):
        """Calculate Exponential Moving Average"""
        return data['Close'].ewm(span=period, adjust=False).mean()

    def calculate_rsi(self, data, period=14):
        """Calculate Relative Strength Index"""
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_bollinger_bands(self, data, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        sma = data['Close'].rolling(window=period).mean()
        std = data['Close'].rolling(window=period).std()
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        return sma, upper_band, lower_band

    def calculate_atr(self, data, period=14):
        """Calculate Average True Range"""
        data['TR'] = np.maximum(
            data['High'] - data['Low'],
            np.maximum(
                abs(data['High'] - data['Close'].shift()),
                abs(data['Low'] - data['Close'].shift())
            )
        )
        atr = data['TR'].rolling(window=period).mean()
        return atr

    def analyze_timeframe(self, data):
        """Analyze single timeframe"""
        if data is None or len(data) < self.bb_period:
            return None

        try:
            current_close = data['Close'].iloc[-1]

            # Calculate indicators
            ema50 = self.calculate_ema(data, self.ema_short).iloc[-1]
            ema200 = self.calculate_ema(data, self.ema_long).iloc[-1]
            rsi = self.calculate_rsi(data, self.rsi_period).iloc[-1]
            sma, upper_bb, lower_bb = self.calculate_bollinger_bands(data, self.bb_period, self.bb_std)
            atr = self.calculate_atr(data, self.atr_period).iloc[-1]

            sma_current = sma.iloc[-1]
            upper_bb_current = upper_bb.iloc[-1]
            lower_bb_current = lower_bb.iloc[-1]

            analysis = {
                'close': current_close,
                'ema50': ema50,
                'ema200': ema200,
                'rsi': rsi,
                'bb_upper': upper_bb_current,
                'bb_middle': sma_current,
                'bb_lower': lower_bb_current,
                'atr': atr
            }

            return analysis
        except Exception as e:
            logger.error(f'Error analyzing timeframe: {e}')
            return None

    def get_dxy_bias(self):
        """Get DXY bias and correlation with gold"""
        try:
            dxy_data = self.fetch_data(self.dxy_symbol, '1h', '7d')
            if dxy_data is None or len(dxy_data) < 2:
                return None, 'Unknown'

            current_dxy = dxy_data['Close'].iloc[-1]
            prev_dxy = dxy_data['Close'].iloc[-2]
            dxy_change = current_dxy - prev_dxy

            if dxy_change > 0:
                bias = 'SELL'  # DXY up = Gold down
                dxy_direction = 'UP'
            else:
                bias = 'BUY'   # DXY down = Gold up
                dxy_direction = 'DOWN'

            return bias, dxy_direction
        except Exception as e:
            logger.error(f'Error getting DXY bias: {e}')
            return None, 'Unknown'

    def calculate_confidence(self, analysis_1h, analysis_4h, dxy_bias):
        """Calculate overall signal confidence, along with the Urdu reasons behind it"""
        if not analysis_1h or not analysis_4h:
            return 0, 'NEUTRAL', []

        confidence_score = 0
        signal_direction = None
        reasons = []

        try:
            # EMA trend analysis
            ema_buy_1h = analysis_1h['close'] > analysis_1h['ema50'] > analysis_1h['ema200']
            ema_sell_1h = analysis_1h['close'] < analysis_1h['ema50'] < analysis_1h['ema200']

            ema_buy_4h = analysis_4h['close'] > analysis_4h['ema50'] > analysis_4h['ema200']
            ema_sell_4h = analysis_4h['close'] < analysis_4h['ema50'] < analysis_4h['ema200']

            # RSI analysis
            rsi_overbought_1h = analysis_1h['rsi'] > 70
            rsi_oversold_1h = analysis_1h['rsi'] < 30
            rsi_overbought_4h = analysis_4h['rsi'] > 70
            rsi_oversold_4h = analysis_4h['rsi'] < 30

            # Bollinger Bands position
            bb_upper_touch_1h = analysis_1h['close'] > analysis_1h['bb_upper'] * 0.98
            bb_lower_touch_1h = analysis_1h['close'] < analysis_1h['bb_lower'] * 1.02

            # Buy Signal Logic
            if ema_buy_1h and ema_buy_4h:
                confidence_score += 25
                signal_direction = 'BUY'
                reasons.append('1H اور 4H دونوں ٹائم فریمز میں تیزی کا EMA رجحان (قیمت > EMA50 > EMA200)')

            if ema_buy_4h and rsi_oversold_1h:
                confidence_score += 20
                signal_direction = 'BUY'
                reasons.append('4H تیزی کا رجحان اور 1H RSI اوور سولڈ زون میں (30 سے کم)')

            if bb_lower_touch_1h and analysis_1h['rsi'] < 50:
                confidence_score += 15
                signal_direction = 'BUY'
                reasons.append('قیمت لوئر بولنگر بینڈ کے قریب اور RSI 50 سے کم')

            if dxy_bias == 'BUY':
                confidence_score += 20
                reasons.append('DXY کمزور ہو رہا ہے، جو گولڈ کی خریداری کے لیے معاون ہے')

            # Sell Signal Logic
            if ema_sell_1h and ema_sell_4h:
                confidence_score += 25
                signal_direction = 'SELL'
                reasons.append('1H اور 4H دونوں ٹائم فریمز میں مندی کا EMA رجحان (قیمت < EMA50 < EMA200)')

            if ema_sell_4h and rsi_overbought_1h:
                confidence_score += 20
                signal_direction = 'SELL'
                reasons.append('4H مندی کا رجحان اور 1H RSI اوور بوٹ زون میں (70 سے زیادہ)')

            if bb_upper_touch_1h and analysis_1h['rsi'] > 50:
                confidence_score += 15
                signal_direction = 'SELL'
                reasons.append('قیمت اپر بولنگر بینڈ کے قریب اور RSI 50 سے زیادہ')

            if dxy_bias == 'SELL':
                confidence_score += 20
                reasons.append('DXY مضبوط ہو رہا ہے، جو گولڈ پر دباؤ ڈال رہا ہے')

            # Normalize confidence to 100
            confidence_score = min(confidence_score, 100)

            # No clear signal
            if signal_direction is None:
                confidence_score = 0
                signal_direction = 'NEUTRAL'
                reasons = ['فی الحال کوئی واضح تکنیکی سیٹ اپ کنفرم نہیں ہو رہا']

            return confidence_score, signal_direction, reasons

        except Exception as e:
            logger.error(f'Error calculating confidence: {e}')
            return 0, 'NEUTRAL', []

    def calculate_targets_and_stops(self, current_price, direction, atr):
        """Calculate entry, stop loss, and take profit levels"""
        try:
            if atr <= 0:
                atr = current_price * 0.001  # Default 0.1% if ATR is invalid

            if direction == 'BUY':
                entry = current_price
                stop_loss = current_price - (2 * atr)
                tp1 = current_price + (1 * atr)
                tp2 = current_price + (2 * atr)
                tp3 = current_price + (3 * atr)
            else:  # SELL
                entry = current_price
                stop_loss = current_price + (2 * atr)
                tp1 = current_price - (1 * atr)
                tp2 = current_price - (2 * atr)
                tp3 = current_price - (3 * atr)

            return {
                'entry': round(entry, 2),
                'stop_loss': round(stop_loss, 2),
                'tp1': round(tp1, 2),
                'tp2': round(tp2, 2),
                'tp3': round(tp3, 2)
            }
        except Exception as e:
            logger.error(f'Error calculating targets: {e}')
            return None

    def get_market_structure(self, data):
        """Determine current market structure"""
        try:
            if data is None or len(data) < 5:
                return 'Unknown'

            recent_highs = data['High'].tail(5).max()
            recent_lows = data['Low'].tail(5).min()
            current_price = data['Close'].iloc[-1]

            if current_price > recent_highs * 0.99:
                return 'Uptrend'
            elif current_price < recent_lows * 1.01:
                return 'Downtrend'
            else:
                return 'Consolidation'
        except Exception as e:
            logger.error(f'Error getting market structure: {e}')
            return 'Unknown'

    def check_news_risk(self):
        """Check for potential news risk (simplified)"""
        # In production, integrate with news API or economic calendar
        return 'Low'

    def confidence_label(self, score):
        """Translate numeric confidence into Low/Medium/High (Urdu)"""
        if score >= 70:
            return 'بلند (High)'
        elif score >= 40:
            return 'درمیانہ (Medium)'
        else:
            return 'کم (Low)'

    def compute_rr(self, entry, stop_loss, target):
        """Risk/Reward ratio for a given target, relative to the stop loss distance"""
        risk = abs(entry - stop_loss)
        if risk <= 0:
            return None
        return round(abs(target - entry) / risk, 2)

    def run_analysis(self):
        """Fetch data and run the full 1H/4H technical analysis. Returns a result dict or None."""
        try:
            data_1h = self.fetch_data(self.symbol, '1h', '30d')
            if data_1h is None:
                logger.warning('Insufficient 1H data for analysis')
                return None

            data_4h = self.resample_4h(data_1h)

            analysis_1h = self.analyze_timeframe(data_1h)
            analysis_4h = self.analyze_timeframe(data_4h)

            if analysis_1h is None or analysis_4h is None:
                logger.warning('Insufficient data for timeframe analysis')
                return None

            dxy_bias, dxy_direction = self.get_dxy_bias()
            confidence, direction, reasons = self.calculate_confidence(analysis_1h, analysis_4h, dxy_bias)
            market_structure = self.get_market_structure(data_1h)
            news_risk = self.check_news_risk()

            targets = None
            if direction != 'NEUTRAL':
                atr = analysis_1h['atr'] if analysis_1h['atr'] > 0 else analysis_1h['close'] * 0.001
                targets = self.calculate_targets_and_stops(analysis_1h['close'], direction, atr)

            return {
                'direction': direction,
                'confidence': confidence,
                'reasons': reasons,
                'analysis_1h': analysis_1h,
                'analysis_4h': analysis_4h,
                'dxy_bias': dxy_bias,
                'dxy_direction': dxy_direction,
                'market_structure': market_structure,
                'news_risk': news_risk,
                'targets': targets,
            }
        except Exception as e:
            logger.error(f'Error in run_analysis: {e}')
            return None

    def format_signal_message(self, result):
        """Urdu formatted Buy/Sell/No Trade signal message"""
        ts = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
        direction = result['direction']
        confidence = result['confidence']
        label = self.confidence_label(confidence)
        reasons_text = '\n'.join(f'• {r}' for r in result['reasons']) or '• فی الحال کوئی واضح تکنیکی سیٹ اپ کنفرم نہیں ہو رہا'

        if direction == 'NEUTRAL' or confidence < self.confidence_threshold or not result['targets']:
            return (
                f"🔔 XAUUSD سگنل\n\n"
                f"📊 نتیجہ: No Trade Zone\n"
                f"فی الحال مارکیٹ clear نہیں ہے، بہتر ہے انتظار کریں\n\n"
                f"💪 اعتماد کی سطح: {confidence}% ({label})\n\n"
                f"📋 وجہ:\n{reasons_text}\n\n"
                f"⏰ {ts}\n\n"
                f"⚠️ {DISCLAIMER}"
            )

        targets = result['targets']
        type_urdu = 'خریداری (Buy)' if direction == 'BUY' else 'فروخت (Sell)'
        rr1 = self.compute_rr(targets['entry'], targets['stop_loss'], targets['tp1'])
        rr2 = self.compute_rr(targets['entry'], targets['stop_loss'], targets['tp2'])
        rr3 = self.compute_rr(targets['entry'], targets['stop_loss'], targets['tp3'])

        return f"""🔔 سگنل: XAUUSD

📈 نوعیت: {type_urdu}
💪 اعتماد کی سطح: {label} ({confidence}%)

💰 انٹری: ${targets['entry']:.2f}
🛑 سٹاپ لاس: ${targets['stop_loss']:.2f}
🎯 ٹیک پرافٹ 1: ${targets['tp1']:.2f} (رسک/ریوارڈ 1:{rr1})
🎯 ٹیک پرافٹ 2: ${targets['tp2']:.2f} (رسک/ریوارڈ 1:{rr2})
🎯 ٹیک پرافٹ 3: ${targets['tp3']:.2f} (رسک/ریوارڈ 1:{rr3})

💱 DXY رجحان: {result['dxy_direction']} ({result['dxy_bias'] or 'Unknown'})
📊 مارکیٹ سٹرکچر: {result['market_structure']}
📍 RSI (1H): {result['analysis_1h']['rsi']:.2f}
⚠️ نیوز رسک: {result['news_risk']}

📋 وجہ:
{reasons_text}

⚠️ کبھی بھی 100% گارنٹی نہیں دی جا سکتی، ہمیشہ رسک مینجمنٹ کے ساتھ اور اوور ٹریڈنگ سے بچ کر trade کریں۔

⏰ {ts}

⚠️ {DISCLAIMER}"""

    def next_move_hint(self, result):
        """Simple rule-based hint for the likely next move, based on current structure/RSI"""
        structure = result['market_structure']
        rsi = result['analysis_1h']['rsi']

        if structure == 'Uptrend':
            if pd.notna(rsi) and rsi > 70:
                return 'اپٹرینڈ برقرار ہے مگر RSI اوور بوٹ زون میں ہے، مختصر اصلاح ممکن ہے'
            return 'اپٹرینڈ برقرار رہنے کا امکان ہے'
        elif structure == 'Downtrend':
            if pd.notna(rsi) and rsi < 30:
                return 'ڈاؤن ٹرینڈ جاری ہے مگر RSI اوور سولڈ زون میں ہے، ریورسل کا امکان ہے'
            return 'ڈاؤن ٹرینڈ برقرار رہنے کا امکان ہے'
        else:
            return 'مارکیٹ کنسولیڈیشن میں ہے، بریک آؤٹ کا انتظار بہتر ہے'

    def format_update_message(self, result, hours):
        """Urdu formatted N-hour market update"""
        ts = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
        a1, a4 = result['analysis_1h'], result['analysis_4h']
        label = self.confidence_label(result['confidence'])
        reasons_text = '\n'.join(f'• {r}' for r in result['reasons']) or '• فی الحال کوئی واضح تکنیکی سیٹ اپ کنفرم نہیں ہو رہا'

        return f"""⏰ {hours} گھنٹے کا مارکیٹ اپڈیٹ — XAUUSD

📊 موجودہ رجحان: {result['market_structure']}
💰 موجودہ قیمت: ${a1['close']:.2f}
📍 RSI (1H): {a1['rsi']:.2f} | RSI (4H): {a4['rsi']:.2f}
💱 DXY رجحان: {result['dxy_direction']} ({result['dxy_bias'] or 'Unknown'})
💪 موجودہ اعتماد کی سطح: {label} ({result['confidence']}%)

🔮 ممکنہ اگلا رخ: {self.next_move_hint(result)}

📋 وجہ:
{reasons_text}

⚠️ نوٹ: یہ موجودہ تکنیکی صورتحال پر مبنی تجزیہ ہے، مستقبل کی قیمت کی کوئی ضمانت نہیں دی جا سکتی۔

⏰ {ts}

⚠️ {DISCLAIMER}"""


bot = GoldSignalBot()

WELCOME_MESSAGE = """👋 السلام علیکم! میں GoldSignalBot ہوں — XAUUSD ٹیکنیکل سگنل اسسٹنٹ۔

میں یہ کر سکتا ہوں:
📈 /signal — موجودہ تکنیکی تجزیے کی بنیاد پر XAUUSD سگنل
⏰ /1h — 1 گھنٹے کا مارکیٹ اپڈیٹ
⏰ /2h — 2 گھنٹے کا مارکیٹ اپڈیٹ

⚠️ یہ تجزیہ صرف EMA/RSI/Bollinger Bands/ATR جیسے تکنیکی اشاریوں پر مبنی ہے۔
⚠️ یاد رکھیں: یہ سگنل صرف رہنمائی کیلئے ہیں، اپنی ذمہ داری پر trade کریں"""

DATA_ERROR_MESSAGE = 'معذرت، فی الحال لائیو مارکیٹ ڈیٹا حاصل نہیں ہو سکا، براہ کرم کچھ دیر بعد دوبارہ کوشش کریں۔'


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    result = bot.run_analysis()
    if result is None:
        await update.message.reply_text(DATA_ERROR_MESSAGE)
        return
    await update.message.reply_text(bot.format_signal_message(result))


async def update_1h_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    result = bot.run_analysis()
    if result is None:
        await update.message.reply_text(DATA_ERROR_MESSAGE)
        return
    await update.message.reply_text(bot.format_update_message(result, 1))


async def update_2h_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    result = bot.run_analysis()
    if result is None:
        await update.message.reply_text(DATA_ERROR_MESSAGE)
        return
    await update.message.reply_text(bot.format_update_message(result, 2))


async def auto_signal_job(context: ContextTypes.DEFAULT_TYPE):
    """Periodic broadcast, mirroring the original scheduled behaviour"""
    if not TELEGRAM_CHAT_ID:
        return
    result = bot.run_analysis()
    if result is None:
        return
    if result['direction'] == 'NEUTRAL' or result['confidence'] >= bot.confidence_threshold:
        try:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=bot.format_signal_message(result))
        except Exception as e:
            logger.error(f'Error sending auto signal: {e}')
    else:
        logger.info(f"Signal below threshold ({result['confidence']}% < {bot.confidence_threshold}%)")


def main():
    if not TELEGRAM_TOKEN:
        logger.error('TELEGRAM_TOKEN is not set, cannot start bot')
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', start_command))
    application.add_handler(CommandHandler('signal', signal_command))
    application.add_handler(CommandHandler('1h', update_1h_command))
    application.add_handler(CommandHandler('2h', update_2h_command))

    if TELEGRAM_CHAT_ID and application.job_queue:
        application.job_queue.run_repeating(
            auto_signal_job, interval=SIGNAL_CHECK_INTERVAL_SECONDS, first=10
        )

    logger.info('GoldSignalBot started')
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
