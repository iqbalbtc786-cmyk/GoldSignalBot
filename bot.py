import os
import sys
import time
import base64
import logging
import threading
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import pytz
from dateutil.relativedelta import relativedelta
import schedule
import anthropic

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
SIGNAL_CHECK_INTERVAL = 30  # minutes

# Optional MetaApi.cloud bridge (lets the bot read price data straight from
# a real MT5 broker account, e.g. Exness) instead of Yahoo Finance. Only
# used when both variables are set; otherwise the bot falls back to
# yfinance automatically. See README.md for how to obtain these.
METAAPI_TOKEN = os.getenv('METAAPI_TOKEN')
METAAPI_ACCOUNT_ID = os.getenv('METAAPI_ACCOUNT_ID')
METAAPI_REGION = os.getenv('METAAPI_REGION', 'new-york')
METAAPI_SYMBOL = os.getenv('METAAPI_SYMBOL', 'XAUUSD')

# Optional: lets users chat with the bot (on-demand "/signal", and photo
# screenshots of a chart get a Claude vision read). Needs an Anthropic API
# key (console.anthropic.com) set as ANTHROPIC_API_KEY. Without it, the bot
# still runs fine and just sends the scheduled signals.
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CHART_ANALYSIS_MODEL = 'claude-opus-5'
CHAT_MODEL = 'claude-opus-5'
MAX_CHAT_HISTORY = 20  # messages (≈10 turns) kept per chat, older ones are dropped

CHAT_SYSTEM_PROMPT = (
    'آپ "گولڈ سگنل بوٹ" ہیں، ایک Telegram بوٹ جو XAUUSD (گولڈ) کے لیے ٹریڈنگ سگنلز بھیجتا ہے۔ '
    'صارف سے دوستانہ اور مختصر انداز میں بات کریں (زیادہ تر اردو میں، اگر صارف انگریزی میں لکھے تو انگریزی میں جواب دیں)۔ '
    'اگر صارف حالیہ درست سگنل/قیمت مانگے تو بتائیں کہ درست نمبروں کے لیے /signal کمانڈ بھیجیں (وہاں سے live data آتا ہے)، '
    'لیکن مارکیٹ، گولڈ، DXY، یا عمومی ٹریڈنگ سوالات پر عمومی رائے اور معلومات ضرور دیں۔ '
    'جب بھی کوئی خاص buy/sell رائے دیں تو ایک مختصر ڈسکلیمر شامل کریں کہ یہ مالی مشورہ نہیں ہے۔'
)

HELP_TEXT = (
    '🤖 <b>گولڈ سگنل بوٹ</b>\n\n'
    'کمانڈز:\n'
    '/signal - ابھی کا XAUUSD تجزیہ حاصل کریں\n'
    '/help - یہ پیغام دوبارہ دکھائیں\n\n'
    '💬 آپ مجھ سے عام گفتگو بھی کر سکتے ہیں - کوئی بھی سوال یا بات لکھ کر بھیج دیں۔\n'
    '📷 آپ گولڈ/XAUUSD چارٹ کی اسکرین شاٹ بھی بھیج سکتے ہیں، میں اس کا تجزیہ کر دوں گا۔'
)

class GoldSignalBot:
    def __init__(self):
        self.symbol = 'XAUUSD=X'
        self.dxy_symbol = '^DXY'
        self.timeframes = ['15m', '1h', '4h']
        self.ema_short = 50
        self.ema_long = 200
        self.rsi_period = 14
        self.bb_period = 20
        self.bb_std = 2
        self.atr_period = 14
        self.confidence_threshold = CONFIDENCE_THRESHOLD
        self.use_metaapi = bool(METAAPI_TOKEN and METAAPI_ACCOUNT_ID)
        self.anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
        self.chat_histories = {}  # chat_id -> list of {"role", "content"} messages

        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning('Telegram credentials not configured')

        if self.use_metaapi:
            logger.info(f'Using MetaApi broker feed for {METAAPI_SYMBOL} (account {METAAPI_ACCOUNT_ID})')
        else:
            logger.info('Using Yahoo Finance (yfinance) as the price data source')

    def fetch_data_metaapi(self, interval, limit=500):
        """Fetch OHLCV candles from the connected MT5 broker account via MetaApi.cloud"""
        try:
            url = (
                f'https://mt-market-data-client-api-v1.{METAAPI_REGION}.agiliumtrade.ai'
                f'/users/current/accounts/{METAAPI_ACCOUNT_ID}'
                f'/historical-market-data/symbols/{METAAPI_SYMBOL}/timeframes/{interval}/candles'
            )
            headers = {'auth-token': METAAPI_TOKEN}
            response = requests.get(url, headers=headers, params={'limit': limit}, timeout=15)

            if response.status_code != 200:
                logger.error(f'MetaApi error {response.status_code}: {response.text}')
                return None

            candles = response.json()
            if not candles:
                logger.warning(f'No MetaApi candles returned for {METAAPI_SYMBOL} {interval}')
                return None

            data = pd.DataFrame(candles)
            data = data.rename(columns={
                'open': 'Open', 'high': 'High', 'low': 'Low',
                'close': 'Close', 'tickVolume': 'Volume'
            })
            data['time'] = pd.to_datetime(data['time'])
            data = data.set_index('time').sort_index()
            return data[['Open', 'High', 'Low', 'Close', 'Volume']]
        except Exception as e:
            logger.error(f'Error fetching MetaApi data: {e}')
            return None

    def fetch_data(self, symbol, interval, period):
        """Fetch OHLCV data, preferring the broker feed (MetaApi) for the gold symbol
        when configured, falling back to yfinance otherwise."""
        if self.use_metaapi and symbol == self.symbol:
            data = self.fetch_data_metaapi(interval)
            if data is not None:
                return data
            logger.warning('MetaApi fetch failed, falling back to yfinance for this cycle')

        try:
            data = yf.download(symbol, interval=interval, period=period, progress=False)
            if data.empty:
                logger.warning(f'No data fetched for {symbol} {interval}')
                return None
            return data
        except Exception as e:
            logger.error(f'Error fetching data for {symbol}: {e}')
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
        """Calculate overall signal confidence"""
        if not analysis_1h or not analysis_4h:
            return 0, 'NEUTRAL'
        
        confidence_score = 0
        signal_direction = None
        
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
            
            if ema_buy_4h and rsi_oversold_1h:
                confidence_score += 20
                signal_direction = 'BUY'
            
            if bb_lower_touch_1h and analysis_1h['rsi'] < 50:
                confidence_score += 15
                signal_direction = 'BUY'
            
            if dxy_bias == 'BUY':
                confidence_score += 20
            
            # Sell Signal Logic
            if ema_sell_1h and ema_sell_4h:
                confidence_score += 25
                signal_direction = 'SELL'
            
            if ema_sell_4h and rsi_overbought_1h:
                confidence_score += 20
                signal_direction = 'SELL'
            
            if bb_upper_touch_1h and analysis_1h['rsi'] > 50:
                confidence_score += 15
                signal_direction = 'SELL'
            
            if dxy_bias == 'SELL':
                confidence_score += 20
            
            # Normalize confidence to 100
            confidence_score = min(confidence_score, 100)
            
            # No clear signal
            if signal_direction is None:
                confidence_score = 0
                signal_direction = 'NEUTRAL'
            
            return confidence_score, signal_direction
        
        except Exception as e:
            logger.error(f'Error calculating confidence: {e}')
            return 0, 'NEUTRAL'
    
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
                return 'اپ ٹرینڈ'
            elif current_price < recent_lows * 1.01:
                return 'ڈاؤن ٹرینڈ'
            else:
                return 'استحکام (Consolidation)'
        except Exception as e:
            logger.error(f'Error getting market structure: {e}')
            return 'نامعلوم'

    def check_news_risk(self):
        """Check for potential news risk (simplified)"""
        # In production, integrate with news API or economic calendar
        return 'کم (Low)'
    
    def generate_signal_message(self, confidence, direction, analysis_1h, analysis_4h, targets):
        """Generate formatted signal message"""
        try:
            dxy_bias, dxy_direction = self.get_dxy_bias()
            
            if direction == 'NEUTRAL':
                message = f"🔔 XAUUSD سگنل\n\n📊 کوئی ٹریڈ نہیں - واضح تصدیق کا انتظار\n\nکانفیڈنس: {confidence}%\nتھریش ہولڈ: {self.confidence_threshold}%\n\n⏰ {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            else:
                data_1h = self.fetch_data(self.symbol, '1h', '30d')
                market_structure = self.get_market_structure(data_1h)
                news_risk = self.check_news_risk()
                bb_position = 'اپر بینڈ' if analysis_1h['close'] > analysis_1h['bb_middle'] else 'لوئر بینڈ'

                message = f"""🔔 XAUUSD سگنل

📈 سمت: {direction}
💪 کانفیڈنس: {confidence}%

💰 انٹری: ${targets['entry']:.2f}
🛑 اسٹاپ لاس: ${targets['stop_loss']:.2f}
🎯 ٹی پی 1: ${targets['tp1']:.2f}
🎯 ٹی پی 2: ${targets['tp2']:.2f}
🎯 ٹی پی 3: ${targets['tp3']:.2f}

💱 ڈالر انڈیکس (DXY): {dxy_direction} ({dxy_bias})
📊 مارکیٹ کی صورتحال: {market_structure}
📍 آر ایس آئی (1H): {analysis_1h['rsi']:.2f}
📌 بولنگر بینڈ پوزیشن: {bb_position}
⚠️ نیوز رسک: {news_risk}

⏰ {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"""

            return message
        except Exception as e:
            logger.error(f'Error generating signal message: {e}')
            return None
    
    def send_telegram_signal(self, message, chat_id=None):
        """Send a message to Telegram (defaults to the configured broadcast chat)"""
        target_chat_id = chat_id if chat_id is not None else TELEGRAM_CHAT_ID

        if not TELEGRAM_TOKEN or not target_chat_id:
            logger.warning('Cannot send Telegram signal: credentials missing')
            return False

        try:
            url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
            payload = {
                'chat_id': target_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info('Signal sent to Telegram')
                return True
            else:
                logger.error(f'Telegram error: {response.text}')
                return False
        except Exception as e:
            logger.error(f'Error sending Telegram signal: {e}')
            return False
    
    def generate_current_analysis(self):
        """Run the full analysis pipeline and return (confidence, direction, message)"""
        data_1h = self.fetch_data(self.symbol, '1h', '30d')
        data_4h = self.fetch_data(self.symbol, '4h', '90d')

        if data_1h is None or data_4h is None:
            logger.warning('Insufficient data for analysis')
            return None, None, None

        analysis_1h = self.analyze_timeframe(data_1h)
        analysis_4h = self.analyze_timeframe(data_4h)

        if not analysis_1h or not analysis_4h:
            return None, None, None

        dxy_bias, dxy_direction = self.get_dxy_bias()
        confidence, direction = self.calculate_confidence(analysis_1h, analysis_4h, dxy_bias)

        atr = analysis_1h['atr'] if analysis_1h['atr'] > 0 else analysis_1h['close'] * 0.001
        targets = self.calculate_targets_and_stops(analysis_1h['close'], direction, atr)
        message = self.generate_signal_message(confidence, direction, analysis_1h, analysis_4h, targets)

        return confidence, direction, message

    def analyze_xauusd(self):
        """Main scheduled analysis - only sends when confidence meets the threshold"""
        try:
            logger.info('Starting XAUUSD analysis...')

            confidence, direction, message = self.generate_current_analysis()

            if confidence is None:
                return

            logger.info(f'Signal: {direction}, Confidence: {confidence}%')

            if confidence >= self.confidence_threshold or direction == 'NEUTRAL':
                if message:
                    logger.info(f'Signal Message:\n{message}')
                    self.send_telegram_signal(message)
            else:
                logger.info(f'Signal below threshold ({confidence}% < {self.confidence_threshold}%)')

        except Exception as e:
            logger.error(f'Error in XAUUSD analysis: {e}')

    def handle_signal_request(self, chat_id):
        """Handle an on-demand /signal request - always replies, regardless of threshold"""
        confidence, direction, message = self.generate_current_analysis()

        if message is None:
            self.send_telegram_signal('⚠️ ابھی پرائس ڈیٹا حاصل نہیں ہو سکا، براہ کرم تھوڑی دیر بعد دوبارہ کوشش کریں۔', chat_id=chat_id)
            return

        self.send_telegram_signal(message, chat_id=chat_id)

    def download_telegram_file(self, file_id):
        """Download a file (e.g. a photo) the user sent to the bot"""
        info_resp = requests.get(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile',
            params={'file_id': file_id}, timeout=15
        )
        info = info_resp.json()
        if not info.get('ok'):
            logger.error(f'getFile error: {info}')
            return None

        file_path = info['result']['file_path']
        file_resp = requests.get(
            f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}', timeout=30
        )
        return file_resp.content

    def analyze_chart_screenshot(self, image_bytes, media_type='image/jpeg'):
        """Ask Claude to read a trading chart screenshot and give a directional view"""
        if not self.anthropic_client:
            return (
                '⚠️ چارٹ امیج تجزیہ ابھی سیٹ اپ نہیں ہے۔ بوٹ چلانے والے سے کہیں کہ '
                'ANTHROPIC_API_KEY سیٹ کریں۔'
            )

        try:
            image_b64 = base64.standard_b64encode(image_bytes).decode('utf-8')

            response = self.anthropic_client.messages.create(
                model=CHART_ANALYSIS_MODEL,
                max_tokens=1024,
                messages=[{
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {'type': 'base64', 'media_type': media_type, 'data': image_b64}
                        },
                        {
                            'type': 'text',
                            'text': (
                                'This is a screenshot of a trading chart (likely XAUUSD/Gold). '
                                'Based only on what is visible in the image (candles, trend lines, '
                                'indicators, support/resistance levels), give a short technical read: '
                                '1) overall trend, 2) key support/resistance levels you can see, '
                                '3) a tentative BUY / SELL / NEUTRAL bias with your reasoning. '
                                'Reply in Urdu (اردو رسم الخط میں), keep it under 150 words, use plain '
                                'text suitable for a Telegram message, and end with a one-line '
                                'disclaimer in Urdu that this is not financial advice.'
                            )
                        }
                    ]
                }]
            )

            if response.stop_reason == 'refusal':
                return '⚠️ یہ تصویر تجزیہ نہیں ہو سکی (سیفٹی فلٹرز کی وجہ سے)۔ کوئی صاف چارٹ اسکرین شاٹ آزمائیں۔'

            text = next((block.text for block in response.content if block.type == 'text'), None)
            return text or '⚠️ یہ چارٹ نہیں پڑھا جا سکا، براہ کرم دوسری تصویر آزمائیں۔'
        except Exception as e:
            logger.error(f'Error analyzing chart image: {e}')
            return '⚠️ اس تصویر کا تجزیہ کرتے ہوئے کچھ غلط ہو گیا، براہ کرم دوبارہ کوشش کریں۔'

    def handle_chart_photo(self, chat_id, file_id):
        """Handle a photo the user sent, analyze it, and reply"""
        self.send_telegram_signal('🔎 آپ کے چارٹ اسکرین شاٹ کا تجزیہ ہو رہا ہے...', chat_id=chat_id)
        image_bytes = self.download_telegram_file(file_id)

        if image_bytes is None:
            self.send_telegram_signal('⚠️ وہ تصویر ڈاؤن لوڈ نہیں ہو سکی، براہ کرم دوبارہ کوشش کریں۔', chat_id=chat_id)
            return

        result = self.analyze_chart_screenshot(image_bytes)
        self.send_telegram_signal(f'📊 <b>چارٹ تجزیہ</b>\n\n{result}', chat_id=chat_id)

    def chat_with_claude(self, chat_id, user_text):
        """Free-form conversation, with a short rolling memory per chat"""
        if not self.anthropic_client:
            return (
                '⚠️ چیٹ فیچر ابھی سیٹ اپ نہیں ہے (ANTHROPIC_API_KEY موجود نہیں)۔ '
                'آپ /signal کمانڈ سے موجودہ سگنل حاصل کر سکتے ہیں۔'
            )

        history = self.chat_histories.setdefault(chat_id, [])
        history.append({'role': 'user', 'content': user_text})
        history[:] = history[-MAX_CHAT_HISTORY:]

        try:
            response = self.anthropic_client.messages.create(
                model=CHAT_MODEL,
                max_tokens=1024,
                system=CHAT_SYSTEM_PROMPT,
                messages=history,
            )

            if response.stop_reason == 'refusal':
                return '⚠️ معذرت، اس سوال کا جواب نہیں دے سکتا۔ کچھ اور پوچھیں۔'

            text = next((block.text for block in response.content if block.type == 'text'), None)
            if not text:
                return '⚠️ معذرت، جواب نہیں بن سکا، دوبارہ کوشش کریں۔'

            history.append({'role': 'assistant', 'content': text})
            history[:] = history[-MAX_CHAT_HISTORY:]
            return text
        except Exception as e:
            logger.error(f'Error in chat_with_claude: {e}')
            # Don't keep a dangling user turn with no reply
            if history and history[-1]['role'] == 'user':
                history.pop()
            return '⚠️ ابھی جواب دینے میں مسئلہ ہوا، براہ کرم دوبارہ کوشش کریں۔'

    def handle_update(self, update):
        """Route a single Telegram update to the right handler"""
        message = update.get('message')
        if not message:
            return

        chat_id = message.get('chat', {}).get('id')
        if chat_id is None:
            return

        if 'photo' in message:
            self.handle_chart_photo(chat_id, message['photo'][-1]['file_id'])
            return

        text = (message.get('text') or '').strip()
        if not text:
            return

        lowered = text.lower()
        if lowered.startswith('/start') or lowered.startswith('/help'):
            self.send_telegram_signal(HELP_TEXT, chat_id=chat_id)
        elif lowered.startswith('/signal') or lowered.startswith('/price'):
            self.handle_signal_request(chat_id)
        else:
            # Any other free-text message is a real chat turn
            reply = self.chat_with_claude(chat_id, text)
            self.send_telegram_signal(reply, chat_id=chat_id)

    def run_telegram_listener(self):
        """Long-poll Telegram for incoming messages/photos and reply to them"""
        if not TELEGRAM_TOKEN:
            logger.warning('Telegram listener not started: TELEGRAM_TOKEN missing')
            return

        logger.info('Telegram listener started')
        offset = None

        while True:
            try:
                params = {'timeout': 30}
                if offset is not None:
                    params['offset'] = offset

                resp = requests.get(
                    f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates',
                    params=params, timeout=35
                )
                data = resp.json()

                if not data.get('ok'):
                    logger.error(f'getUpdates error: {data}')
                    time.sleep(5)
                    continue

                for update in data.get('result', []):
                    offset = update['update_id'] + 1
                    try:
                        self.handle_update(update)
                    except Exception as e:
                        logger.error(f'Error handling update: {e}')

            except Exception as e:
                logger.error(f'Telegram listener error: {e}')
                time.sleep(5)
    
    def send_welcome_message(self):
        """Send a one-time welcome message when the bot comes online"""
        source = f'MetaApi ({METAAPI_SYMBOL})' if self.use_metaapi else 'Yahoo Finance'
        message = (
            '🟢 گولڈ سگنل بوٹ اب لائیو ہے\n\n'
            f'📡 ڈیٹا سورس: {source}\n'
            f'⏱ ہر {SIGNAL_CHECK_INTERVAL} منٹ بعد XAUUSD چیک ہوگا\n'
            f'🎯 کانفیڈنس تھریش ہولڈ: {self.confidence_threshold}%\n\n'
            f'⏰ {datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")}'
        )
        self.send_telegram_signal(message)

    def start(self):
        """Start the bot scheduler"""
        logger.info('GoldSignalBot started')

        self.send_welcome_message()

        # Listen for incoming Telegram messages/photos in the background
        threading.Thread(target=self.run_telegram_listener, daemon=True).start()

        # Schedule the analysis to run every 30 minutes
        schedule.every(SIGNAL_CHECK_INTERVAL).minutes.do(self.analyze_xauusd)

        # Run initial analysis
        self.analyze_xauusd()
        
        # Keep the scheduler running
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)
            except Exception as e:
                logger.error(f'Scheduler error: {e}')
                time.sleep(60)


if __name__ == '__main__':
    bot = GoldSignalBot()
    bot.start()
