# trading-signals-website/app.py

import os
import json
import threading
import logging
import time
import uuid
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
# Rất quan trọng vì Flask (web thread) và Scheduler (scan thread)
# sẽ cùng truy cập file signals.json
data_lock = threading.Lock()

# Đường dẫn file dữ liệu
DATA_FILE = os.path.join('data', 'signals.json')

# =============================================================================
# FILE STORAGE FUNCTIONS (Thread-safe)
# =============================================================================

def load_data():
    """Tải file JSON một cách an toàn (dùng trong lock)"""
    if not os.path.exists('data'):
        os.makedirs('data')
        
    if not os.path.exists(DATA_FILE):
        save_data({"signals": []})  # Tạo file nếu chưa có
        return {"signals": []}
    try:
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Lỗi đọc {DATA_FILE}: {e}. Tạo file mới.")
        save_data({"signals": []})
        return {"signals": []}

def save_data(data):
    """Lưu file JSON một cách an toàn (dùng trong lock)"""
    temp_file = f"{DATA_FILE}.tmp"
    try:
        with open(temp_file, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(temp_file, DATA_FILE)
    except Exception as e:
        logger.error(f"Lỗi lưu {DATA_FILE}: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

# =============================================================================
# BINANCE API & INDICATORS (Giữ nguyên từ code gốc)
# =============================================================================

def get_klines(symbol, max_retries=3):
    """Fetch klines from Binance Futures API with retry mechanism"""
    url = f"https://fapi.binance.com/fapi/v1/klines"
    params = { "symbol": symbol, "interval": INTERVAL, "limit": LIMIT }
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume", 
                "close_time", "quote_volume", "trades", "taker_buy_base", 
                "taker_buy_quote", "ignore"
            ])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            logger.info(f"✅ Fetched {len(df)} candles for {symbol}")
            return df
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}/{max_retries} failed for {symbol}: {e}")
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

# ... (Copy toàn bộ 16 hàm combo từ combo1 đến combo16 vào đây) ...
# ... (Tôi sẽ bỏ qua để tiết kiệm không gian, nhưng bạn PHẢI copy chúng vào) ...

# 
# def combo1_fvg_squeeze_pro(df): ...
# def combo2_macd_ob_retest(df): ...
# ...
# def combo16_rsi_extreme_bounce(df): ...
#

# Thêm 2 combo mới
def combo17_ema_stack_volume_confirmation(df):
    """
    COMBO 17: EMA Stack + Volume Confirmation
    """
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
    """
    COMBO 18: Support/Resistance Break + Retest
    """
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
            retest_confirmation = (last.low <= (resistance_level + last.atr * 0.2) and # Cho phép retest sâu hơn 1 chút
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
# UTILITY FUNCTIONS (Đã sửa đổi)
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
# MAIN SCANNING FUNCTION (Đã sửa đổi)
# =============================================================================

def scan():
    """Hàm quét chính - kiểm tra tất cả combo và lưu vào signals.json"""
    logger.info(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] 🔍 Bắt đầu chu kỳ quét...")
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
    
    # Tải dữ liệu tín hiệu HIỆN TẠI (một lần) để kiểm tra cooldown
    with data_lock:
        data = load_data()
        all_signals = data.get("signals", [])

    for coin in COINS:
        try:
            df = get_klines(coin)
            if df is None or len(df) < 200:
                logger.warning(f"⚠️ Không đủ dữ liệu cho {coin}")
                continue
            
            df = add_indicators(df.copy()) # Thêm .copy() để tránh SettingWithCopyWarning

            for combo_func in combos:
                try:
                    result = combo_func(df)
                    if result:
                        direction, entry, sl, tp, combo_name = result
                        
                        # 1. Kiểm tra Cooldown
                        if not check_cooldown(coin, combo_name, all_signals):
                            continue # Bỏ qua nếu đang trong cooldown

                        # 2. Tạo tín hiệu
                        signal_id = str(uuid.uuid4()) # Tạo ID duy nhất
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
                            "timestamp": now_utc.isoformat(), # Lưu giờ UTC theo chuẩn ISO
                            "status": "active", # 'active' hoặc 'closed'
                            "votes_win": 0,
                            "votes_lose": 0,
                            "voted_ips": [] # Ngăn chặn vote nhiều lần
                        }
                        
                        # 3. Lưu tín hiệu (Thread-safe)
                        with data_lock:
                            # Tải lại data để đảm bảo tính toàn vẹn
                            current_data = load_data()
                            current_data.setdefault("signals", []).append(new_signal)
                            save_data(current_data)
                            
                            # Cập nhật all_signals để check cooldown cho vòng lặp sau
                            all_signals.append(new_signal) 
                        
                        signals_found_this_run += 1
                        logger.info(f"✅ Tín hiệu MỚI: {coin} - {combo_name}")
                        
                        # Chỉ lấy 1 tín hiệu mỗi coin mỗi lần quét
                        break 
                except Exception as e:
                    logger.error(f"❌ Lỗi combo {combo_func.__name__} cho {coin}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Lỗi quét {coin}: {e}")

    logger.info(f"✅ Quét xong. Tìm thấy {signals_found_this_run} tín hiệu mới.")

# =============================================================================
# FLASK API ROUTES (Cung cấp data cho Frontend)
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
# FLASK HTML ROUTES (Trang web)
# =============================================================================

@app.route('/')
def index():
    """Render trang chủ (index.html)"""
    # index.html sẽ chứa cả dashboard và bảng tín hiệu
    return render_template('index.html')

# =g===========================================================================
# MAIN EXECUTION
# =============================================================================

# Hàm này được gọi bởi render.yaml (worker)
def run_scheduler():
    logger.info("🚀 Khởi chạy Background Scheduler...")
    scheduler = BackgroundScheduler()
    scheduler.add_job(scan, 'interval', minutes=SCAN_INTERVAL_MINUTES)
    
    # Chạy lần quét đầu tiên ngay lập tức
    logger.info("🔍 Chạy lần quét đầu tiên...")
    try:
        scan()
    except Exception as e:
        logger.error(f"❌ Lỗi quét lần đầu: {e}")
        
    scheduler.start()
    logger.info(f"✅ Scheduler đã bắt đầu (quét mỗi {SCAN_INTERVAL_MINUTES} phút)")
    
    # Giữ cho worker chạy
    try:
        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler đã dừng.")

# Hàm này được gọi khi chạy local hoặc bởi render.yaml (web)
if __name__ == "__main__":
    # Khi chạy local, chúng ta cần chạy cả web và scheduler
    # Khi deploy, Render sẽ chạy 2 tiến trình riêng biệt
    
    if os.getenv("RENDER"):
        # Nếu đang trên Render, Gunicorn sẽ chạy app
        logger.info("🚀 Đang chạy trên Render (chỉ khởi chạy web)...")
    else:
        # Nếu chạy local (python app.py)
        logger.info("🚀 Khởi chạy ở chế độ local (Web + Scheduler)...")
        # Chạy scheduler trong 1 thread riêng
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Chạy Flask web
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"🌐 Khởi chạy Flask server tại http://0.0.0.0:{port}...")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

