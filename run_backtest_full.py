"""
Tüm Borsa İstanbul Backtest
Sadece en umut verici 2 eşiği (60+ ve 65+) test eder.
Süre: ~10-15 dakika
"""

import sys
import time
from datetime import datetime, timedelta
from universe import BIST_ALL
from backtester import run_backtest_for_ticker


def run_full_backtest(score_threshold: int, initial_capital: float, risk_pct: float,
                      start_str: str, end_str: str) -> dict:
    all_trades = []
    failed = []

    total = len(BIST_ALL)
    for i, ticker in enumerate(BIST_ALL):
        sys.stdout.write(f"\r  [{i+1}/{total}] {ticker:<12} ...      ")
        sys.stdout.flush()

        trades = run_backtest_for_ticker(
            ticker, start_str, end_str,
            initial_capital, risk_pct,
            score_threshold=score_threshold
        )
        if trades:
            all_trades.extend(trades)
        else:
            failed.append(ticker)

    print(f"\n  (Veri alinamayan/delisted: {len(failed)} hisse)")

    if not all_trades:
        return {'threshold': score_threshold, 'total_trades': 0, 'wins': 0,
                'losses': 0, 'win_rate': 0, 'net_pnl': 0, 'roi': 0,
                'avg_win': 0, 'avg_loss': 0, 'rr_actual': 0, 'ev': 0, 'trades': []}

    total_trades = len(all_trades)
    wins   = [t for t in all_trades if t['pnl'] > 0]
    losses = [t for t in all_trades if t['pnl'] <= 0]
    win_rate  = (len(wins) / total_trades) * 100
    net_pnl   = sum(t['pnl'] for t in all_trades)
    roi       = (net_pnl / initial_capital) * 100
    avg_win   = sum(t['pnl'] for t in wins)   / len(wins)   if wins   else 0
    avg_loss  = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    rr_actual = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    ev        = (win_rate/100) * avg_win + (1 - win_rate/100) * avg_loss

    # Gercekci ROI: gunluk 1 islem siniri
    real_trades = min(total_trades, 250)
    real_roi    = (real_trades * ev) / initial_capital * 100

    return {
        'threshold':    score_threshold,
        'total_trades': total_trades,
        'wins':         len(wins),
        'losses':       len(losses),
        'win_rate':     win_rate,
        'net_pnl':      net_pnl,
        'roi':          roi,
        'real_roi':     real_roi,
        'avg_win':      avg_win,
        'avg_loss':     avg_loss,
        'rr_actual':    rr_actual,
        'ev':           ev,
        'trades':       all_trades,
    }


def main():
    print("=" * 70)
    print("   📈 TÜM BORSA İSTANBUL — GEÇMİŞ VERİ TESTİ")
    print("=" * 70)

    end_date   = datetime.now()
    start_date = end_date - timedelta(days=365)
    start_str  = start_date.strftime('%Y-%m-%d')
    end_str    = end_date.strftime('%Y-%m-%d')

    initial_capital = 10_000.0
    risk_pct        = 2.0
    thresholds      = [60, 65]      # En iyi 2 esik

    print(f"  Test Dönemi  : {start_str}  →  {end_str}")
    print(f"  Evren        : Tüm BIST ({len(BIST_ALL)} hisse)")
    print(f"  Başlangıç    : {initial_capital:,.0f} TL  |  Risk: %{risk_pct}")
    print(f"  Test Eşikleri: {thresholds}")
    print("=" * 70)
    print("  ⏳ Bu test ~10-15 dakika sürecek, lütfen bekleyin...\n")

    all_results = []
    t0 = time.time()

    for threshold in thresholds:
        print(f"\n{'─'*70}")
        print(f"  🔍 Eşik {threshold}+ test ediliyor...")
        print(f"{'─'*70}")
        result = run_full_backtest(threshold, initial_capital, risk_pct, start_str, end_str)
        all_results.append(result)

        r = result
        print(f"\n  Eşik {r['threshold']}+ ÖZET:")
        print(f"    Toplam Sinyal    : {r['total_trades']:,}")
        print(f"    Kazanma Oranı    : %{r['win_rate']:.1f}")
        print(f"    İşlem Başı EV    : {r['ev']:+.1f} TL")
        print(f"    Gerçekçi Yıl. ROI: %{r['real_roi']:+.1f}  (günde 1 işlem sınırı)")

    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"  ✅ Tüm testler tamamlandı — {elapsed:.0f} saniye")
    print(f"{'=' * 70}")

    # Karşılaştırma
    print("\n📊 BIST 30 VS TÜM BIST KARŞILAŞTIRMASI:\n")
    print(f"  {'Evren':<18} | {'Eşik':<6} | {'Sinyal':<8} | {'Win%':<8} | {'EV/İşlem':<11} | {'Gerçek ROI'}")
    print("  " + "─" * 65)

    bist30_data = {
        60: (869,  57.2, 9.3,  23.3),
        65: (302,  55.0, 12.8, 31.9),
    }
    for r in all_results:
        b30 = bist30_data[r['threshold']]
        print(f"  {'BIST 30 (31 hisse)':<18} | {r['threshold']:>4}+ | {b30[0]:>7,} | %{b30[1]:>5.1f} | {b30[2]:>+9.1f} TL | %{b30[3]:>+.1f}")
        print(f"  {'Tüm BIST (244 hisse)':<18} | {r['threshold']:>4}+ | {r['total_trades']:>7,} | %{r['win_rate']:>5.1f} | {r['ev']:>+9.1f} TL | %{r['real_roi']:>+.1f}")
        print()

    # En iyi 5 hisse
    for r in all_results:
        if not r['trades']:
            continue
        from collections import defaultdict
        ticker_pnl = defaultdict(float)
        ticker_cnt = defaultdict(int)
        for t in r['trades']:
            ticker_pnl[t['ticker']] += t['pnl']
            ticker_cnt[t['ticker']] += 1

        top5 = sorted(ticker_pnl.items(), key=lambda x: x[1], reverse=True)[:5]
        bot5 = sorted(ticker_pnl.items(), key=lambda x: x[1])[:5]

        print(f"\n🏆 EN KÂRLI 5 HİSSE (Eşik {r['threshold']}+):")
        for ticker, pnl in top5:
            print(f"    {ticker:<12} → {ticker_pnl[ticker]:>+8.0f} TL  ({ticker_cnt[ticker]} işlem)")

        print(f"\n💔 EN ZARARLI 5 HİSSE (Eşik {r['threshold']}+):")
        for ticker, pnl in bot5:
            print(f"    {ticker:<12} → {ticker_pnl[ticker]:>+8.0f} TL  ({ticker_cnt[ticker]} işlem)")

    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
