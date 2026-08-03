import os
import sys
import time
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import pytz
from dateutil.relativedelta import relativedelta
import schedule

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
    
    def generate_signal_message(self, confidence, direction, analysis_1h, analysis_4h, targets):
        """Generate formatted signal message"""
        try:
            dxy_bias, dxy_direction = self.get_dxy_bias()
            
            if direction == 'NEUTRAL':
                message = f"🔔 XAUUSD SIGNAL\n\n📊 No Trade - Waiting for Confirmation\n\nConfidence: {confidence}%\nThreshold: {self.confidence_threshold}%\n\n⏰ {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            else:
                data_1h = self.fetch_data(self.symbol, '1h', '30d')
                market_structure = self.get_market_structure(data_1h)
                news_risk = self.check_news_risk()
                
                message = f"""🔔 XAUUSD SIGNAL

📈 Direction: {direction}
💪 Confidence: {confidence}%

💰 Entry: ${targets['entry']:.2f}
🛑 Stop Loss: ${targets['stop_loss']:.2f}
🎯 TP1: ${targets['tp1']:.2f}
🎯 TP2: ${targets['tp2']:.2f}
🎯 TP3: ${targets['tp3']:.2f}

💱 DXY Bias: {dxy_direction} ({dxy_bias})
📊 Market Structure: {market_structure}
📍 RSI (1H): {analysis_1h['rsi']:.2f}
📌 BB Position: {'Upper Band' if analysis_1h['close'] > analysis_1h['bb_middle'] else 'Lower Band'}
⚠️ News Risk: {news_risk}

⏰ {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"""
            
            return message
        except Exception as e:
            logger.error(f'Error generating signal message: {e}')
            return None
    
    def send_telegram_signal(self, message):
        """Send signal to Telegram"""
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning('Cannot send Telegram signal: credentials missing')
            return False
        
        try:
            url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
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
    
    def analyze_xauusd(self):
        """Main analysis function"""
        try:
            logger.info('Starting XAUUSD analysis...')
            
            # Fetch data for all timeframes
            data_15m = self.fetch_data(self.symbol, '15m', '5d')
            data_1h = self.fetch_data(self.symbol, '1h', '30d')
            data_4h = self.fetch_data(self.symbol, '4h', '90d')
            
            if data_1h is None or data_4h is None:
                logger.warning('Insufficient data for analysis')
                return
            
            # Analyze timeframes
            analysis_15m = self.analyze_timeframe(data_15m)
            analysis_1h = self.analyze_timeframe(data_1h)
            analysis_4h = self.analyze_timeframe(data_4h)
            
            # Get DXY bias
            dxy_bias, dxy_direction = self.get_dxy_bias()
            
            # Calculate confidence and signal
            confidence, direction = self.calculate_confidence(analysis_1h, analysis_4h, dxy_bias)
            
            logger.info(f'Signal: {direction}, Confidence: {confidence}%')
            
            # If confidence meets threshold, generate and send signal
            if confidence >= self.confidence_threshold or direction == 'NEUTRAL':
                if analysis_1h and analysis_4h:
                    atr = analysis_1h['atr'] if analysis_1h['atr'] > 0 else analysis_1h['close'] * 0.001
                    targets = self.calculate_targets_and_stops(analysis_1h['close'], direction, atr)
                    
                    message = self.generate_signal_message(confidence, direction, analysis_1h, analysis_4h, targets)
                    
                    if message:
                        logger.info(f'Signal Message:\n{message}')
                        self.send_telegram_signal(message)
            else:
                logger.info(f'Signal below threshold ({confidence}% < {self.confidence_threshold}%)')
        
        except Exception as e:
            logger.error(f'Error in XAUUSD analysis: {e}')
    
    def send_welcome_message(self):
        """Send a one-time welcome message when the bot comes online"""
        source = f'MetaApi ({METAAPI_SYMBOL})' if self.use_metaapi else 'Yahoo Finance'
        message = (
            '🟢 Gold Signal Bot is now LIVE\n\n'
            f'📡 Data source: {source}\n'
            f'⏱ Checking XAUUSD every {SIGNAL_CHECK_INTERVAL} minutes\n'
            f'🎯 Confidence threshold: {self.confidence_threshold}%\n\n'
            f'⏰ {datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")}'
        )
        self.send_telegram_signal(message)

    def start(self):
        """Start the bot scheduler"""
        logger.info('GoldSignalBot started')

        self.send_welcome_message()

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
