# trading-signals-website/config.py

import os

# =============================================================================
# CẤU HÌNH TRADING - ĐÃ TỐI ƯU
# =============================================================================

# Giữ 20 coins nhưng sắp xếp hợp lý hơn
COINS = [
    # Top 5 - Volume cao nhất, ít biến động mạnh
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    
    # Mid-cap - Tiềm năng tốt
    "SOLUSDT", "DOTUSDT", "LTCUSDT", "LINKUSDT", "AVAXUSDT",
    
    # Small-cap - Biến động mạnh (cẩn thận)
    "DOGEUSDT", "SHIBUSDT", "TRXUSDT", "NEARUSDT", "UNIUSDT",
    
    # Test coins - Để debug và kiểm tra
    "MATICUSDT", "ATOMUSDT", "FILUSDT", "ETCUSDT", "ALGOUSDT"
]

# Interval - Dùng 15m là tốt nhất cho swing trading
INTERVAL = os.getenv("INTERVAL", "15m")

# LIMIT - Tăng lên 500 để có đủ dữ liệu tính indicator
LIMIT = int(os.getenv("LIMIT", "500"))

# SQUEEZE_THRESHOLD - Điều chỉnh cho phù hợp
SQUEEZE_THRESHOLD = float(os.getenv("SQUEEZE_THRESHOLD", "0.015"))

# COOLDOWN - Giảm xuống còn 30 phút để không bỏ lỡ cơ hội
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "30"))

# SCAN_INTERVAL - Không dùng nữa (đã chuyển sang cron) nhưng giữ để tương thích
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))

# RISK - Giữ nguyên
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))

# =============================================================================
# CẤU HÌNH CHỈ BÁO KỸ THUẬT
# =============================================================================

# Ngưỡng RSI
RSI_OVERSOLD = 25
RSI_OVERBOUGHT = 75

# Tỷ lệ Risk:Reward mặc định
DEFAULT_RR_RATIO = 2.0

# Số nến tối thiểu để tính indicator
MIN_CANDLES = 200

# =============================================================================
# CẤU HÌNH WEBSITE - ĐÃ CẢI THIỆN MÔ TẢ
# =============================================================================

COMBO_DETAILS = {
    "FVG Squeeze Pro": """
    <strong>🎯 Chiến lược:</strong> Kết hợp Squeeze Momentum và FVG (Fair Value Gap)<br>
    <strong>📊 Tín hiệu:</strong> Breakout khỏi vùng nén Bollinger Bands với xác nhận volume<br>
    <strong>⚡ Điều kiện:</strong> 
    - BB Width < 0.015 & BB nằm trong Keltner Channel<br>
    - Volume spike > 130% MA20<br>
    - Giá trên EMA200 & RSI < 68<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:3
    """,
    
    "MACD Order Block Retest": """
    <strong>🎯 Chiến lược:</strong> MACD Cross kết hợp retest Order Block<br>
    <strong>📊 Tín hiệu:</strong> MACD cắt lên + giá retest vùng order block cũ<br>
    <strong>⚡ Điều kiện:</strong>
    - MACD histogram chuyển dương<br>
    - Giá retest order block trong phạm vi 0.5 ATR<br>
    - Volume > trung bình 110%<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:2.5
    """,
    
    "Stop Hunt Squeeze": """
    <strong>🎯 Chiến lược:</strong> Bắt điểm quét stop loss trong vùng squeeze<br>
    <strong>📊 Tín hiệu:</strong> Wick dài + breakout khỏi squeeze<br>
    <strong>⚡ Điều kiện:</strong>
    - BB Width < 0.015 (squeeze)<br>
    - Wick/body > 2 (stop hunt)<br>
    - Breakout khỏi BB<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:2.8
    """,
    
    "FVG EMA Pullback": """
    <strong>🎯 Chiến lược:</strong> Pullback về FVG kết hợp EMA cross<br>
    <strong>📊 Tín hiệu:</strong> Giá pullback về FVG + EMA 8 cắt lên EMA 21<br>
    <strong>⚡ Điều kiện:</strong>
    - FVG bullish trong 5 nến gần nhất<br>
    - EMA 8 > EMA 21 (golden cross)<br>
    - Giá chạm FVG zone<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:2
    """,
    
    "FVG + MACD Divergence": """
    <strong>🎯 Chiến lược:</strong> Phân kỳ MACD kết hợp FVG<br>
    <strong>📊 Tín hiệu:</strong> Hidden bullish divergence + FVG confirmation<br>
    <strong>⚡ Điều kiện:</strong>
    - MACD hist tăng nhưng giá giảm (divergence)<br>
    - FVG bullish trong 8 nến<br>
    - RSI < 30 (oversold)<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:2.5
    """,
    
    "Order Block + Liquidity Grab": """
    <strong>🎯 Chiến lược:</strong> Quét thanh khoản tại Order Block<br>
    <strong>📊 Tín hiệu:</strong> Wick dài + retest order block<br>
    <strong>⚡ Điều kiện:</strong>
    - Lower wick > 2.5x body<br>
    - Giá trên order block cũ<br>
    - MACD histogram > 0<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:1.8
    """,
    
    "Stop Hunt + FVG Retest": """
    <strong>🎯 Chiến lược:</strong> Stop hunt retest FVG<br>
    <strong>📊 Tín hiệu:</strong> Quét stop loss + retest FVG<br>
    <strong>⚡ Điều kiện:</strong>
    - Wick dài (stop hunt)<br>
    - FVG bullish trong 3 nến<br>
    - Giá retest FVG zone<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:1.5
    """,
    
    "FVG + MACD Hist Spike": """
    <strong>🎯 Chiến lược:</strong> FVG với MACD momentum mạnh<br>
    <strong>📊 Tín hiệu:</strong> FVG + MACD histogram tăng mạnh<br>
    <strong>⚡ Điều kiện:</strong>
    - MACD hist 3 nến liên tiếp tăng<br>
    - FVG bullish trong 5 nến<br>
    - Giá trên VWAP<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:2.5
    """,
    
    "OB + FVG Confluence": """
    <strong>🎯 Chiến lược:</strong> Vùng hợp lưu Order Block và FVG<br>
    <strong>📊 Tín hiệu:</strong> Order Block và FVG trùng nhau<br>
    <strong>⚡ Điều kiện:</strong>
    - OB và FVG cách nhau < 0.5 ATR<br>
    - Bullish engulfing pattern<br>
    - Volume > 150% trung bình<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:2
    """,
    
    "SMC Ultimate": """
    <strong>🎯 Chiến lược:</strong> Smart Money Concepts tổng hợp<br>
    <strong>📊 Tín hiệu:</strong> Kết hợp 5 yếu tố SMC<br>
    <strong>⚡ Điều kiện:</strong>
    - Squeeze + FVG + MACD tăng<br>
    - Wick dài (liquidity grab)<br>
    - Retest order block<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:3.5
    """,
    
    "FVG OB Liquidity Break": """
    <strong>🎯 Chiến lược:</strong> Break thanh khoản với FVG và OB<br>
    <strong>📊 Tín hiệu:</strong> Break high + FVG + volume spike<br>
    <strong>⚡ Điều kiện:</strong>
    - FVG bullish<br>
    - Break high 5 nến<br>
    - Volume > 150% MA20<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:2
    """,
    
    "Liquidity Grab FVG Retest": """
    <strong>🎯 Chiến lược:</strong> Quét thanh khoản retest FVG<br>
    <strong>📊 Tín hiệu:</strong> Wick dài + retest FVG + MACD tăng<br>
    <strong>⚡ Điều kiện:</strong>
    - Lower wick > 2.5x body<br>
    - FVG retest<br>
    - MACD hist tăng<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:1.8
    """,
    
    "FVG MACD Momentum Scalp": """
    <strong>🎯 Chiến lược:</strong> Scalping với FVG và MACD momentum<br>
    <strong>📊 Tín hiệu:</strong> FVG nhỏ + MACD momentum + low volatility<br>
    <strong>⚡ Điều kiện:</strong>
    - FVG recent (2 nến)<br>
    - MACD momentum tăng<br>
    - Giá trên VWAP<br>
    - ATR/Close < 2% (low vol)<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:1.2
    """,
    
    "OB Liquidity MACD Div": """
    <strong>🎯 Chiến lược:</strong> Order Block + Liquidity + MACD Divergence<br>
    <strong>📊 Tín hiệu:</strong> Quét thanh khoản + divergence + retest OB<br>
    <strong>⚡ Điều kiện:</strong>
    - Wick dài (liquidity grab)<br>
    - Bullish divergence MACD<br>
    - Giá trên order block<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:2.5
    """,
    
    "VWAP EMA Volume Scalp": """
    <strong>🎯 Chiến lược:</strong> Scalping với VWAP, EMA cross và volume<br>
    <strong>📊 Tín hiệu:</strong> EMA cross + trên VWAP + volume spike<br>
    <strong>⚡ Điều kiện:</strong>
    - EMA 8 cắt lên EMA 21<br>
    - Giá trên VWAP<br>
    - Volume > 180% MA20<br>
    - RSI < 60<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:1
    """,
    
    "RSI Extreme Bounce": """
    <strong>🎯 Chiến lược:</strong> Bắt đảo chiều tại vùng RSI cực đoạn<br>
    <strong>📊 Tín hiệu:</strong> RSI oversold/overbought + reversal pattern<br>
    <strong>⚡ Điều kiện:</strong>
    - RSI < 25 (long) hoặc > 75 (short)<br>
    - Bullish/bearish engulfing hoặc Hammer/Shooting star<br>
    - Volume > 120% MA20<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:1.5
    """,
    
    "EMA Stack Volume Confirmation": """
    <strong>🎯 Chiến lược:</strong> Trend following với EMA stack<br>
    <strong>📊 Tín hiệu:</strong> EMA stack + pullback + volume confirmation<br>
    <strong>⚡ Điều kiện:</strong>
    - EMA 8 > 21 > 50 > 200 (stack)<br>
    - Giá trên tất cả EMA<br>
    - Pullback về EMA 8/21<br>
    - Volume > 150% MA20<br>
    - RSI < 65<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:1.8
    """,
    
    "Resistance Break Retest": """
    <strong>🎯 Chiến lược:</strong> Breakout và retest kháng cự/hỗ trợ<br>
    <strong>📊 Tín hiệu:</strong> Break resistance/support + retest thành công<br>
    <strong>⚡ Điều kiện:</strong>
    - Break level quan trọng<br>
    - Retest level đó<br>
    - Volume > 180% MA20<br>
    - MACD confirmation<br>
    <strong>🎲 Tỷ lệ RR:</strong> 1:2
    """
}
