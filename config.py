# trading-signals-website/config.py

import os

# =============================================================================
# Cấu hình Trading
# =============================================================================

# Giảm xuống 20 coins theo yêu cầu
COINS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", 
    "DOGEUSDT", "ADAUSDT", "TRXUSDT", "AVAXUSDT", "SHIBUSDT", 
    "LINKUSDT", "DOTUSDT", "NEARUSDT", "LTCUSDT", "UNIUSDT", 
    "PEPEUSDT", "ICPUSDT", "APTUSDT", "IMXUSDT", "INJUSDT"
]

INTERVAL = os.getenv("INTERVAL", "15m")
LIMIT = int(os.getenv("LIMIT", "300"))
SQUEEZE_THRESHOLD = float(os.getenv("SQUEEZE_THRESHOLD", "0.018"))
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "60"))
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "6"))
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))

# =============================================================================
# Cấu hình Website
# =============================================================================
# Thông tin combo (để hiển thị modal chi tiết trên web)
# (Bạn có thể tự mô tả chi tiết hơn cho từng combo ở đây)
COMBO_DETAILS = {
    "FVG Squeeze Pro": "Kết hợp Tqueeze (nén) và FVG. Tín hiệu vào lệnh khi giá breakout khỏi vùng nén, xác nhận bởi volume và FVG.",
    "MACD Order Block Retest": "Tìm kiếm tín hiệu MACD giao cắt lên tại vùng Order Block (khối lệnh) quan trọng đã được retest.",
    "Stop Hunt Squeeze": "Bắt tín hiệu 'stop hunt' (quét stoploss) trong điều kiện thị trường nén (squeeze), chờ đợi một cú breakout mạnh.",
    "FVG EMA Pullback": "Tín hiệu LONG khi giá pullback (điều chỉnh) về vùng FVG (khoảng trống giá) và đồng thời nhận được hỗ trợ từ các đường EMA (8, 21).",
    "FVG + MACD Divergence": "Tìm kiếm tín hiệu phân kỳ ẩn (divergence) của MACD trong khi giá đang hình thành một FVG, cho thấy khả năng đảo chiều hoặc tiếp diễn mạnh.",
    "Order Block + Liquidity Grab": "Tín hiệu dựa trên việc giá 'quét thanh khoản' (liquidity grab) bên dưới một vùng đáy cũ, sau đó phản ứng tăng giá tại một Order Block.",
    "Stop Hunt + FVG Retest": "Sau một cú quét stoploss (stop hunt), giá quay lại retest vùng FVG vừa tạo ra và cho tín hiệu tiếp diễn.",
    "FVG + MACD Hist Spike": "Tín hiệu vào lệnh khi có một FVG xuất hiện đồng thời với một cột MACD Histogram tăng đột biến, cho thấy momentum mạnh.",
    "OB + FVG Confluence": "Tín hiệu mạnh khi vùng Order Block và vùng FVG trùng nhau (confluence), giá phản ứng tại vùng hợp lưu này.",
    "SMC Ultimate": "Chiến lược SMC (Smart Money Concepts) tổng hợp: kết hợp Squeeze, FVG, MACD, Liquidity Grab và OB Retest để tìm điểm vào lệnh tối ưu.",
    "FVG OB Liquidity Break": "Giá phá vỡ (break) một vùng thanh khoản, sau đó retest lại vùng FVG hoặc Order Block trước khi tiếp diễn.",
    "Liquidity Grab FVG Retest": "Tương tự Combo 6 và 7, tập trung vào việc giá quét thanh khoản và ngay lập tức retest FVG.",
    "FVG MACD Momentum Scalp": "Scalping: Tín hiệu FVG nhỏ được xác nhận bởi momentum MACD (hist tăng) và giá nằm trên VWAP.",
    "OB Liquidity MACD Div": "Kết hợp 3 yếu tố: Giá quét thanh khoản tại vùng Order Block cũ, đồng thời xuất hiện phân kỳ MACD.",
    "VWAP EMA Volume Scalp": "Scalping: EMA 8 cắt lên EMA 21, giá trên VWAP và có volume tăng đột biến. Tín hiệu vào lệnh nhanh.",
    "RSI Extreme Bounce": "Bắt đáy/đỉnh: Tìm kiếm tín hiệu nến đảo chiều (Engulfing, Hammer) tại vùng RSI quá bán (< 25) hoặc quá mua (> 75).",
    "EMA Stack Volume Confirmation": "Tín hiệu trend-following: Các đường EMA (8, 21, 50, 200) xếp chồng theo thứ tự, giá pullback về EMA 8/21 và bật lên với volume lớn.",
    "Resistance Break Retest": "Giá phá vỡ (breakout) vùng kháng cự quan trọng, sau đó quay lại retest (biến kháng cự thành hỗ trợ) và đi lên, xác nhận bởi volume và MACD."
}
