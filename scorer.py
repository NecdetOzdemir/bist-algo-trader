"""
Puanlama Motoru — Her hisse 0-100 arası puanlanır.

5 Kategori × 20 puan:
1. Trend Gücü     (20p) — EMA ve VWAP konumu
2. Hacim Kalitesi  (20p) — VPA, volume artışı
3. Pivot Konumu   (20p) — Camarilla ve Floor Pivot
4. Risk/Ödül      (20p) — ATR bazlı R/R oranı
5. Momentum       (20p) — RSI ve MACD
"""

from indicators import compute_all, get_entry_targets


def score_stock(indicators: dict) -> dict:
    """
    Bir hissenin indikatörlerini alır ve 0-100 arası skor döndürür.
    
    Returns:
        {
            'total': 0-100,
            'trend': 0-20,
            'volume': 0-20,
            'pivot': 0-20,
            'rr': 0-20,
            'momentum': 0-20,
            'breakdown': {açıklamalar},
            'verdict': 'GÜÇLÜ' | 'ORTA' | 'ZAYIF',
            'color': 'green' | 'yellow' | 'red',
        }
    """
    if not indicators:
        return _empty_score()

    breakdown = {}

    # ── 1. Trend Gücü (20 puan) ──────────────────────────────
    trend_score = 0
    trend_reasons = []
    price = indicators.get('current_price', 0)
    ema9  = indicators.get('ema9', price)
    ema20 = indicators.get('ema20', price)
    ema50 = indicators.get('ema50', price)
    vwap  = indicators.get('vwap', price)
    trend = indicators.get('trend', 'YATAY')

    if price > ema9:
        trend_score += 5
        trend_reasons.append("Fiyat EMA9 üzerinde ✅")
    if price > ema20:
        trend_score += 5
        trend_reasons.append("Fiyat EMA20 üzerinde ✅")
    if ema9 > ema20:
        trend_score += 5
        trend_reasons.append("EMA9 > EMA20 (yükseliş trendi) ✅")
    if price > vwap:
        trend_score += 5
        trend_reasons.append("Fiyat VWAP üzerinde ✅")
    if price < ema9:
        trend_reasons.append("Fiyat EMA9 altında ⚠️")
    if price < ema20:
        trend_reasons.append("Fiyat EMA20 altında ⚠️")

    breakdown['trend'] = {
        'score': trend_score,
        'reasons': trend_reasons,
        'label': 'Trend Gücü'
    }

    # ── 2. Hacim Kalitesi (20 puan) ──────────────────────────
    volume_score = 0
    volume_reasons = []
    vol_ratio = indicators.get('volume_ratio', 1.0)
    price_change = indicators.get('price_change_1d', 0)
    obv_trend = indicators.get('obv_trend', 'YATAY')

    # Hacim artışı puanlaması
    if vol_ratio >= 2.0:
        volume_score += 12
        volume_reasons.append(f"Hacim ortalamanın %{vol_ratio:.0%} — Çok güçlü ✅")
    elif vol_ratio >= 1.5:
        volume_score += 9
        volume_reasons.append(f"Hacim ortalamanın %{vol_ratio:.0%} — Güçlü ✅")
    elif vol_ratio >= 1.2:
        volume_score += 6
        volume_reasons.append(f"Hacim ortalamanın %{vol_ratio:.0%} — Normal üstü")
    elif vol_ratio >= 0.8:
        volume_score += 3
        volume_reasons.append(f"Hacim ortalamanın %{vol_ratio:.0%} — Zayıf ⚠️")
    else:
        volume_reasons.append(f"Hacim ortalamanın %{vol_ratio:.0%} — Çok zayıf 🔴")

    # VPA: Hacim+Fiyat uyumu (Anna Coulling'den)
    if vol_ratio >= 1.2 and price_change > 0:
        volume_score += 8
        volume_reasons.append("Hacim+Fiyat uyumlu — Güçlü alım sinyali ✅")
    elif vol_ratio >= 1.2 and price_change < 0:
        volume_score += 2
        volume_reasons.append("Yüksek hacimde düşüş — Dikkatli ol ⚠️")
    elif vol_ratio < 0.8 and price_change > 0:
        volume_score += 2
        volume_reasons.append("Düşük hacimde yükseliş — Zayıf hareket ⚠️")
    else:
        volume_score += 4

    # OBV trend
    if obv_trend == 'YUKARI':
        volume_score += 0  # Zaten yukarıda puanlandı
        volume_reasons.append("OBV trendi yukarı ✅")

    volume_score = min(20, volume_score)

    breakdown['volume'] = {
        'score': volume_score,
        'reasons': volume_reasons,
        'label': 'Hacim Kalitesi'
    }

    # ── 3. Pivot Konumu (20 puan) ─────────────────────────────
    pivot_score = 0
    pivot_reasons = []
    cam = indicators.get('camarilla', {})
    fp  = indicators.get('floor_pivots', {})
    pivot_pos = indicators.get('pivot_position', '')

    if cam and fp:
        l3 = cam.get('L3', price)
        l4 = cam.get('L4', price)
        h3 = cam.get('H3', price)
        h4 = cam.get('H4', price)
        p  = fp.get('P', price)
        r1 = fp.get('R1', price)
        s1 = fp.get('S1', price)

        # L3 yakınında alım fırsatı
        l3_proximity = abs(price - l3) / price
        if l3_proximity < 0.01 and price >= l3:
            pivot_score = 20
            pivot_reasons.append("L3 Camarilla yakınında — En iyi alım bölgesi 🟢")
        elif price > l3 and price < p:
            pivot_score = 16
            pivot_reasons.append("L3-Pivot arası — İyi destek bölgesi ✅")
        elif price > p and price < r1:
            pivot_score = 12
            pivot_reasons.append("Pivot üstünde — Yükseliş potansiyeli var")
        elif price > r1 and price < h3:
            pivot_score = 8
            pivot_reasons.append("R1-H3 arası — Devam trendi")
        elif price > h4:
            pivot_score = 6
            pivot_reasons.append("H4 üstü — Kırılım yaşandı, riskli ⚠️")
        elif price < s1:
            pivot_score = 3
            pivot_reasons.append("S1 altı — Zayıf bölge 🔴")
        else:
            pivot_score = 10

        # CPR analizi
        cpr = indicators.get('cpr', {})
        if cpr.get('is_narrow') and abs(price - p) / price < 0.005:
            pivot_score = min(20, pivot_score + 4)
            pivot_reasons.append("Dar CPR — Güçlü trend günü bekleniyor ✅")

    breakdown['pivot'] = {
        'score': pivot_score,
        'reasons': pivot_reasons,
        'label': 'Pivot Konumu'
    }

    # ── 4. Risk/Ödül (20 puan) ───────────────────────────────
    rr_score = 0
    rr_reasons = []
    targets = get_entry_targets(indicators)
    rr = targets.get('rr_ratio', 0)

    if rr >= 3.0:
        rr_score = 20
        rr_reasons.append(f"Mükemmel R/R: 1:{rr:.1f} 🟢")
    elif rr >= 2.5:
        rr_score = 17
        rr_reasons.append(f"Çok iyi R/R: 1:{rr:.1f} ✅")
    elif rr >= 2.0:
        rr_score = 14
        rr_reasons.append(f"İyi R/R: 1:{rr:.1f} ✅")
    elif rr >= 1.5:
        rr_score = 10
        rr_reasons.append(f"Kabul edilebilir R/R: 1:{rr:.1f} ⚠️")
    elif rr >= 1.0:
        rr_score = 5
        rr_reasons.append(f"Düşük R/R: 1:{rr:.1f} — Daha iyi fırsat bekle ⚠️")
    else:
        rr_score = 0
        rr_reasons.append(f"R/R olumsuz: 1:{rr:.1f} — İşlem yapma 🔴")

    # ATR volatilite kontrolü
    atr_pct = indicators.get('atr_pct', 0)
    if atr_pct < 1.0:
        rr_reasons.append("ATR düşük — Az volatilite, dar stop kullanılabilir")
    elif atr_pct > 5.0:
        rr_score = max(0, rr_score - 3)
        rr_reasons.append(f"ATR yüksek (%{atr_pct:.1f}) — Yüksek volatilite, dikkat ⚠️")

    breakdown['rr'] = {
        'score': rr_score,
        'reasons': rr_reasons,
        'label': 'Risk/Ödül',
        'targets': targets,
    }

    # ── 5. Momentum (20 puan) ─────────────────────────────────
    momentum_score = 0
    momentum_reasons = []
    rsi_val  = indicators.get('rsi', 50)
    macd_val = indicators.get('macd', 0)
    signal   = indicators.get('macd_signal', 0)
    bull_cross = indicators.get('macd_bullish_cross', False)
    bear_cross = indicators.get('macd_bearish_cross', False)

    # RSI puanlaması
    if 45 <= rsi_val <= 60:
        momentum_score += 12
        momentum_reasons.append(f"RSI {rsi_val:.0f} — Sağlıklı momentum ✅")
    elif 35 <= rsi_val < 45:
        momentum_score += 10
        momentum_reasons.append(f"RSI {rsi_val:.0f} — Nötr, dönüş potansiyeli var")
    elif 60 < rsi_val <= 68:
        momentum_score += 8
        momentum_reasons.append(f"RSI {rsi_val:.0f} — Güçlü ama dikkat, aşırı alıma yakın")
    elif 30 <= rsi_val < 35:
        momentum_score += 7
        momentum_reasons.append(f"RSI {rsi_val:.0f} — Aşırı satım, dikkatli al")
    elif rsi_val > 68:
        momentum_score += 3
        momentum_reasons.append(f"RSI {rsi_val:.0f} — Aşırı alım, riskli ⚠️")
    else:
        momentum_score += 5
        momentum_reasons.append(f"RSI {rsi_val:.0f} — Aşırı satım bölgesi")

    # MACD puanlaması
    if bull_cross:
        momentum_score += 8
        momentum_reasons.append("MACD Bullish Cross — Güçlü alım sinyali 🚀")
    elif bear_cross:
        momentum_score -= 3
        momentum_reasons.append("MACD Bearish Cross — Dikkat ⚠️")
    elif macd_val > signal and macd_val > 0:
        momentum_score += 6
        momentum_reasons.append("MACD pozitif + sinyal üstü ✅")
    elif macd_val > signal and macd_val < 0:
        momentum_score += 4
        momentum_reasons.append("MACD toparlanıyor")
    elif macd_val < signal:
        momentum_score += 2
        momentum_reasons.append("MACD sinyal altında ⚠️")

    momentum_score = max(0, min(20, momentum_score))

    breakdown['momentum'] = {
        'score': momentum_score,
        'reasons': momentum_reasons,
        'label': 'Momentum (RSI/MACD)'
    }

    # ── Toplam skor ───────────────────────────────────────────
    total = trend_score + volume_score + pivot_score + rr_score + momentum_score
    total = max(0, min(100, total))

    if total >= 75:
        verdict = "GÜÇLÜ"
        color   = "green"
        label   = "Güçlü Sinyal 🟢"
        suitable = True
    elif total >= 50:
        verdict = "ORTA"
        color   = "yellow"
        label   = "Orta Sinyal 🟡"
        suitable = True
    else:
        verdict = "ZAYIF"
        color   = "red"
        label   = "Zayıf Sinyal 🔴"
        suitable = False

    return {
        'total':      total,
        'trend':      trend_score,
        'volume':     volume_score,
        'pivot':      pivot_score,
        'rr':         rr_score,
        'momentum':   momentum_score,
        'breakdown':  breakdown,
        'verdict':    verdict,
        'color':      color,
        'label':      label,
        'suitable':   suitable,
        'targets':    targets,
    }


def _empty_score() -> dict:
    """Veri yoksa boş skor döndür"""
    return {
        'total': 0, 'trend': 0, 'volume': 0, 'pivot': 0,
        'rr': 0, 'momentum': 0, 'breakdown': {},
        'verdict': 'VERİ YOK', 'color': 'gray',
        'label': 'Veri çekilemedi', 'suitable': False,
        'targets': {}
    }
