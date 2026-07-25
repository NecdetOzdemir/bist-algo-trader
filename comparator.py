"""
Hisse Karşılaştırma Modülü — İki hisseyi yan yana analiz eder.
Hangisi daha iyi? Neden? Açık ve net şekilde söyler.
"""

from data_fetcher import get_daily_data
from indicators import compute_all
from scorer import score_stock
from universe import get_display_name, get_sector, normalize_ticker


def compare(ticker1: str, ticker2: str) -> dict:
    """
    İki hisseyi karşılaştırır ve hangisinin daha iyi olduğunu söyler.
    
    Returns:
        Karşılaştırma raporu + kazanan + neden
    """
    t1 = normalize_ticker(ticker1)
    t2 = normalize_ticker(ticker2)
    b1 = t1.replace('.IS', '')
    b2 = t2.replace('.IS', '')

    # Her iki hisse için veri çek
    df1 = get_daily_data(t1, period="6mo")
    df2 = get_daily_data(t2, period="6mo")

    result = {
        'ticker1': b1,
        'ticker2': b2,
        'name1': get_display_name(t1),
        'name2': get_display_name(t2),
        'sector1': get_sector(t1),
        'sector2': get_sector(t2),
        'error': None,
        'winner': None,
        'winner_reasons': [],
        'comparison': {},
    }

    # Veri kontrolü
    if df1 is None or len(df1) < 20:
        result['error'] = f"'{b1}' için yeterli veri bulunamadı."
        return result
    if df2 is None or len(df2) < 20:
        result['error'] = f"'{b2}' için yeterli veri bulunamadı."
        return result

    # İndikatörleri hesapla
    ind1 = compute_all(df1)
    ind2 = compute_all(df2)

    if not ind1 or not ind2:
        result['error'] = "İndikatör hesaplanamadı."
        return result

    # Skorları hesapla
    s1 = score_stock(ind1)
    s2 = score_stock(ind2)

    # Karşılaştırma tablosu
    comparison = {
        'total_score': {
            'label': 'Genel Skor',
            'val1':  s1['total'],
            'val2':  s2['total'],
            'unit':  '/100',
            'winner': 1 if s1['total'] > s2['total'] else (2 if s2['total'] > s1['total'] else 0),
        },
        'trend': {
            'label': 'Trend Skoru',
            'val1':  s1['trend'],
            'val2':  s2['trend'],
            'unit':  '/20',
            'winner': 1 if s1['trend'] > s2['trend'] else (2 if s2['trend'] > s1['trend'] else 0),
        },
        'volume': {
            'label': 'Hacim Kalitesi',
            'val1':  s1['volume'],
            'val2':  s2['volume'],
            'unit':  '/20',
            'winner': 1 if s1['volume'] > s2['volume'] else (2 if s2['volume'] > s1['volume'] else 0),
        },
        'rr': {
            'label': 'Risk/Ödül',
            'val1':  s1['rr'],
            'val2':  s2['rr'],
            'unit':  '/20',
            'winner': 1 if s1['rr'] > s2['rr'] else (2 if s2['rr'] > s1['rr'] else 0),
        },
        'momentum': {
            'label': 'Momentum',
            'val1':  s1['momentum'],
            'val2':  s2['momentum'],
            'unit':  '/20',
            'winner': 1 if s1['momentum'] > s2['momentum'] else (2 if s2['momentum'] > s1['momentum'] else 0),
        },
        'pivot': {
            'label': 'Pivot Konumu',
            'val1':  s1['pivot'],
            'val2':  s2['pivot'],
            'unit':  '/20',
            'winner': 1 if s1['pivot'] > s2['pivot'] else (2 if s2['pivot'] > s1['pivot'] else 0),
        },
        'price_change_1d': {
            'label': 'Günlük Değişim',
            'val1':  ind1.get('price_change_1d', 0),
            'val2':  ind2.get('price_change_1d', 0),
            'unit':  '%',
            'winner': 1 if ind1.get('price_change_1d', 0) > ind2.get('price_change_1d', 0) else 2,
        },
        'rsi': {
            'label': 'RSI',
            'val1':  ind1.get('rsi', 50),
            'val2':  ind2.get('rsi', 50),
            'unit':  '',
            'note':  '45-60 arası ideal',
            # RSI için hangisi daha sağlıklı aralıkta
            'winner': _rsi_winner(ind1.get('rsi', 50), ind2.get('rsi', 50)),
        },
        'volume_ratio': {
            'label': 'Hacim Oranı',
            'val1':  round(ind1.get('volume_ratio', 1.0), 2),
            'val2':  round(ind2.get('volume_ratio', 1.0), 2),
            'unit':  'x',
            'winner': 1 if ind1.get('volume_ratio', 1) > ind2.get('volume_ratio', 1) else 2,
        },
        'rr_ratio': {
            'label': 'R/R Oranı',
            'val1':  s1['targets'].get('rr_ratio', 0),
            'val2':  s2['targets'].get('rr_ratio', 0),
            'unit':  '',
            'winner': 1 if s1['targets'].get('rr_ratio', 0) > s2['targets'].get('rr_ratio', 0) else 2,
        },
        'atr_pct': {
            'label': 'Volatilite (ATR%)',
            'val1':  ind1.get('atr_pct', 0),
            'val2':  ind2.get('atr_pct', 0),
            'unit':  '%',
            'note':  'Düşük = daha kontrollü',
            'winner': 1 if ind1.get('atr_pct', 0) < ind2.get('atr_pct', 0) else 2,
        },
        'vwap_status': {
            'label': 'VWAP Durumu',
            'val1':  'Üstünde' if ind1.get('above_vwap') else 'Altında',
            'val2':  'Üstünde' if ind2.get('above_vwap') else 'Altında',
            'unit':  '',
            'winner': 1 if ind1.get('above_vwap') and not ind2.get('above_vwap') else
                      2 if ind2.get('above_vwap') and not ind1.get('above_vwap') else 0,
        },
    }

    result['comparison'] = comparison

    # Kazananı belirle
    score_diff = s1['total'] - s2['total']
    winner_reasons = []

    if abs(score_diff) < 5:
        # Çok yakın — detaylı inceleme
        result['winner'] = None
        result['winner_name'] = None
        result['winner_reasons'] = [
            "İki hisse birbirine çok yakın skor aldı.",
            "Risk/ödül oranı daha iyi olan tercih edilebilir.",
            f"{b1} R/R: 1:{s1['targets'].get('rr_ratio', 0):.1f} — {b2} R/R: 1:{s2['targets'].get('rr_ratio', 0):.1f}",
        ]
    elif score_diff > 0:
        result['winner'] = 1
        result['winner_name'] = b1
        winner_reasons = _build_winner_reasons(b1, b2, ind1, ind2, s1, s2)
        result['winner_reasons'] = winner_reasons
    else:
        result['winner'] = 2
        result['winner_name'] = b2
        winner_reasons = _build_winner_reasons(b2, b1, ind2, ind1, s2, s1)
        result['winner_reasons'] = winner_reasons

    # Her iki hissenin özet bilgisi
    result['stock1'] = {
        'ticker': b1,
        'price': ind1.get('current_price', 0),
        'change_1d': ind1.get('price_change_1d', 0),
        'score': s1['total'],
        'verdict': s1['verdict'],
        'color': s1['color'],
        'suitable': s1['suitable'],
        'targets': s1['targets'],
        'rsi': ind1.get('rsi', 0),
        'trend': ind1.get('trend', 'YATAY'),
        'above_vwap': ind1.get('above_vwap', False),
    }
    result['stock2'] = {
        'ticker': b2,
        'price': ind2.get('current_price', 0),
        'change_1d': ind2.get('price_change_1d', 0),
        'score': s2['total'],
        'verdict': s2['verdict'],
        'color': s2['color'],
        'suitable': s2['suitable'],
        'targets': s2['targets'],
        'rsi': ind2.get('rsi', 0),
        'trend': ind2.get('trend', 'YATAY'),
        'above_vwap': ind2.get('above_vwap', False),
    }

    return result


def _rsi_winner(rsi1: float, rsi2: float) -> int:
    """RSI için hangisi daha sağlıklı aralıkta?"""
    ideal = 52.5  # 45-60 arasının ortası
    dist1 = abs(rsi1 - ideal)
    dist2 = abs(rsi2 - ideal)
    if dist1 < dist2:
        return 1
    elif dist2 < dist1:
        return 2
    return 0


def _build_winner_reasons(winner: str, loser: str, w_ind: dict, l_ind: dict,
                           w_score: dict, l_score: dict) -> list:
    """Kazanan hisse için neden daha iyi olduğunu açıkla."""
    reasons = []
    score_diff = w_score['total'] - l_score['total']

    reasons.append(
        f"{winner} daha yüksek skor aldı ({w_score['total']}/100 vs {l_score['total']}/100)"
    )

    # Trend
    if w_score['trend'] > l_score['trend']:
        reasons.append(f"Trend skoru daha güçlü ({w_score['trend']} vs {l_score['trend']})")

    # R/R
    w_rr = w_score['targets'].get('rr_ratio', 0)
    l_rr = l_score['targets'].get('rr_ratio', 0)
    if w_rr > l_rr:
        reasons.append(f"Risk/Ödül oranı daha iyi (1:{w_rr:.1f} vs 1:{l_rr:.1f})")

    # RSI
    w_rsi = w_ind.get('rsi', 50)
    l_rsi = l_ind.get('rsi', 50)
    if 40 <= w_rsi <= 65 and not (40 <= l_rsi <= 65):
        reasons.append(f"RSI sağlıklı aralıkta ({w_rsi:.0f} vs {l_rsi:.0f})")

    # Hacim
    w_vol = w_ind.get('volume_ratio', 1)
    l_vol = l_ind.get('volume_ratio', 1)
    if w_vol > l_vol:
        reasons.append(f"Hacim oranı daha yüksek ({w_vol:.1f}x vs {l_vol:.1f}x)")

    # VWAP
    w_vwap = w_ind.get('above_vwap', False)
    l_vwap = l_ind.get('above_vwap', False)
    if w_vwap and not l_vwap:
        reasons.append("VWAP üzerinde (diğer hisse VWAP altında)")

    # MACD
    if w_ind.get('macd_bullish_cross') and not l_ind.get('macd_bullish_cross'):
        reasons.append("MACD Bullish Cross sinyali var!")

    return reasons
