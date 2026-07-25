"""
Teknik indikatörler modülü
Andrew Aziz, Pivot Boss ve VPA kitaplarından alınan yöntemler.
"""

import pandas as pd
import numpy as np


# ──────────────────────────────────────────
# TREND İNDİKATÖRLERİ
# ──────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    """Üstel Hareketli Ortalama (EMA)"""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Basit Hareketli Ortalama (SMA)"""
    return series.rolling(window=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI (Relative Strength Index)
    30 altı: Aşırı satım | 70 üstü: Aşırı alım
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    MACD hesaplama
    Returns: (macd_line, signal_line, histogram)
    """
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Average True Range - Volatilite ölçüsü
    """
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    VWAP - Hacim Ağırlıklı Ortalama Fiyat
    Andrew Aziz: 'En önemli intraday indikatör'
    Günlük veri üzerinde rolling VWAP hesaplar.
    """
    typical = (high + low + close) / 3
    vwap_vals = (typical * volume).cumsum() / volume.cumsum()
    return vwap_vals


def rolling_vwap(high: pd.Series, low: pd.Series, close: pd.Series,
                 volume: pd.Series, period: int = 20) -> pd.Series:
    """
    Rolling VWAP - N günlük pencere üzerinde
    """
    typical = (high + low + close) / 3
    num = (typical * volume).rolling(period).sum()
    den = volume.rolling(period).sum()
    return num / (den + 1e-10)


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    On Balance Volume - Hacim bazlı trend göstergesi
    """
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (direction * volume).cumsum()


def volume_ratio(volume: pd.Series, avg_period: int = 20) -> pd.Series:
    """
    Bugünkü hacim / N günlük ortalama hacim
    > 1.5 güçlü sinyal
    """
    avg = volume.rolling(avg_period).mean()
    return volume / (avg + 1e-10)


# ──────────────────────────────────────────
# PİVOT SEVİYELERİ (Pivot Boss kitabından)
# ──────────────────────────────────────────

def floor_pivots(prev_high: float, prev_low: float, prev_close: float) -> dict:
    """
    Standart Floor Pivot seviyeleri
    Kaynak: Franklin O. Ochoa Jr. - Secrets of a Pivot Boss, Ch.5
    
    Formül:
    P  = (H + L + C) / 3
    R1 = 2P - L
    R2 = P + (H - L)
    R3 = H + 2(P - L)
    S1 = 2P - H
    S2 = P - (H - L)
    S3 = L - 2(H - P)
    """
    P = (prev_high + prev_low + prev_close) / 3
    R1 = 2 * P - prev_low
    R2 = P + (prev_high - prev_low)
    R3 = prev_high + 2 * (P - prev_low)
    S1 = 2 * P - prev_high
    S2 = P - (prev_high - prev_low)
    S3 = prev_low - 2 * (prev_high - P)
    return {
        'P':  round(P, 4),
        'R1': round(R1, 4),
        'R2': round(R2, 4),
        'R3': round(R3, 4),
        'S1': round(S1, 4),
        'S2': round(S2, 4),
        'S3': round(S3, 4),
    }


def camarilla_pivots(prev_high: float, prev_low: float, prev_close: float) -> dict:
    """
    Camarilla Pivot seviyeleri
    Kaynak: Franklin O. Ochoa Jr. - Secrets of a Pivot Boss, Ch.7
    
    Formül:
    RANGE = H - L
    H5 = (H/L) × C
    H4 = C + RANGE × 1.1/2
    H3 = C + RANGE × 1.1/4
    L3 = C - RANGE × 1.1/4
    L4 = C - RANGE × 1.1/2
    L5 = C - (H5 - C)
    
    Kullanım:
    - L3: Geri dönüş ALIŞ noktası
    - H3: Geri dönüş SATIŞ noktası
    - H4: Yukarı kırılım noktası (güçlü yükseliş)
    - L4: Aşağı kırılım noktası (düşüş sinyali)
    """
    RANGE = prev_high - prev_low
    H5 = (prev_high / prev_low) * prev_close if prev_low > 0 else prev_close
    H4 = prev_close + RANGE * 1.1 / 2
    H3 = prev_close + RANGE * 1.1 / 4
    H2 = prev_close + RANGE * 1.1 / 6
    H1 = prev_close + RANGE * 1.1 / 12
    L1 = prev_close - RANGE * 1.1 / 12
    L2 = prev_close - RANGE * 1.1 / 6
    L3 = prev_close - RANGE * 1.1 / 4
    L4 = prev_close - RANGE * 1.1 / 2
    L5 = prev_close - (H5 - prev_close)
    return {
        'H5': round(H5, 4),
        'H4': round(H4, 4),
        'H3': round(H3, 4),
        'H2': round(H2, 4),
        'H1': round(H1, 4),
        'L1': round(L1, 4),
        'L2': round(L2, 4),
        'L3': round(L3, 4),
        'L4': round(L4, 4),
        'L5': round(L5, 4),
    }


def central_pivot_range(prev_high: float, prev_low: float, prev_close: float) -> dict:
    """
    Merkezi Pivot Aralığı (CPR)
    Kaynak: Pivot Boss, Ch.6
    
    CPR dar → Güçlü trend günü beklenir
    CPR geniş → Yatay seyir beklenir
    """
    P = (prev_high + prev_low + prev_close) / 3
    TC = (prev_high + prev_low) / 2  # Top Central
    BC = 2 * P - TC                   # Bottom Central
    width = abs(TC - BC)
    width_pct = (width / prev_close) * 100 if prev_close > 0 else 0

    return {
        'P':  round(P, 4),
        'TC': round(TC, 4),
        'BC': round(BC, 4),
        'width': round(width, 4),
        'width_pct': round(width_pct, 4),
        'is_narrow': width_pct < 0.3,  # Dar CPR → trend günü
    }


# ──────────────────────────────────────────
# TAM ANALİZ (DataFrame'den)
# ──────────────────────────────────────────

def compute_all(df: pd.DataFrame) -> dict:
    """
    Bir hissenin tüm indikatörlerini hesaplar.
    df: günlük OHLCV DataFrame (Open, High, Low, Close, Volume)
    
    Returns: İndikatör değerlerini içeren dict
    """
    if df is None or len(df) < 20:
        return {}

    close  = df['Close']
    high   = df['High']
    low    = df['Low']
    volume = df['Volume']
    
    # Son değerler
    last_close  = float(close.iloc[-1])
    last_high   = float(high.iloc[-1])
    last_low    = float(low.iloc[-1])
    last_volume = float(volume.iloc[-1])

    # Önceki gün değerleri (pivot hesaplamaları için)
    prev_close  = float(close.iloc[-2])
    prev_high   = float(high.iloc[-2])
    prev_low    = float(low.iloc[-2])

    # EMA'lar
    ema9  = ema(close, 9)
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200) if len(df) >= 200 else None

    # RSI
    rsi14 = rsi(close, 14)

    # MACD
    macd_line, signal_line, histogram = macd(close)

    # ATR
    atr14 = atr(high, low, close, 14)

    # VWAP (rolling 20 gün)
    vwap20 = rolling_vwap(high, low, close, volume, 20)

    # Hacim oranı
    vol_ratio = volume_ratio(volume, 20)

    # OBV
    obv_line = obv(close, volume)

    # Pivot seviyeleri (önceki günün OHLC'si kullanılır)
    fp = floor_pivots(prev_high, prev_low, prev_close)
    cam = camarilla_pivots(prev_high, prev_low, prev_close)
    cpr = central_pivot_range(prev_high, prev_low, prev_close)

    # Son değerleri al
    last_ema9   = float(ema9.iloc[-1])
    last_ema20  = float(ema20.iloc[-1])
    last_ema50  = float(ema50.iloc[-1])
    last_ema200 = float(ema200.iloc[-1]) if ema200 is not None else None
    last_rsi    = float(rsi14.iloc[-1])
    last_macd   = float(macd_line.iloc[-1])
    last_signal = float(signal_line.iloc[-1])
    last_hist   = float(histogram.iloc[-1])
    last_atr    = float(atr14.iloc[-1])
    last_vwap   = float(vwap20.iloc[-1])
    last_vol_ratio = float(vol_ratio.iloc[-1])

    # Önceki MACD histogram (crossover tespiti için)
    prev_hist = float(histogram.iloc[-2]) if len(histogram) >= 2 else 0
    macd_bullish_cross = prev_hist < 0 and last_hist > 0
    macd_bearish_cross = prev_hist > 0 and last_hist < 0

    # Fiyat değişimleri
    price_change_1d = ((last_close - prev_close) / prev_close) * 100
    price_change_5d = ((last_close - float(close.iloc[-6])) / float(close.iloc[-6])) * 100 if len(df) >= 6 else 0
    price_change_20d = ((last_close - float(close.iloc[-21])) / float(close.iloc[-21])) * 100 if len(df) >= 21 else 0

    # Trend yönü belirle
    if last_close > last_ema9 > last_ema20:
        trend = "YUKARI"
    elif last_close < last_ema9 < last_ema20:
        trend = "AŞAĞI"
    else:
        trend = "YATAY"

    # VWAP durumu
    above_vwap = last_close > last_vwap

    # Pivot pozisyonu
    pivot_pos = _pivot_position(last_close, fp, cam)

    # ATR bazlı stop ve hedef
    stop_loss     = last_close - (1.5 * last_atr)
    take_profit   = last_close + (2.5 * last_atr)
    risk_reward   = (take_profit - last_close) / (last_close - stop_loss) if last_close > stop_loss else 0

    return {
        # Fiyat bilgisi
        'current_price':    round(last_close, 4),
        'prev_close':       round(prev_close, 4),
        'price_change_1d':  round(price_change_1d, 2),
        'price_change_5d':  round(price_change_5d, 2),
        'price_change_20d': round(price_change_20d, 2),
        'high_today':       round(last_high, 4),
        'low_today':        round(last_low, 4),
        'volume_today':     int(last_volume),

        # EMA
        'ema9':    round(last_ema9, 4),
        'ema20':   round(last_ema20, 4),
        'ema50':   round(last_ema50, 4),
        'ema200':  round(last_ema200, 4) if last_ema200 else None,

        # Momentum
        'rsi':              round(last_rsi, 2),
        'macd':             round(last_macd, 4),
        'macd_signal':      round(last_signal, 4),
        'macd_hist':        round(last_hist, 4),
        'macd_bullish_cross': macd_bullish_cross,
        'macd_bearish_cross': macd_bearish_cross,

        # Volatilite
        'atr':  round(last_atr, 4),
        'atr_pct': round((last_atr / last_close) * 100, 2),

        # VWAP
        'vwap':       round(last_vwap, 4),
        'above_vwap': above_vwap,

        # Hacim
        'volume_ratio': round(last_vol_ratio, 2),
        'obv_trend':    'YUKARI' if float(obv_line.iloc[-1]) > float(obv_line.iloc[-5]) else 'AŞAĞI',

        # Trend
        'trend': trend,

        # Pivot seviyeleri
        'floor_pivots':    fp,
        'camarilla':       cam,
        'cpr':             cpr,
        'pivot_position':  pivot_pos,

        # Al/Sat seviyeleri
        'suggested_entry':      round(last_close, 4),
        'suggested_stop_loss':  round(stop_loss, 4),
        'suggested_take_profit':round(take_profit, 4),
        'risk_reward_ratio':    round(risk_reward, 2),
    }


def _pivot_position(price: float, fp: dict, cam: dict) -> str:
    """
    Fiyatın pivot seviyeleri içindeki konumunu belirler.
    Kullanıcıya anlamlı bir pozisyon bilgisi verir.
    """
    if price >= cam['H4']:
        return "H4 ÜSTÜ — Kırılım Bölgesi 🚀"
    elif price >= cam['H3']:
        return "H3-H4 Arası — Direnç Bölgesi ⚠️"
    elif price >= fp['R1']:
        return "R1 Üstü — Güçlü Yükseliş"
    elif price >= fp['P']:
        return "Pivot Üstü — Nötr/Pozitif"
    elif price >= cam['L3']:
        return "L3-Pivot Arası — Destek Bölgesi"
    elif price >= cam['L4']:
        return "L3 Civarı — Potansiyel Alım 🟢"
    else:
        return "L4 Altı — Zayıf Bölge 🔴"


def get_entry_targets(indicators: dict, mode: str = 'normal') -> dict:
    """
    Pivot seviyelerine göre optimal giriş, stop ve hedef hesapla.
    Stop-loss her zaman giriş fiyatının ALTINDA olur.
    """
    cam = indicators.get('camarilla', {})
    fp  = indicators.get('floor_pivots', {})
    price = indicators.get('current_price', 0)
    atr_val = indicators.get('atr', price * 0.02)  # Fallback: %2 ATR

    if price <= 0:
        return {'entry': 0, 'stop': 0, 'target1': 0, 'target2': 0,
                'risk_per_share': 0, 'reward_per_share': 0, 'rr_ratio': 0}

    entry = price

    # ── Stop-Loss Belirleme ───────────────────────────────────────
    # ATR tabanlı stop-loss: giriş - 1.5 × ATR (her zaman giriş altında)
    stop_atr = entry - (1.5 * atr_val)

    # Camarilla L3/L4 bazlı stop (eğer giriş fiyatının altındaysa kullan)
    stop_cam = None
    if cam:
        l3 = cam.get('L3', 0)
        l4 = cam.get('L4', 0)
        # L3 eğer giriş fiyatının altındaysa stop olarak kullanılabilir
        if 0 < l3 < entry:
            stop_cam = l3 - atr_val * 0.1  # L3'ün biraz altı
        elif 0 < l4 < entry:
            stop_cam = l4

    # En kötü senaryo: ATR tabanlı stop
    # Eğer Camarilla L3 uygunsa onu kullan (daha teknik)
    if stop_cam is not None and stop_cam < entry:
        stop = max(stop_cam, stop_atr)  # İkisinden daha yakın olanı al
    else:
        stop = stop_atr

    # Stop'un gerçekten giriş altında olduğunu garantile
    stop = min(stop, entry - atr_val * 0.5)
    stop = max(stop, 0.01)

    # ── Hedef Fiyat Belirleme ─────────────────────────────────────
    # Floor Pivot R1 veya Camarilla H3 — hangisi daha yakınsa
    target_candidates = []

    if fp:
        r1 = fp.get('R1', 0)
        r2 = fp.get('R2', 0)
        if r1 > entry: target_candidates.append(r1)
        if r2 > entry: target_candidates.append(r2)

    if cam:
        h3 = cam.get('H3', 0)
        h4 = cam.get('H4', 0)
        if h3 > entry: target_candidates.append(h3)
        if h4 > entry: target_candidates.append(h4)

    if target_candidates:
        target_candidates.sort()
        target1 = target_candidates[0]  # En yakın hedef
        target2 = target_candidates[-1] if len(target_candidates) > 1 else target1 + atr_val
    else:
        target1 = entry + 2.0 * atr_val
        target2 = entry + 3.5 * atr_val

    # Hedefin giriş üstünde olduğunu garantile
    if target1 <= entry:
        target1 = entry + 2.0 * atr_val
    if target2 <= target1:
        target2 = target1 + atr_val

    # ── Risk/Ödül Hesabı ──────────────────────────────────────────
    risk    = entry - stop
    reward  = target1 - entry
    rr      = reward / risk if risk > 0 else 0

    return {
        'entry':             round(entry, 2),
        'stop':              round(stop, 2),
        'target1':           round(target1, 2),
        'target2':           round(target2, 2),
        'risk_per_share':    round(risk, 2),
        'reward_per_share':  round(reward, 2),
        'rr_ratio':          round(rr, 2),
    }
