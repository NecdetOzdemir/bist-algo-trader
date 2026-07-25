"""
Hisse Tarayıcı — Seçilen evreni tarar ve en iyi fırsatları sıralar.
"""

from data_fetcher import get_daily_data
from indicators import compute_all
from scorer import score_stock
from universe import get_universe, get_display_name, get_sector, normalize_ticker


def scan(universe_choice: str = 'bist30', top_n: int = 15) -> list:
    """
    Seçilen evreni tara, en yüksek skorlu hisseleri döndür.
    
    Args:
        universe_choice: 'bist30', 'bist100', 'bistall'
        top_n: Kaç sonuç döndürülsün
        
    Returns:
        Sıralı hisse listesi (score azalan sırada)
    """
    tickers = get_universe(universe_choice)
    results = []

    for ticker in tickers:
        try:
            df = get_daily_data(ticker, period="6mo")
            if df is None or len(df) < 20:
                continue

            indicators = compute_all(df)
            if not indicators:
                continue

            score = score_stock(indicators)
            base  = ticker.replace('.IS', '')

            results.append({
                'ticker':       base,
                'ticker_full':  ticker,
                'name':         get_display_name(ticker),
                'sector':       get_sector(ticker),
                'score':        score['total'],
                'verdict':      score['verdict'],
                'color':        score['color'],
                'label':        score['label'],
                'suitable':     score['suitable'],

                # Fiyat
                'price':        indicators.get('current_price', 0),
                'change_1d':    indicators.get('price_change_1d', 0),
                'change_5d':    indicators.get('price_change_5d', 0),
                'trend':        indicators.get('trend', 'YATAY'),
                'volume_ratio': indicators.get('volume_ratio', 1.0),

                # Al/Sat seviyeleri
                'entry':        score['targets'].get('entry', 0),
                'stop':         score['targets'].get('stop', 0),
                'target1':      score['targets'].get('target1', 0),
                'target2':      score['targets'].get('target2', 0),
                'rr_ratio':     score['targets'].get('rr_ratio', 0),

                # Skor detayları
                'score_trend':    score['trend'],
                'score_volume':   score['volume'],
                'score_pivot':    score['pivot'],
                'score_rr':       score['rr'],
                'score_momentum': score['momentum'],

                # Teknik değerler
                'rsi':          indicators.get('rsi', 0),
                'macd_cross':   indicators.get('macd_bullish_cross', False),
                'above_vwap':   indicators.get('above_vwap', False),
                'pivot_pos':    indicators.get('pivot_position', ''),
                'atr_pct':      indicators.get('atr_pct', 0),
            })

        except Exception as e:
            print(f"[Scanner] {ticker} taranamadı: {e}")
            continue

    # Skora göre sırala (yüksekten düşüğe)
    results.sort(key=lambda x: x['score'], reverse=True)

    # Sadece uygun olanları öne al (opsiyonel filtre)
    suitable = [r for r in results if r['suitable']]
    not_suitable = [r for r in results if not r['suitable']]

    ordered = suitable + not_suitable
    return ordered[:top_n]


def quick_check(ticker: str) -> dict:
    """
    Tek bir hisse için hızlı kontrol.
    Kullanıcı 'EREGL' yazarsa bu fonksiyon çağrılır.
    """
    ticker = normalize_ticker(ticker)

    df = get_daily_data(ticker, period="6mo")
    if df is None or len(df) < 20:
        return {
            'error': f"{ticker.replace('.IS', '')} için veri bulunamadı.",
            'ticker': ticker.replace('.IS', ''),
        }

    indicators = compute_all(df)
    if not indicators:
        return {
            'error': f"{ticker.replace('.IS', '')} indikatör hesaplanamadı.",
            'ticker': ticker.replace('.IS', ''),
        }

    score = score_stock(indicators)
    base  = ticker.replace('.IS', '')

    return {
        'ticker':   base,
        'name':     get_display_name(ticker),
        'sector':   get_sector(ticker),
        'score':    score,
        'indicators': indicators,
        'suitable': score['suitable'],
        'verdict':  score['verdict'],
    }
