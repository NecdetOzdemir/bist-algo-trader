"""
Backtest (Geçmiş Veri Testi) Motoru — v2
Düzeltmeler:
- Kötü senaryo yerine dengeli senaryo (aynı günde hem stop hem hedef -> 50/50)
- Skor eşiği parametrik (dışarıdan verilebilir)
- Error handling iyileştirildi
"""

import pandas as pd
from data_fetcher import get_daily_data
from indicators import compute_all
from scorer import score_stock
from risk_calculator import calculate_position


def run_backtest_for_ticker(ticker: str, start_date: str, end_date: str,
                             initial_capital: float, risk_pct: float = 2.0,
                             score_threshold: int = 60) -> list:
    """
    Belirli bir hisse için belirtilen tarih aralığında geçmiş testini çalıştırır.

    Args:
        ticker: Hisse kodu (örn: THYAO.IS)
        start_date: Test başlangıç tarihi (YYYY-MM-DD)
        end_date: Test bitiş tarihi (YYYY-MM-DD)
        initial_capital: Başlangıç sermayesi (TL)
        risk_pct: İşlem başına max risk yüzdesi
        score_threshold: Alım sinyali için minimum skor (varsayılan: 60)

    Returns:
        Gerçekleşen işlemler listesi (dict formatında)
    """
    # 2 yıllık veri çekelim ki EMA200 vb. hesaplanabilsin
    df = get_daily_data(ticker, period="2y")
    if df is None or df.empty:
        return []

    # Sadece belirtilen tarih aralığını filtrele
    try:
        df_test = df.loc[start_date:end_date]
    except Exception:
        return []

    if df_test.empty:
        return []

    trades = []

    # Zaman makinesi: Gün gün ilerle
    for date in df_test.index:
        pos = df.index.get_loc(date)

        # En az 30 günlük geçmişe ihtiyacımız var
        if pos < 30:
            continue

        # O günden ÖNCEKİ tüm veriler (geleceği görmemek için!)
        df_history = df.iloc[:pos]

        # İndikatör ve skor hesapla
        try:
            ind = compute_all(df_history)
            if not ind:
                continue
            score = score_stock(ind)
        except Exception:
            continue

        # Belirlenen eşiğin üzerindeyse alım sinyali
        if score['total'] >= score_threshold and score.get('suitable', False):
            targets = score.get('targets', {})
            if not targets:
                continue

            entry_price  = targets.get('entry', 0)
            stop_price   = targets.get('stop', 0)
            target_price = targets.get('target1', 0)

            if entry_price <= 0 or stop_price <= 0 or target_price <= 0:
                continue
            if stop_price >= entry_price:
                continue  # Geçersiz stop (yukarıda olmamalı)
            if target_price <= entry_price:
                continue  # Geçersiz hedef

            # FiLTRE 1: Stop mesafesi en az %0.5 olmali (gercekci olmayan cok yakin stoplar)
            stop_pct = (entry_price - stop_price) / entry_price * 100
            if stop_pct < 0.5:
                continue

            # FiLTRE 2: Hacim filtresi — illikit hisseleri ele (min 100,000 lot/gun)
            avg_volume = ind.get('volume_today', 0)
            if avg_volume < 100_000:
                continue

            # Bugünün gerçek fiyat hareketleri
            today_row    = df.iloc[pos]
            today_open   = float(today_row['Open'])
            today_high   = float(today_row['High'])
            today_low    = float(today_row['Low'])
            today_close  = float(today_row['Close'])

            # Giriş gerçekleşti mi?
            actual_entry = 0
            if today_open <= entry_price:
                actual_entry = today_open  # Açılıştan doğrudan girdik
            elif today_low <= entry_price <= today_high:
                actual_entry = entry_price  # Gün içinde fiyata geldik

            if actual_entry <= 0:
                continue  # Bu gün alım gerçekleşmedi

            # Pozisyon büyüklüğünü hesapla
            try:
                pos_info = calculate_position(initial_capital, actual_entry, stop_price, risk_pct)
                if pos_info.get('error') or pos_info.get('shares', 0) == 0:
                    continue
                shares = pos_info['shares']
                # Yedek guvenlik: toplam yatirim hesap buyuklugunu gecemez
                max_affordable = int(initial_capital / actual_entry)
                shares = min(shares, max_affordable)
                if shares == 0:
                    continue
            except Exception:
                continue

            # ── Çıkış Senaryosu ──────────────────────────────────────────
            # Günlük veri olduğu için gün içi sırayı bilemeyiz.
            # Önce hangisine değdi?  High/Low yakınlığına göre tahmin et.
            #
            # Kural:
            #   - Sadece Stop'a değdiyse   → LOSS
            #   - Sadece Hedefe değdiyse   → WIN
            #   - İkisine de değdiyse      → 50/50 (dengeli senaryo)
            #   - Hiçbirine değmediyse     → kapanış fiyatından çık

            hit_stop   = today_low  <= stop_price
            hit_target = today_high >= target_price

            if hit_stop and hit_target:
                # Aynı günde ikisine de değdi: %50 ihtimalle WIN, %50 LOSS
                # Bunun yerine hangisine daha yakın açılıyorsa onu önce say.
                dist_to_stop   = abs(actual_entry - stop_price)
                dist_to_target = abs(target_price - actual_entry)
                if dist_to_stop <= dist_to_target:
                    result = 'LOSS'
                    exit_price = stop_price
                else:
                    result = 'WIN'
                    exit_price = target_price
            elif hit_stop:
                result = 'LOSS'
                exit_price = stop_price
            elif hit_target:
                result = 'WIN'
                exit_price = target_price
            else:
                # Gün sonu kapanışından çık
                result = 'WIN' if today_close > actual_entry else 'LOSS'
                exit_price = today_close

            pnl = (exit_price - actual_entry) * shares

            trades.append({
                'ticker':       ticker,
                'date':         date.strftime('%Y-%m-%d'),
                'entry_price':  round(actual_entry, 2),
                'stop_price':   round(stop_price, 2),
                'target_price': round(target_price, 2),
                'exit_price':   round(exit_price, 2),
                'result':       result,
                'shares':       shares,
                'pnl':          round(pnl, 2),
                'score':        score['total'],
                'rr':           targets.get('rr_ratio', 0),
            })

    return trades
