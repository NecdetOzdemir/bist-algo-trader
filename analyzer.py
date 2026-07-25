"""
Derinlemesine Hisse Analizi — Tek hisse için kapsamlı rapor üretir.
"""

from data_fetcher import get_daily_data
from indicators import compute_all
from scorer import score_stock
from universe import get_display_name, get_sector, normalize_ticker


def analyze(ticker: str) -> dict:
    """
    Tek hisse için tam analiz raporu üretir.
    Tarayıcıdan daha detaylı bilgi verir.
    """
    ticker = normalize_ticker(ticker)
    base   = ticker.replace('.IS', '')

    df = get_daily_data(ticker, period="6mo")
    if df is None or len(df) < 20:
        return {
            'error': True,
            'message': f"'{base}' için yeterli veri bulunamadı. Lütfen hisse kodunu kontrol edin.",
            'ticker': base,
        }

    indicators = compute_all(df)
    if not indicators:
        return {
            'error': True,
            'message': f"'{base}' için indikatör hesaplanamadı.",
            'ticker': base,
        }

    score = score_stock(indicators)

    # Durum özeti oluştur
    status_summary = _build_status_summary(indicators, score)

    # Geçmiş performans (son 5 ve 20 gün)
    recent_prices = df['Close'].tail(20).tolist()
    recent_dates  = [str(d.date()) for d in df.index.tolist()[-20:]]
    recent_volumes = df['Volume'].tail(20).tolist()

    # 52 haftalık yüksek/düşük
    high_52w = float(df['High'].max())
    low_52w  = float(df['Low'].min())
    from_high_52w = ((indicators['current_price'] - high_52w) / high_52w) * 100
    from_low_52w  = ((indicators['current_price'] - low_52w)  / low_52w)  * 100

    return {
        'error': False,
        'ticker': base,
        'name': get_display_name(ticker),
        'sector': get_sector(ticker),

        # Skor
        'score': score,

        # Teknik indikatörler
        'indicators': indicators,

        # Durum özeti
        'status_summary': status_summary,

        # Grafik verisi
        'chart': {
            'dates':   recent_dates,
            'prices':  [round(p, 2) for p in recent_prices],
            'volumes': [int(v) for v in recent_volumes],
        },

        # İstatistikler
        'stats': {
            'high_52w':       round(high_52w, 2),
            'low_52w':        round(low_52w, 2),
            'from_high_52w':  round(from_high_52w, 2),
            'from_low_52w':   round(from_low_52w, 2),
            'data_days':      len(df),
        },
    }


def _build_status_summary(indicators: dict, score: dict) -> dict:
    """
    Kullanıcıya anlamlı bir özet oluştur.
    Teknik dil değil, sade Türkçe açıklamalar.
    """
    positives = []
    warnings  = []
    signals   = []

    price     = indicators.get('current_price', 0)
    rsi       = indicators.get('rsi', 50)
    vwap      = indicators.get('vwap', price)
    vol_ratio = indicators.get('volume_ratio', 1.0)
    trend     = indicators.get('trend', 'YATAY')
    macd_cross = indicators.get('macd_bullish_cross', False)
    cam = indicators.get('camarilla', {})
    fp  = indicators.get('floor_pivots', {})
    above_vwap = indicators.get('above_vwap', False)

    # Trend analizi
    if trend == 'YUKARI':
        positives.append("Hisse yükseliş trendinde — EMA9 ve EMA20 üzerinde")
    elif trend == 'AŞAĞI':
        warnings.append("Hisse düşüş trendinde — Trade için dikkatli ol")
    else:
        warnings.append("Trend belirsiz — Güçlü sinyal bekle")

    # VWAP analizi
    if above_vwap:
        positives.append(f"Fiyat VWAP ({vwap:.2f} TL) üzerinde — Alıcılar kontrol ediyor")
    else:
        warnings.append(f"Fiyat VWAP ({vwap:.2f} TL) altında — Satıcılar baskın")

    # Hacim analizi
    if vol_ratio >= 1.5:
        positives.append(f"Hacim normalin {vol_ratio:.1f}x'i — Güçlü ilgi var")
    elif vol_ratio < 0.8:
        warnings.append(f"Hacim düşük (normalin {vol_ratio:.0%}'si) — İlgi yok")

    # RSI analizi
    if 40 <= rsi <= 65:
        positives.append(f"RSI {rsi:.0f} — Sağlıklı aralıkta, alım için uygun")
    elif rsi > 70:
        warnings.append(f"RSI {rsi:.0f} — Aşırı alım bölgesi, düzeltme riski")
    elif rsi < 30:
        signals.append(f"RSI {rsi:.0f} — Aşırı satım, potansiyel geri dönüş")

    # Pivot analizi
    if cam:
        l3 = cam.get('L3', 0)
        h3 = cam.get('H3', 0)
        if l3 > 0 and abs(price - l3) / price < 0.015:
            signals.append(f"Camarilla L3 ({l3:.2f} TL) yakınında — Klasik alım bölgesi")
        elif price > cam.get('H4', 0):
            warnings.append(f"H4 kırıldı ({cam.get('H4', 0):.2f} TL) — Mevcut pozisyonlar için güçlü ama yeni giriş riskli")

    # MACD analizi
    if macd_cross:
        signals.append("MACD Bullish Cross oluştu — Güçlü momentum sinyali")

    # Günlük trade uygunluğu
    suitable = score.get('suitable', False)
    total    = score.get('total', 0)

    if suitable and total >= 75:
        verdict_text = f"Bu hisse bugün günlük trade için GÜÇLÜ görünüyor (Skor: {total}/100). Risk/ödül oranı iyi."
    elif suitable:
        verdict_text = f"Bu hisse bugün için ORTA seviyede uygun (Skor: {total}/100). Dikkatli giriş yap."
    else:
        verdict_text = f"Bu hisse bugün günlük trade için UYGUN DEĞİL (Skor: {total}/100). Daha iyi fırsatları bekle."

    return {
        'verdict_text': verdict_text,
        'positives':    positives,
        'warnings':     warnings,
        'signals':      signals,
        'suitable':     suitable,
    }
