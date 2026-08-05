import os
import sys
import json
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
from universe import BIST_100

# Sahte tarayici basligı (Cloud IP banini önler)
yf_session = requests.Session()
yf_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
})

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/scan')
def scan():
    """BIST100 hisselerini chunk'lar halinde tara, teknik skor ve pivot verileri döndür."""
    offset = int(request.args.get('offset', 0))
    limit  = int(request.args.get('limit', 15))
    chunk  = BIST_100[offset:offset + limit]
    results = []
    for tic in chunk:
        try:
            data = analyze(tic)
            if data:
                results.append(data)
        except Exception:
            pass
    return jsonify({
        'results':     results,
        'total':       len(BIST_100),
        'next_offset': offset + limit,
    })


@app.route('/market_status')
def market_status():
    """XU100 SMA50 durumunu kontrol et (Test C1 Filtresi)."""
    try:
        df = yf.download('XU100.IS', period='100d', progress=False, auto_adjust=True, session=yf_session)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df['Close'].astype(float)
        sma50 = close.rolling(50).mean()
        last_c = float(close.iloc[-1])
        last_s = float(sma50.iloc[-1])
        ok = last_c > last_s
        return jsonify({'ok': ok, 'close': round(last_c, 2), 'sma50': round(last_s, 2)})
    except Exception as e:
        return jsonify({'ok': True, 'error': str(e)}) # Hata olursa kısıtlamayalım

# ──────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ──────────────────────────────────────────────

def safe(v, decimals=4):
    """NaN / Inf kontrolü yaparak güvenli float döndür."""
    try:
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, decimals)
    except Exception:
        return None


def pivot_zone(price, s2, s1, pivot, r1, r2):
    """Fiyatın hangi pivot bölgesinde olduğunu döndür."""
    tol = 0.015  # %1.5 tolerans = "yakın" eşiği
    if price < s2 * (1 - tol):         return 'below_s2'
    if price <= s2 * (1 + tol):        return 'near_s2'      # S2 destek yakını
    if price < s1 * (1 - tol):         return 'between_s2_s1'
    if price <= s1 * (1 + tol):        return 'near_s1'      # S1 destek yakını
    if price < pivot * (1 - tol):      return 'below_pivot'  # Pivot altı destek bölgesi
    if price <= pivot * (1 + tol):     return 'near_pivot'   # Pivot çevresinde
    if price < r1 * (1 - tol):         return 'above_pivot'  # Normal bullish bölge
    if price <= r1 * (1 + tol):        return 'near_r1'      # R1 direnç yakını
    if price < r2:                      return 'above_r1'     # Direnç üstü
    return 'above_r2'                                         # Aşırı uzak


# ──────────────────────────────────────────────
# Ana analiz fonksiyonu
# ──────────────────────────────────────────────

def analyze(ticker):
    tic = ticker if ticker.endswith('.IS') else ticker + '.IS'

    df = yf.download(tic, period='100d', progress=False,
                     auto_adjust=True, session=yf_session)
    if df is None or len(df) < 60:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.copy()
    close = df['Close'].astype(float)
    high  = df['High'].astype(float)
    low   = df['Low'].astype(float)
    vol   = df['Volume'].astype(float)

    # ── Hareketli Ortalamalar ──
    sma20  = close.rolling(20).mean()
    sma50  = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    # ── RSI (14) ──
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi_s = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # ── MACD (12, 26, 9) ──
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_sig  = macd_line.ewm(span=9, adjust=False).mean()

    # ── ATR (14) ──
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr_s = tr.rolling(14).mean()

    # ── ADX (14) — manuel hesaplama ──
    up_move   = high.diff()
    down_move = -low.diff()
    plus_dm   = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm  = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    plus_di   = 100 * plus_dm.rolling(14).mean()  / (atr_s + 1e-9)
    minus_di  = 100 * minus_dm.rolling(14).mean() / (atr_s + 1e-9)
    dx        = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    adx_s     = dx.rolling(14).mean()

    # ── Bollinger Bantları (20, 2σ) ──
    bb_mid   = close.rolling(20).mean()
    bb_std   = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_pct_s = (close - bb_lower) / (bb_upper - bb_lower + 1e-9)

    # ── Relatif Hacim ──
    vol_avg  = vol.rolling(10).mean()
    rvol_s   = vol / (vol_avg + 1e-9)

    # ── Son değerleri al ──
    if len(df) < 2:
        return None

    last  = df.iloc[-1]
    prev  = df.iloc[-2]

    price = safe(last['Close'], 2)
    if not price:
        return None

    rsi    = safe(rsi_s.iloc[-1],   1)
    atr    = safe(atr_s.iloc[-1],   4)
    adx    = safe(adx_s.iloc[-1],   1)
    rvol   = safe(rvol_s.iloc[-1],  2)
    sma20v = safe(sma20.iloc[-1],   2)
    sma50v = safe(sma50.iloc[-1],   2)
    sma200v= safe(sma200.iloc[-1],  2)
    macd_v = safe(macd_line.iloc[-1], 6)
    macd_sv= safe(macd_sig.iloc[-1],  6)
    bb_pct_v = safe(bb_pct_s.iloc[-1], 4)
    bb_low_v = safe(bb_lower.iloc[-1], 2)
    bb_up_v  = safe(bb_upper.iloc[-1], 2)

    if not all([rsi, atr, adx, rvol, sma50v]):
        return None

    # ── ATR% filtresi: %1.5 – %4.5 ──
    atr_pct = (atr / price) * 100
    if atr_pct < 1.5 or atr_pct > 4.5:
        return None

    # ── 5 günlük momentum ──
    mom_5d = 0.0
    if len(close) >= 6:
        p5 = safe(close.iloc[-6], 4)
        if p5:
            mom_5d = round((price - p5) / p5 * 100, 2)

    # ── Pivot Noktaları (önceki günden) ──
    ph = float(prev['High'])
    pl = float(prev['Low'])
    pc = float(prev['Close'])
    pv = round((ph + pl + pc) / 3, 2)
    r1 = round(2 * pv - pl, 2)
    r2 = round(pv + (ph - pl), 2)
    s1 = round(2 * pv - ph, 2)
    s2 = round(pv - (ph - pl), 2)

    zone = pivot_zone(price, s2, s1, pv, r1, r2)

    # ── SKORLAMA (0–8) ──
    score = 0
    # 1. Ana trend
    if sma50v and sma200v and sma50v > sma200v:         score += 1
    # 2. Kısa trend
    if sma20v and price > sma20v:                        score += 1
    # 3. RSI (ideal zone = +2, toparlanma = +1)
    if rsi:
        if 40 <= rsi <= 65:                              score += 2
        elif 30 <= rsi < 40:                             score += 1
    # 4. MACD pozitif yön
    if macd_v and macd_sv and macd_v > macd_sv:         score += 1
    # 5. Yüksek hacim
    if rvol and rvol >= 1.3:                             score += 1
    # 6. ADX — trend güçlü
    if adx and adx >= 20:                                score += 1
    # 7. 5 günlük momentum — henüz aşırı alım yok
    if 2.0 <= mom_5d <= 15.0:                            score += 1

    # ── SMA trend etiketi ──
    if sma50v and sma200v:
        if sma50v > sma200v and price > sma50v:     sma_trend = 'strong_up'
        elif price > sma50v:                          sma_trend = 'up'
        elif price < sma50v and sma50v < sma200v:   sma_trend = 'strong_down'
        else:                                         sma_trend = 'down'
    else:
        sma_trend = 'unknown'

    macd_bull = bool(macd_v and macd_sv and macd_v > macd_sv)
    is_trailing = bool(adx and adx >= 25 and sma_trend == 'strong_up' and macd_bull)
    trailing_stop = round(price - (atr * 2.5), 2) if atr else None

    # Dinamik Risk/Kazanc Hesaplamasi (ATR Tabanli)
    risk_pct = max(2.0, min(atr_pct * 1.2, 5.0)) if atr_pct else 3.0
    stop_p = round(price * (1 - (risk_pct / 100)), 2)
    reward_mult = 3.0 if score >= 6 else 2.0
    target_pct = risk_pct * reward_mult
    target_p = round(price * (1 + (target_pct / 100)), 2)

    return {
        'ticker':     ticker.replace('.IS', ''),
        'price':      price,
        'score':      score,
        'score_max':  8,
        'rsi':        rsi,
        'atr_pct':    round(atr_pct, 2),
        'adx':        adx,
        'rvol':       rvol,
        'mom_5d':     mom_5d,
        'bb_pct':     round(bb_pct_v * 100, 1) if bb_pct_v is not None else None,
        'bb_lower':   bb_low_v,
        'bb_upper':   bb_up_v,
        'sma20':      sma20v,
        'sma50':      sma50v,
        'sma200':     sma200v,
        'sma_trend':  sma_trend,
        'macd_bull':  macd_bull,
        'is_trailing': is_trailing,
        'trailing_stop': trailing_stop,
        'pivot':      pv,
        's1':         s1,
        's2':         s2,
        'r1':         r1,
        'r2':         r2,
        'pivot_zone': zone,
        'stop':       stop_p,
        'stop_pct':   round(risk_pct, 1),
        'target':     target_p,
        'target_pct': round(target_pct, 1),
    }


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
