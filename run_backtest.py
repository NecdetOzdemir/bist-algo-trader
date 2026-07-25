"""
Backtest Çalıştırma Betiği — v2
Farklı skor eşiklerini karşılaştırır ve en iyi parametreyi bulur.
"""

import sys
import time
from datetime import datetime, timedelta
from universe import BIST_30
from backtester import run_backtest_for_ticker


def run_full_backtest(score_threshold: int, initial_capital: float, risk_pct: float,
                      start_str: str, end_str: str, verbose: bool = True) -> dict:
    """Tüm BIST 30 hisseleri üzerinde backtest koşar ve özet istatistikleri döner."""
    all_trades = []

    for i, ticker in enumerate(BIST_30):
        if verbose:
            sys.stdout.write(f"\r  [{i+1}/{len(BIST_30)}] {ticker} ...      ")
            sys.stdout.flush()

        trades = run_backtest_for_ticker(
            ticker, start_str, end_str,
            initial_capital, risk_pct,
            score_threshold=score_threshold
        )
        all_trades.extend(trades)

    if verbose:
        print()

    if not all_trades:
        return {
            'threshold':    score_threshold,
            'total_trades': 0,
            'wins':         0,
            'losses':       0,
            'win_rate':     0,
            'net_pnl':      0,
            'roi':          0,
            'avg_win':      0,
            'avg_loss':     0,
            'rr_actual':    0,
            'trades':       [],
        }

    total_trades  = len(all_trades)
    wins          = [t for t in all_trades if t['pnl'] > 0]
    losses        = [t for t in all_trades if t['pnl'] <= 0]
    win_rate      = (len(wins) / total_trades) * 100
    net_pnl       = sum(t['pnl'] for t in all_trades)
    roi           = (net_pnl / initial_capital) * 100
    avg_win       = sum(t['pnl'] for t in wins)  / len(wins)   if wins   else 0
    avg_loss      = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    rr_actual     = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    return {
        'threshold':    score_threshold,
        'total_trades': total_trades,
        'wins':         len(wins),
        'losses':       len(losses),
        'win_rate':     win_rate,
        'net_pnl':      net_pnl,
        'roi':          roi,
        'avg_win':      avg_win,
        'avg_loss':     avg_loss,
        'rr_actual':    rr_actual,
        'trades':       all_trades,
    }


def print_result(r: dict, initial_capital: float):
    emoji = "✅" if r['roi'] > 0 else "❌"
    print(f"  Eşik {r['threshold']:3d}+ | "
          f"İşlem: {r['total_trades']:4d} | "
          f"Win Rate: %{r['win_rate']:5.1f} | "
          f"R/R: 1:{r['rr_actual']:.2f} | "
          f"ROI: {r['roi']:+.1f}%  {emoji}")


def main():
    print("=" * 70)
    print("   📈 BIST TRADE ASİSTAN — GEÇMİŞ VERİ TESTİ v2 (PARAMETRE ARAMASI)")
    print("=" * 70)

    end_date   = datetime.now()
    start_date = end_date - timedelta(days=365)
    start_str  = start_date.strftime('%Y-%m-%d')
    end_str    = end_date.strftime('%Y-%m-%d')

    initial_capital = 10_000.0
    risk_pct        = 2.0

    # Test edilecek skor eşikleri
    thresholds = [50, 55, 60, 65, 70, 75]

    print(f"  Test Dönemi  : {start_str}  →  {end_str}")
    print(f"  Evren        : BIST 30 ({len(BIST_30)} hisse)")
    print(f"  Başlangıç    : {initial_capital:,.0f} TL")
    print(f"  Risk / İşlem : %{risk_pct}")
    print(f"  Skor Eşikleri: {thresholds}")
    print("=" * 70)

    all_results = []
    t0 = time.time()

    for threshold in thresholds:
        print(f"\n🔍 Eşik {threshold}+ test ediliyor...")
        result = run_full_backtest(threshold, initial_capital, risk_pct, start_str, end_str, verbose=True)
        all_results.append(result)
        print_result(result, initial_capital)

    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"  ✅ Tüm testler tamamlandı — {elapsed:.1f} saniye")
    print(f"{'=' * 70}")

    # Parametre Karşılaştırma Tablosu
    print("\n📊 PARAMETRE KARŞILAŞTIRMA TABLOSU:\n")
    print(f"  {'Eşik':>6} | {'İşlem':>6} | {'Kazanma':>10} | {'Orta.Kâr':>10} | {'Orta.Zarar':>12} | {'R/R':>6} | {'ROI':>8}")
    print("  " + "-" * 68)
    for r in all_results:
        print(f"  {r['threshold']:>4}+  | "
              f"{r['total_trades']:>6} | "
              f"{r['win_rate']:>9.1f}% | "
              f"{r['avg_win']:>+9.1f}₺ | "
              f"{r['avg_loss']:>+11.1f}₺ | "
              f"1:{r['rr_actual']:.2f} | "
              f"{r['roi']:>+7.1f}%")

    # En iyi eşiği belirle (ROI'ye göre)
    best = max(all_results, key=lambda x: x['roi'])
    print(f"\n🏆 EN İYİ EŞİK: {best['threshold']}+ skor")
    print(f"   → {best['total_trades']} işlem | %{best['win_rate']:.1f} kazanma | ROI: {best['roi']:+.1f}%")

    # En iyi eşiğin detaylı işlem listesi
    best_trades = best['trades']
    if best_trades:
        sorted_trades = sorted(best_trades, key=lambda x: x['pnl'], reverse=True)

        print(f"\n🏆 EN İYİ 5 İŞLEM (Eşik: {best['threshold']}+):")
        for t in sorted_trades[:5]:
            print(f"  {t['date']} | {t['ticker']:<12} | "
                  f"Giriş: {t['entry_price']:>8.2f} | Çıkış: {t['exit_price']:>8.2f} | "
                  f"Kâr/Zarar: {t['pnl']:>+8.2f} TL | Skor: {t['score']}")

        print(f"\n💔 EN KÖTÜ 5 İŞLEM (Eşik: {best['threshold']}+):")
        for t in sorted_trades[-5:]:
            print(f"  {t['date']} | {t['ticker']:<12} | "
                  f"Giriş: {t['entry_price']:>8.2f} | Çıkış: {t['exit_price']:>8.2f} | "
                  f"Kâr/Zarar: {t['pnl']:>+8.2f} TL | Skor: {t['score']}")

    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
