# trading-signals-website/app.py

import os
import json
import threading
import logging
import time
import uuid
import tempfile
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd
from flask import Flask, jsonify, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler
from ta.trend import MACD, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
import numpy as np

# Import cấu hình
from config import (
    COINS, INTERVAL, LIMIT, SQUEEZE_THRESHOLD, COOLDOWN_MINUTES,
    SCAN_INTERVAL_MINUTES, RISK_PER_TRADE, COMBO_DETAILS
)

# =============================================================================
# CONFIGURATION & LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Khóa an toàn luồng (Thread-safety lock)
data_lock = threading.Lock()

# =============================================================================
# FILE STORAGE FUNCTIONS (Thread-safe) - ĐÃ SỬA
# =============================================================================

# Sử dụng thư mục hiện tại cho đơn giản
DATA_FILE = 'trading_signals.json'

def load_data():
    """Tải file JSON với xử lý lỗi tốt hơn"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"✅ Đã tải {len(data.get('signals', []))} tín hiệu từ {DATA_FILE}")
                return data
        else:
            logger.info(f"📁 File {DATA_FILE} chưa tồn tại, tạo mới")
    except Exception as e:
        logger.error(f"❌ Lỗi đọc {DATA_FILE}: {e}")
    
    # Trả về data mặc định nếu có lỗi
    return {"signals": []}

def save_data(data):
    """Lưu file JSON một cách an toàn (dùng trong lock)"""
    temp_file = f"{DATA_FILE}.tmp"
    try:
        with open(temp_file, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(temp_file, DATA_FILE)
        logger.info(f"💾 Đã lưu {len(data.get('signals', []))} tín hiệu vào {DATA_FILE}")
    except Exception as e:
        logger.error(f"❌ Lỗi lưu {DATA_FILE}: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

# =============================================================================
# BINANCE API & INDICATORS - ĐÃ SỬA
# =============================================================================

def get_klines(symbol, max_retries=3):
    """Fetch klines từ Binance Futures API với xử lý lỗi tốt hơn"""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": INTERVAL, "limit": LIMIT}
    
    logger.info(f"📡 Đang lấy dữ liệu cho {symbol}...")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            
            # Kiểm tra HTTP status code
            if response.status_code != 200:
                logger.error(f"❌ Binance API error {response.status_code} cho {symbol}: {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
                
            data = response.json()
            
            # Kiểm tra nếu Binance trả về lỗi (dạng dict)
            if isinstance(data, dict) and 'code' in data:
                error_msg = data.get('msg', 'Unknown error')
                logger.error(f"❌ Binance API error cho {symbol}: {error_msg} (code: {data.get('code')})")
                return None
                
            # Kiểm tra dữ liệu trả về
            if not data or len(data) < 100:  # Ít nhất 100 nến
                logger.warning(f"⚠️ Không đủ dữ liệu cho {symbol}: {len(data) if data else 0} nến")
                return None
                
            # Tạo DataFrame
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume", 
                "close_time", "quote_volume", "trades", "taker_buy_base", 
                "taker_buy_quote", "ignore"
            ])
            
            # Chuyển đổi kiểu dữ liệu với xử lý lỗi
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Kiểm tra và loại bỏ NaN values
            nan_count = df[["open", "high", "low", "close", "volume"]].isna().sum().sum()
            if nan_count > 0:
                logger.warning(f"⚠️ {symbol} có {nan_count} giá trị NaN, đang làm sạch...")
                df = df.dropna()
            
            if len(df) < 100:
                logger.warning(f"⚠️ {symbol} có quá nhiều NaN, chỉ còn {len(df)} nến")
                return None
                
            # Chuyển đổi thời gian
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            
            logger.info(f"✅ {symbol}: Lấy thành công {len(df)} nến, giá cuối: {df['close'].iloc[-1]:.4f}")
            return df
            
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Timeout lần {attempt + 1} cho {symbol}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
                
        except requests.exceptions.ConnectionError:
            logger.error(f"🌐 Lỗi kết nối lần {attempt + 1} cho {symbol}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
                
        except Exception as e:
            logger.error(f"💥 Lỗi không xác định lần {attempt + 1} cho {symbol}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
    
    return None

def add_indicators(df):
    """Add all technical indicators to dataframe"""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    
    # EMAs
    df["ema8"] = EMAIndicator(close, window=8).ema_indicator()
    df["ema21"] = EMAIndicator(close, window=21).ema_indicator()
    df["ema50"] = EMAIndicator(close, window=50).ema_indicator()
    df["ema200"] = EMAIndicator(close, window=200).ema_indicator()
    # MACD
    macd = MACD(close)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()
    # RSI
    df["rsi14"] = RSIIndicator(close, window=14).rsi()
    # Bollinger Bands
    bb = BollingerBands(close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
    # ATR
    atr = AverageTrueRange(high, low, close, window=14)
    df["atr"] = atr.average_true_range()
    # Keltner Channel
    typical_price = (high + low + close) / 3
    df["kc_mid"] = typical_price.rolling(20).mean()
    df["kc_range"] = df["atr"] * 1.5
    df["kc_upper"] = df["kc_mid"] + df["kc_range"]
    df["kc_lower"] = df["kc_mid"] - df["kc_range"]
    # VWAP
    df["vwap"] = (typical_price * volume).cumsum() / volume.cumsum()
    # Volume MA
    df["volume_ma20"] = volume.rolling(20).mean()
    # FVG Detection
    df["fvg_bull"] = (df["low"].shift(2) > df["high"].shift(1))
    df["fvg_bear"] = (df["high"].shift(2) < df["low"].shift(1))
    # Wick and Body
    df["body"] = abs(df["open"] - df["close"])
    df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    return df

# =============================================================================
# 18 TRADING COMBOS (Đã bao gồm 2 combo mới)
# =============================================================================

def combo1_fvg_squeeze_pro(df):
    """FVG Squeeze Pro"""
    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        squeeze = (last.bb_width < SQUEEZE_THRESHOLD and 
                  last.bb_upper < last.kc_upper and 
                  last.bb_lower > last.kc_lower)
        breakout_up = last.close > last.bb_upper and prev.close <= prev.bb_upper
        vol_spike = last.volume > last.volume_ma20 * 1.3
        trend_up = last.close > last.ema200
        rsi_ok = last.rsi14 < 68
        
        if squeeze and breakout_up and vol_spike and trend_up and rsi_ok:
            entry = last.close
            sl = entry - 1.5 * last.atr
            tp = entry + 3.0 * last.atr
            return "LONG", entry, sl, tp, "FVG Squeeze Pro"
        
        breakout_down = last.close < last.bb_lower and prev.close >= prev.bb_lower
        if squeeze and breakout_down and vol_spike and last.close < last.ema200:
            entry = last.close
            sl = entry + 1.5 * last.atr
            tp = entry - 3.0 * last.atr
            return "SHORT", entry, sl, tp, "FVG Squeeze Pro"
            
    except Exception as e:
        logger.error(f"Combo1 error: {e}")
    
    return None

def combo2_macd_ob_retest(df):
    """MACD Order Block Retest"""
    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        macd_cross_up = last.macd > last.macd_signal and prev.macd <= prev.macd_signal
        price_above_ema200 = last.close > last.ema200
        
        ob_zone = None
        if all(df["close"].iloc[-3:] > df["open"].iloc[-3:]):
            ob_zone = df["low"].iloc[-5:-2].min()
        
        retest = ob_zone is not None and last.low <= ob_zone + last.atr * 0.5
        vol_confirm = last.volume > df["volume"].mean() * 1.1
        
        if macd_cross_up and price_above_ema200 and retest and vol_confirm:
            entry = last.close
            sl = ob_zone - last.atr
            tp = entry + 2.5 * last.atr
            return "LONG", entry, sl, tp, "MACD Order Block Retest"
            
    except Exception as e:
        logger.error(f"Combo2 error: {e}")
    
    return None

def combo3_stop_hunt_squeeze(df):
    """Stop Hunt Squeeze"""
    try:
        last = df.iloc[-1]
        
        squeeze = last.bb_width < SQUEEZE_THRESHOLD
        stop_hunt = False
        
        if last.body > 0:
            if last.close > last.open:
                stop_hunt = (last.lower_wick / last.body > 2)
            else:
                stop_hunt = (last.upper_wick / last.body > 2)
        
        breakout_up = last.close > last.bb_upper
        
        if squeeze and stop_hunt and breakout_up:
            entry = last.close
            sl = last.low - last.atr
            tp = entry + 2.8 * last.atr
            return "LONG", entry, sl, tp, "Stop Hunt Squeeze"
            
    except Exception as e:
        logger.error(f"Combo3 error: {e}")
    
    return None

def combo4_fvg_ema_pullback(df):
    """FVG EMA Pullback"""
    try:
        last = df.iloc[-1]
        
        fvg_bull_zones = df[df["fvg_bull"]]
        fvg_pullback = False
        
        if not fvg_bull_zones.empty and df["fvg_bull"].iloc[-5:].any():
            fvg_pullback = last.low <= fvg_bull_zones["high"].max()
        
        cross_up = last.ema8 > last.ema21 and df["ema8"].iloc[-2] <= df["ema21"].iloc[-2]
        
        if fvg_pullback and cross_up:
            entry = last.close
            sl = last.low - last.atr * 0.8
            tp = entry + 2.0 * last.atr
            return "LONG", entry, sl, tp, "FVG EMA Pullback"
            
    except Exception as e:
        logger.error(f"Combo4 error: {e}")
    
    return None

def combo5_fvg_macd_divergence(df):
    """FVG + MACD Divergence"""
    try:
        last = df.iloc[-1]
        
        hist = df["macd_hist"]
        low = df["low"]
        
        divergence = hist.iloc[-1] > hist.iloc[-3] and low.iloc[-1] < low.iloc[-3]
        fvg = df["fvg_bull"].iloc[-8:].any()
        rsi_ok = last.rsi14 < 30
        
        if divergence and fvg and rsi_ok:
            entry = last.close
            sl = low.iloc[-5:].min() - last.atr
            tp = entry + 2.5 * last.atr
            return "LONG", entry, sl, tp, "FVG + MACD Divergence"
            
    except Exception as e:
        logger.error(f"Combo5 error: {e}")
    
    return None

def combo6_ob_liquidity_grab(df):
    """Order Block + Liquidity Grab"""
    try:
        last = df.iloc[-1]
        
        ob = df["low"].iloc[-6:-3].min()
        liquidity_grab = (last.lower_wick / last.body > 2.5) if last.body > 0 else False
        retest_ob = last.close > ob
        macd_pos = last.macd_hist > 0
        
        if liquidity_grab and retest_ob and macd_pos:
            entry = last.close
            sl = last.low - last.atr
            tp = entry + 1.8 * last.atr
            return "LONG", entry, sl, tp, "Order Block + Liquidity Grab"
            
    except Exception as e:
        logger.error(f"Combo6 error: {e}")
    
    return None

def combo7_stop_hunt_fvg_retest(df):
    """Stop Hunt + FVG Retest"""
    try:
        last = df.iloc[-1]
        
        stop_hunt = (last.lower_wick / last.body > 2) if last.body > 0 else False
        fvg_after = df["fvg_bull"].iloc[-3:]
        retest = (last.low <= df["high"].shift(1).max()) if fvg_after.any() else False
        
        if stop_hunt and fvg_after.any() and retest:
            entry = last.close
            sl = last.low - 0.5 * last.atr
            tp = entry + 1.5 * last.atr
            return "LONG", entry, sl, tp, "Stop Hunt + FVG Retest"
            
    except Exception as e:
        logger.error(f"Combo7 error: {e}")
    
    return None

def combo8_fvg_macd_hist_spike(df):
    """FVG + MACD Hist Spike"""
    try:
        last = df.iloc[-1]
        
        if len(df) >= 5:
            current_hist = df["macd_hist"].iloc[-3:].values
            prev_hist = df["macd_hist"].iloc[-4:-1].values
            if len(current_hist) == 3 and len(prev_hist) == 3:
                hist_spike = (current_hist > prev_hist).all()
            else:
                hist_spike = False
        else:
            hist_spike = False
            
        fvg = df["fvg_bull"].iloc[-5:].any()
        price_above_vwap = last.close > last.vwap
        
        if hist_spike and fvg and price_above_vwap:
            entry = last.close
            sl = last.low - last.atr
            tp = entry + 2.5 * last.atr
            return "LONG", entry, sl, tp, "FVG + MACD Hist Spike"
            
    except Exception as e:
        logger.error(f"Combo8 error: {e}")
    
    return None

def combo9_ob_fvg_confluence(df):
    """OB + FVG Confluence"""
    try:
        last = df.iloc[-1]
        
        ob = df["low"].iloc[-10:-5].min()
        fvg_bull_zones = df[df["fvg_bull"]]
        fvg_zone = 0
        
        if not fvg_bull_zones.empty and df["fvg_bull"].iloc[-10:].any():
            fvg_zone = fvg_bull_zones["high"].max()
        
        confluence = (abs(ob - fvg_zone) < last.atr * 0.5) if fvg_zone > 0 else False
        engulfing = last.close > last.open and last.open < df["close"].iloc[-2]
        volume_delta = last.volume > df["volume"].mean() * 1.5
        
        if confluence and engulfing and volume_delta:
            entry = last.close
            sl = min(ob, fvg_zone) - last.atr if fvg_zone > 0 else ob - last.atr
            tp = entry + 2.0 * last.atr
            return "LONG", entry, sl, tp, "OB + FVG Confluence"
            
    except Exception as e:
        logger.error(f"Combo9 error: {e}")
    
    return None

def combo10_smc_ultimate(df):
    """SMC Ultimate"""
    try:
        last = df.iloc[-1]
        
        squeeze = last.bb_width < SQUEEZE_THRESHOLD
        fvg = df["fvg_bull"].iloc[-5:].any()
        macd_up = last.macd_hist > 0 and last.macd_hist > df["macd_hist"].iloc[-2]
        liquidity = (last.lower_wick / last.body > 2) if last.body > 0 else False
        ob_retest = last.low <= df["low"].iloc[-5:-2].min()
        
        if squeeze and fvg and macd_up and liquidity and ob_retest:
            entry = last.close
            sl = last.low - last.atr
            tp = entry + 3.5 * last.atr
            return "LONG", entry, sl, tp, "SMC Ultimate"
            
    except Exception as e:
        logger.error(f"Combo10 error: {e}")
    
    return None

def combo11_fvg_ob_liquidity_break(df):
    """FVG + Order Block + Liquidity Break"""
    try:
        last = df.iloc[-1]
        
        # FVG bullish
        fvg = last.fvg_bull or df["fvg_bull"].iloc[-3:].any()
        
        # Order Block
        ob = df["low"].iloc[-5:].min()
        
        # Liquidity Break
        liquidity_break = last.close > df["high"].iloc[-5:].max()
        
        # Volume
        vol_spike = last.volume > last.volume_ma20 * 1.5
        
        if fvg and liquidity_break and vol_spike:
            entry = last.close
            sl = ob - 0.5 * last.atr
            tp = entry + 2.0 * last.atr
            return "LONG", entry, sl, tp, "FVG OB Liquidity Break"
            
    except Exception as e:
        logger.error(f"Combo11 error: {e}")
    
    return None

def combo12_liquidity_grab_fvg_retest(df):
    """Liquidity Grab + FVG Retest"""
    try:
        last = df.iloc[-1]
        
        # Liquidity Grab
        liquidity_grab = (last.lower_wick / last.body > 2.5) if last.body > 0 else False
        
        # FVG Retest
        fvg_zones = df[df["fvg_bull"]]
        fvg_retest = False
        if not fvg_zones.empty and df["fvg_bull"].iloc[-5:].any():
            fvg_retest = last.low <= fvg_zones["high"].max()
        
        # MACD
        macd_ok = last.macd_hist > 0 and last.macd_hist > df["macd_hist"].iloc[-2]
        
        if liquidity_grab and fvg_retest and macd_ok:
            entry = last.close
            sl = last.low - 0.8 * last.atr
            tp = entry + 1.8 * last.atr
            return "LONG", entry, sl, tp, "Liquidity Grab FVG Retest"
            
    except Exception as e:
        logger.error(f"Combo12 error: {e}")
    
    return None

def combo13_fvg_macd_momentum_scalp(df):
    """COMBO 13: FVG + MACD Momentum Scalp"""
    try:
        last = df.iloc[-1]
        
        # FVG recent
        fvg = df["fvg_bull"].iloc[-2:].any() and last.close > last.open
        
        # MACD momentum
        macd_mom = last.macd > last.macd_signal and abs(last.macd_hist) > abs(df["macd_hist"].iloc[-2])
        
        # VWAP
        above_vwap = last.close > last.vwap
        
        # Low volatility
        low_vol = (last.atr / last.close) < 0.02
        
        if fvg and macd_mom and above_vwap and low_vol:
            entry = last.close
            sl = last.low - 0.5 * last.atr
            tp = entry + 1.2 * last.atr
            return "LONG", entry, sl, tp, "FVG MACD Momentum Scalp"
            
    except Exception as e:
        logger.error(f"Combo13 error: {e}")
    
    return None

def combo14_ob_liquidity_macd_div(df):
    """COMBO 14: Order Block + Liquidity + MACD Divergence"""
    try:
        last = df.iloc[-1]
        
        # Order Block
        ob = df["low"].iloc[-7:-2].min()
        
        # Liquidity sweep
        liquidity = (last.lower_wick / last.body > 2.0) if last.body > 0 else False
        
        # MACD Divergence
        divergence = (df["macd_hist"].iloc[-1] > df["macd_hist"].iloc[-3] and 
                     df["low"].iloc[-1] < df["low"].iloc[-3])
        
        # Entry confirmation
        entry_ok = last.close > ob
        
        if liquidity and divergence and entry_ok:
            entry = last.close
            sl = ob - 0.3 * last.atr
            tp = entry + 2.5 * last.atr
            return "LONG", entry, sl, tp, "OB Liquidity MACD Div"
            
    except Exception as e:
        logger.error(f"Combo14 error: {e}")
    
    return None

def combo15_vwap_ema_volume_scalp(df):
    """COMBO 15: VWAP + EMA Cross + Volume Spike Scalp"""
    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # EMA Cross (8 & 21)
        ema_cross = last.ema8 > last.ema21 and prev.ema8 <= prev.ema21
        
        # Price above VWAP
        above_vwap = last.close > last.vwap
        
        # Volume spike (180% of 20-period average)
        vol_spike = last.volume > last.volume_ma20 * 1.8
        
        # RSI not overbought (below 60)
        rsi_ok = last.rsi14 < 60
        
        if ema_cross and above_vwap and vol_spike and rsi_ok:
            entry = last.close
            sl = last.low - 0.5 * last.atr
            tp = entry + 1.0 * last.atr
            return "LONG", entry, sl, tp, "VWAP EMA Volume Scalp"
            
    except Exception as e:
        logger.error(f"Combo15 error: {e}")
    
    return None

def combo16_rsi_extreme_bounce(df):
    """COMBO 16: RSI Extreme + Price Action Bounce"""
    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # RSI Extreme (oversold for long, overbought for short)
        rsi_oversold = last.rsi14 < 25
        rsi_overbought = last.rsi14 > 75
        
        # Price Action Bounce patterns
        bullish_engulfing = (last.close > last.open and 
                           prev.close < prev.open and 
                           last.close > prev.open and 
                           last.open < prev.close)
        
        bearish_engulfing = (last.close < last.open and 
                           prev.close > prev.open and 
                           last.close < prev.open and 
                           last.open > prev.close)
        
        hammer = (last.lower_wick > 2 * last.body and 
                last.upper_wick < 0.2 * last.body and 
                last.close > last.open) if last.body > 0 else False
                
        shooting_star = (last.upper_wick > 2 * last.body and 
                       last.lower_wick < 0.2 * last.body and 
                       last.close < last.open) if last.body > 0 else False
        
        # Volume confirmation
        vol_ok = last.volume > last.volume_ma20 * 1.2
        
        # LONG: RSI oversold + bullish pattern
        if rsi_oversold and (bullish_engulfing or hammer) and vol_ok:
            entry = last.close
            sl = last.low - 0.8 * last.atr
            tp = entry + 1.5 * last.atr
            return "LONG", entry, sl, tp, "RSI Extreme Bounce LONG"
            
        # SHORT: RSI overbought + bearish pattern  
        if rsi_overbought and (bearish_engulfing or shooting_star) and vol_ok:
            entry = last.close
            sl = last.high + 0.8 * last.atr
            tp = entry - 1.5 * last.atr
            return "SHORT", entry, sl, tp, "RSI Extreme Bounce SHORT"
            
    except Exception as e:
        logger.error(f"Combo16 error: {e}")
    
    return None

def combo17_ema_stack_volume_confirmation(df):
    """COMBO 17: EMA Stack + Volume Confirmation"""
    try:
        last = df.iloc[-1]
        
        # EMA Stack đẹp (xếp chồng tăng)
        ema_stack = (last.ema8 > last.ema21 > last.ema50 > last.ema200)
        
        # Giá trên tất cả EMA
        price_above_all = (last.close > last.ema8 and
                           last.close > last.ema21 and
                           last.close > last.ema50 and
                           last.close > last.ema200)
        
        # Volume tăng ít nhất 50% so với trung bình
        volume_confirm = last.volume > last.volume_ma20 * 1.5
        
        # RSI không quá mua (dưới 65)
        rsi_ok = last.rsi14 < 65
        
        # Pullback về EMA8 hoặc EMA21 rồi bật lên
        pullback_bounce = (
            (last.low <= last.ema8 and last.close > last.ema8) or
            (last.low <= last.ema21 and last.close > last.ema21)
        )
        
        if (ema_stack and price_above_all and volume_confirm and
            rsi_ok and pullback_bounce):
            
            entry = last.close
            # SL dưới EMA21 hoặc low của nến
            sl = min(last.ema21, last.low) - 0.3 * last.atr
            tp = entry + 1.8 * last.atr
            
            return "LONG", entry, sl, tp, "EMA Stack Volume Confirmation"
            
    except Exception as e:
        logger.error(f"Combo17 error: {e}")
    
    return None

def combo18_support_resistance_break_retest(df):
    """COMBO 18: Support/Resistance Break + Retest"""
    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Xác định Support/Resistance gần nhất
        resistance_level = df["high"].iloc[-20:-1].max()
        support_level = df["low"].iloc[-20:-1].min()
        
        # Breakout trên Resistance
        resistance_break = (last.close > resistance_level and
                            prev.close <= resistance_level)
        
        # Breakout dưới Support
        support_break = (last.close < support_level and
                         prev.close >= support_level)
        
        # Volume xác nhận breakout (tăng ít nhất 80%)
        volume_spike = last.volume > last.volume_ma20 * 1.8
        
        # Retest sau breakout
        retest_confirmation = False
        if resistance_break:
            # Retest resistance trở thành support
            retest_confirmation = (last.low <= (resistance_level + last.atr * 0.2) and
                                   last.close > resistance_level)
        elif support_break:
            # Retest support trở thành resistance
            retest_confirmation = (last.high >= (support_level - last.atr * 0.2) and
                                   last.close < support_level)
        
        # MACD xác nhận momentum
        macd_confirm_long = (resistance_break and last.macd > last.macd_signal and last.macd_hist > 0)
        macd_confirm_short = (support_break and last.macd < last.macd_signal and last.macd_hist < 0)
            
        if (volume_spike and retest_confirmation):
            
            if resistance_break and macd_confirm_long:
                entry = last.close
                sl = resistance_level - 0.5 * last.atr
                tp = entry + 2.0 * last.atr
                return "LONG", entry, sl, tp, "Resistance Break Retest"
                
            elif support_break and macd_confirm_short:
                entry = last.close
                sl = support_level + 0.5 * last.atr
                tp = entry - 2.0 * last.atr
                return "SHORT", entry, sl, tp, "Support Break Retest"
                
    except Exception as e:
        logger.error(f"Combo18 error: {e}")
    
    return None

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def check_cooldown(symbol, combo_name, all_signals):
    """Kiểm tra cooldown từ file signals.json (UTC-aware)"""
    now = datetime.now(timezone.utc)
    for sig in all_signals:
        if sig["coin"] == symbol and sig.get("combo_name") == combo_name:
            sig_time = datetime.fromisoformat(sig["timestamp"])
            elapsed_minutes = (now - sig_time).total_seconds() / 60
            if elapsed_minutes < COOLDOWN_MINUTES:
                logger.info(f"⏳ Cooldown: {symbol} - {combo_name}: {elapsed_minutes:.1f}/{COOLDOWN_MINUTES} min")
                return False
    return True

# =============================================================================
# MAIN SCANNING FUNCTION - ĐÃ SỬA VỚI DEBUG LOGGING
# =============================================================================

def scan():
    """Hàm quét chính - với logging chi tiết để debug"""
    logger.info(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] 🔍 Bắt đầu chu kỳ quét {len(COINS)} coins...")
    signals_found_this_run = 0

    # Danh sách tất cả 18 combo
    combos = [
        combo1_fvg_squeeze_pro, combo2_macd_ob_retest, combo3_stop_hunt_squeeze,
        combo4_fvg_ema_pullback, combo5_fvg_macd_divergence, combo6_ob_liquidity_grab,
        combo7_stop_hunt_fvg_retest, combo8_fvg_macd_hist_spike, combo9_ob_fvg_confluence,
        combo10_smc_ultimate, combo11_fvg_ob_liquidity_break, combo12_liquidity_grab_fvg_retest,
        combo13_fvg_macd_momentum_scalp, combo14_ob_liquidity_macd_div,
        combo15_vwap_ema_volume_scalp, combo16_rsi_extreme_bounce,
        combo17_ema_stack_volume_confirmation, combo18_support_resistance_break_retest
    ]
    
    logger.info(f"📊 Sẽ kiểm tra {len(combos)} combo cho mỗi coin")

    # Tải dữ liệu tín hiệu HIỆN TẠI (một lần) để kiểm tra cooldown
    with data_lock:
        data = load_data()
        all_signals = data.get("signals", [])
        logger.info(f"📁 Hiện có {len(all_signals)} tín hiệu trong database")

    for coin in COINS:
        try:
            logger.info(f"🎯 Đang xử lý {coin}...")
            df = get_klines(coin)
            
            if df is None:
                logger.warning(f"❌ Không lấy được dữ liệu cho {coin}")
                continue
                
            if len(df) < 200:
                logger.warning(f"⚠️ Không đủ dữ liệu cho {coin}: chỉ có {len(df)} nến")
                continue
            
            logger.info(f"✅ {coin}: {len(df)} nến, giá cuối: {df['close'].iloc[-1]:.4f}")
            
            # Kiểm tra dữ liệu NaN
            if df['close'].isna().any():
                logger.warning(f"⚠️ {coin} có dữ liệu NaN, đang làm sạch...")
                df = df.dropna()
                if len(df) < 200:
                    logger.warning(f"⚠️ Sau khi làm sạch, {coin} chỉ còn {len(df)} nến")
                    continue

            df = add_indicators(df.copy())
            logger.info(f"📈 {coin}: Đã thêm indicators, đang kiểm tra combo...")

            combo_checked = 0
            combo_found = 0

            for i, combo_func in enumerate(combos, 1):
                try:
                    combo_checked += 1
                    result = combo_func(df)
                    if result:
                        direction, entry, sl, tp, combo_name = result
                        combo_found += 1
                        
                        logger.info(f"🎯 {coin} - COMBO{i}: TÌM THẤY TÍN HIỆU - {combo_name}")
                        
                        # 1. Kiểm tra Cooldown
                        if not check_cooldown(coin, combo_name, all_signals):
                            logger.info(f"⏳ {coin} - {combo_name}: Đang trong cooldown, bỏ qua")
                            continue

                        # 2. Tạo tín hiệu
                        signal_id = str(uuid.uuid4())
                        now_utc = datetime.now(timezone.utc)
                        
                        risk = abs(entry - sl)
                        reward = abs(tp - entry)
                        rr_ratio = (reward / risk) if risk > 0 else 0
                        
                        new_signal = {
                            "id": signal_id,
                            "coin": coin,
                            "direction": direction,
                            "entry": float(entry),
                            "sl": float(sl),
                            "tp": float(tp),
                            "combo_name": combo_name,
                            "combo_details": COMBO_DETAILS.get(combo_name, "Không có mô tả chi tiết."),
                            "rr": round(rr_ratio, 2),
                            "timestamp": now_utc.isoformat(),
                            "status": "active",
                            "votes_win": 0,
                            "votes_lose": 0,
                            "voted_ips": []
                        }
                        
                        # 3. Lưu tín hiệu (Thread-safe)
                        with data_lock:
                            current_data = load_data()
                            current_data.setdefault("signals", []).append(new_signal)
                            save_data(current_data)
                            all_signals.append(new_signal)
                        
                        signals_found_this_run += 1
                        logger.info(f"✅ ĐÃ LƯU: {coin} - {combo_name} - Entry: {entry:.4f}, SL: {sl:.4f}, TP: {tp:.4f}, RR: 1:{rr_ratio:.1f}")
                        
                        # Chỉ lấy 1 tín hiệu mỗi coin mỗi lần quét
                        break 
                    else:
                        logger.debug(f"❌ {coin} - COMBO{i}: Không đạt điều kiện")
                        
                except Exception as e:
                    logger.error(f"💥 {coin} - COMBO{i} ({combo_func.__name__}) lỗi: {e}")
                    
            logger.info(f"📊 {coin}: Đã kiểm tra {combo_checked} combo, tìm thấy {combo_found} tín hiệu")
                    
        except Exception as e:
            logger.error(f"💥 Lỗi xử lý {coin}: {e}")

    logger.info(f"✅ Quét xong. Tìm thấy {signals_found_this_run} tín hiệu mới trong lần quét này.")

# =============================================================================
# FLASK API ROUTES
# =============================================================================

@app.route('/api/signals')
def get_signals():
    """API: Lấy tất cả tín hiệu đang 'active'"""
    with data_lock:
        data = load_data()
        signals = data.get("signals", [])
    
    # Sắp xếp: tín hiệu mới nhất lên đầu
    signals.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Chỉ gửi các tín hiệu 'active' (chưa bị vote đóng)
    active_signals = [s for s in signals if s.get('status', 'active') == 'active']
    
    return jsonify(active_signals)

@app.route('/api/stats')
def get_stats():
    """API: Thống kê Win/Lose (chỉ tính các tín hiệu đã 'closed')"""
    with data_lock:
        data = load_data()
        signals = data.get("signals", [])
        
    now = datetime.now(timezone.utc)
    
    # Chỉ thống kê các tín hiệu đã được vote (status = 'closed')
    closed_signals = [s for s in signals if s.get('status') == 'closed']
    
    def calculate_stats(period_signals):
        wins = sum(1 for s in period_signals if s.get('votes_win', 0) > s.get('votes_lose', 0))
        losses = sum(1 for s in period_signals if s.get('votes_lose', 0) > s.get('votes_win', 0))
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        return {"wins": wins, "losses": losses, "total": total, "win_rate": round(win_rate, 1)}

    # Lọc theo thời gian
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    signals_today = [s for s in closed_signals if datetime.fromisoformat(s['timestamp']) >= today_start]
    signals_week = [s for s in closed_signals if datetime.fromisoformat(s['timestamp']) >= week_start]
    signals_month = [s for s in closed_signals if datetime.fromisoformat(s['timestamp']) >= month_start]

    stats = {
        "today": calculate_stats(signals_today),
        "week": calculate_stats(signals_week),
        "month": calculate_stats(signals_month)
    }
    
    return jsonify(stats)

@app.route('/api/vote/<signal_id>/<vote_type>', methods=['POST'])
def vote_signal(signal_id, vote_type):
    """API: Xử lý vote (Win/Lose) từ user"""
    if vote_type not in ['win', 'lose']:
        return jsonify({"error": "Vote không hợp lệ"}), 400
        
    user_ip = request.remote_addr # Lấy IP user
    
    with data_lock:
        data = load_data()
        signals = data.get("signals", [])
        
        signal_to_update = None
        for sig in signals:
            if sig['id'] == signal_id:
                signal_to_update = sig
                break
        
        if not signal_to_update:
            return jsonify({"error": "Không tìm thấy tín hiệu"}), 404
            
        # Kiểm tra IP đã vote chưa
        if user_ip in signal_to_update.get('voted_ips', []):
            return jsonify({"error": "Bạn đã vote cho tín hiệu này rồi"}), 403

        # Ghi nhận vote
        if vote_type == 'win':
            signal_to_update['votes_win'] = signal_to_update.get('votes_win', 0) + 1
        else:
            signal_to_update['votes_lose'] = signal_to_update.get('votes_lose', 0) + 1
            
        # Thêm IP vào danh sách đã vote
        signal_to_update.setdefault('voted_ips', []).append(user_ip)
        
        # Kiểm tra điều kiện đóng tín hiệu (ví dụ: > 5 votes)
        total_votes = signal_to_update['votes_win'] + signal_to_update['votes_lose']
        if total_votes >= 5: # Đóng tín hiệu sau 5 lượt vote
             signal_to_update['status'] = 'closed'
             
        save_data(data) # Lưu lại thay đổi
        
    logger.info(f"🗳️ Vote: {signal_id} - {vote_type} từ {user_ip}")
    return jsonify({
        "message": "Cảm ơn bạn đã vote!",
        "votes_win": signal_to_update['votes_win'],
        "votes_lose": signal_to_update['votes_lose'],
        "status": signal_to_update['status']
    })

# =============================================================================
# FLASK HTML ROUTES
# =============================================================================

@app.route('/')
def index():
    """Render trang chủ (index.html)"""
    return render_template('index.html')
    
@app.route('/api/debug')
def debug_info():
    """API debug để kiểm tra trạng thái hệ thống"""
    import threading
    import tempfile
    
    # Kiểm tra thread đang chạy
    threads = []
    for thread in threading.enumerate():
        threads.append({
            'name': thread.name,
            'daemon': thread.daemon,
            'alive': thread.is_alive()
        })
    
    info = {
        "service": "Trading Signals Website",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": "RENDER" if os.getenv('RENDER') else "LOCAL",
        "data_file": DATA_FILE,
        "file_exists": os.path.exists(DATA_FILE),
        "coins_count": len(COINS),
        "active_threads": threads,
        "temp_dir": tempfile.gettempdir(),
        "current_utc": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    }
    
    return jsonify(info)

@app.route('/api/test-scan')
def test_scan():
    """API để test scan thủ công"""
    try:
        logger.info("🧪 BẮT ĐẦU TEST SCAN THỦ CÔNG...")
        scan()
        return jsonify({"message": "✅ Test scan hoàn thành", "status": "success"})
    except Exception as e:
        logger.error(f"💥 Lỗi test scan: {e}")
        return jsonify({"error": str(e)}), 500
# =============================================================================
# MAIN EXECUTION - SỬA LẠI CHO RENDER
# =============================================================================

def run_scheduler():
    """
    Chạy BackgroundScheduler ở chế độ CRON.
    """
    try:
        logger.info("🎬 BẮT ĐẦU CHẠY SCHEDULER...")
        # Luôn chỉ định timezone là UTC để cron chạy đúng
        scheduler = BackgroundScheduler(timezone="UTC") 
        
        # Sử dụng 'cron' để đồng bộ với nến 15m
        scheduler.add_job(scan, 'cron', minute='1,16,31,46') 
        
        # Chạy lần quét đầu tiên ngay lập tức
        logger.info("🔍 Chạy lần quét đầu tiên (khởi động)...")
        scan()
        
        scheduler.start()
        logger.info(f"✅ SCHEDULER ĐÃ BẮT ĐẦU (Chạy cron vào các phút 1, 16, 31, 46 UTC)")
        
        # Giữ cho scheduler chạy
        while True:
            time.sleep(3600)
            
    except Exception as e:
        logger.error(f"💥 LỖI SCHEDULER: {e}")

# Chạy scheduler ngay khi import (cho Render)
import os
if os.getenv('RENDER'):
    logger.info("🚀 ĐANG TRÊN RENDER - KHỞI ĐỘNG SCHEDULER...")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
else:
    logger.info("🚀 ĐANG CHẠY LOCAL - CHUẨN BỊ SCHEDULER...")

if __name__ == "__main__":
    # Trên Render, cái này có thể không chạy (vì dùng gunicorn)
    # Nhưng chúng ta đã chạy scheduler ở trên rồi
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 KHỞI CHẠY FLASK SERVER tại http://0.0.0.0:{port}...")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
