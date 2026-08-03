"""
BIST AI Trader - Geçmiş Veri Backtest Scripti
=============================================
Bu script, Sabah Planı sisteminin 2024-2025 verilerinde
gerçekte ne kadar başarılı olduğunu test eder.

Çalıştırmak için:
    python3 backtest.py

Gerekli paketler (requirements.txt'te zaten var):
    pip install yfinance pandas ta numpy
"""

import yfinance as yf
import pandas as pd
import numpy as np
import ta
import warnings
import sys
import os
from datetime import datetime

warnings.filterwarnings('ignore')

# Hisse listesini buradan al
sys.path.insert(0, os.path.dirname(__file__))
try:
    from universe import BIST_100
except ImportError:
    print("universe.py bulunamadi. Script'i proje klasoründen calistirin.")
    sys.exit(1)

# -------------------------------------------------
# PARAMETRELER — Degistirip test edebilirsin
# -------------------------------------------------
START_DATE      = "2024-06-01"   # Backtest baslangic tarihi
END_DATE        = "2025-07-31"   # Backtest bitis tarihi  
DATA_START      = "2023-07-01"   # Veri baslangici (SMA200 icin fazladan gerekli)
ATR_STOP_MULT   = 1.5            # Stop  = Giris - 1.5xATR
ATR_TP_MULT     = 3.0            # Hedef = Giris + 3.0xATR  ->  RR her zaman 1:2
MIN_COMP_SCORE  = 5              # Kac puan uzerindeki hisseler alinsin (0-10)
MAX_HOLD_DAYS   = 15             # Kac gunde sonuc cikmaz ise pozisyonu kapat
# -------------------------------------------------


def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if len(df) < 210:
        return pd.DataFrame()

    macd_ind       = ta.trend.MACD(close=df['Close'])
    df['macd']     = macd_ind.macd()
    df['macd_sig'] = macd_ind.macd_signal()
    df['rsi'] = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()
    df['atr'] = ta.volatility.AverageTrueRange(
        high=df['High'], low=df['Low'], close=df['Close'], window=14
    ).average_true_range()
    df['sma50']  = df['Close'].rolling(50).mean()
    df['sma200'] = df['Close'].rolling(200).mean()
    df['vol_sma10'] = df['Volume'].rolling(10).mean()
    df['rel_vol']   = df['Volume'] / (df['vol_sma10'] + 1e-9)
    return df.dropna(subset=['macd', 'rsi', 'atr', 'sma50', 'sma200'])


def composite_score(row) -> int:
    comp = 0
    close = row['Close']
    if close > row['sma200']:        comp += 1
    if close > row['sma50']:         comp += 1
    if row['sma50'] > row['sma200']: comp += 1
    rsi = row['rsi']
    if 40 <= rsi <= 65:              comp += 2
    elif 30 <= rsi < 40:             comp += 1
    if row['macd'] > row['macd_sig']: comp += 1
    if row['rel_vol'] >= 1.20:       comp += 1
    return comp   # max 7 (AI modeli yok, web'de max 10)


def sma_trend(row) -> str:
    close = row['Close']
    if close > row['sma50'] and row['sma50'] > row['sma200']:
        return 'strong_up'
    if close > row['sma50']:
        return 'up'
    return 'down'


def backtest_stock(ticker: str) -> list:
    tic = ticker if ticker.endswith('.IS') else ticker + '.IS'
    try:
        raw = yf.download(tic, start=DATA_START, end=END_DATE,
                          progress=False, auto_adjust=True)
    except Exception:
        return []
    if raw is None or raw.empty:
        return []
    df = calc_indicators(raw)
    if df.empty:
        return []
    df = df.reset_index()
    df['Date'] = pd.to_datetime(df['Date'])
    test = df[df['Date'] >= pd.Timestamp(START_DATE)].reset_index(drop=True)
    if len(test) < 10:
        return []

    trades = []
    skip_until = -1

    for i in range(len(test) - MAX_HOLD_DAYS - 1):
        if i < skip_until:
            continue
        row   = test.iloc[i]
        comp  = composite_score(row)
        trend = sma_trend(row)
        if comp < MIN_COMP_SCORE:
            continue
        if trend not in ('up', 'strong_up'):
            continue

        entry_row = test.iloc[i + 1]
        entry = float(entry_row['Open'])
        if pd.isna(entry) or entry <= 0:
            continue

        atr    = float(row['atr'])
        stop   = round(entry - ATR_STOP_MULT * atr, 4)
        target = round(entry + ATR_TP_MULT * atr, 4)

        outcome    = 'timeout'
        exit_price = float(test.iloc[min(i + MAX_HOLD_DAYS, len(test) - 1)]['Close'])

        for j in range(i + 2, min(i + 1 + MAX_HOLD_DAYS + 1, len(test))):
            day        = test.iloc[j]
            stop_hit   = float(day['Low'])  <= stop
            target_hit = float(day['High']) >= target
            if stop_hit and target_hit:
                outcome = 'stop'; exit_price = stop; skip_until = j; break
            if stop_hit:
                outcome = 'stop'; exit_price = stop; skip_until = j; break
            if target_hit:
                outcome = 'target'; exit_price = target; skip_until = j; break

        pnl = (exit_price - entry) / entry * 100
        trades.append({
            'ticker':  ticker.replace('.IS', ''),
            'date':    str(row['Date'].date()),
            'comp':    comp,
            'trend':   trend,
            'entry':   round(entry, 4),
            'stop':    round(stop, 4),
            'target':  round(target, 4),
            'exit':    round(exit_price, 4),
            'outcome': outcome,
            'pnl_pct': round(pnl, 3),
        })
    return trades


# -------------------------------------------------
# ANA DONGU
# -------------------------------------------------
print(f"\n{'='*60}")
print(f"  BIST AI Backtest — {START_DATE} ile {END_DATE}")
print(f"  Composite >= {MIN_COMP_SCORE} | Trend: UP | ATRx{ATR_STOP_MULT}/{ATR_TP_MULT}")
print(f"{'='*60}\n")

all_trades = []
n = len(BIST_100)
for idx, tic in enumerate(BIST_100):
    sys.stdout.write(f"\r  Tariyor: {idx+1}/{n}  {tic:<16}")
    sys.stdout.flush()
    trades = backtest_stock(tic)
    all_trades.extend(trades)

print(f"\n\n  Toplam sinyal: {len(all_trades)}")

if not all_trades:
    print("  Hicbir islem uretilmedi. Parametreleri gevsetin.")
    sys.exit(0)

# -------------------------------------------------
# SONUCLAR
# -------------------------------------------------
df_t = pd.DataFrame(all_trades)

total    = len(df_t)
wins     = (df_t['outcome'] == 'target').sum()
stops    = (df_t['outcome'] == 'stop').sum()
timeouts = (df_t['outcome'] == 'timeout').sum()
win_rate = wins / total * 100

avg_win  = df_t[df_t['outcome'] == 'target']['pnl_pct'].mean()
avg_loss = df_t[df_t['outcome'] == 'stop']['pnl_pct'].mean()
avg_to   = df_t[df_t['outcome'] == 'timeout']['pnl_pct'].mean()
total_ev = df_t['pnl_pct'].mean()

streak = max_streak = 0
for _, row in df_t.iterrows():
    if row['outcome'] != 'target':
        streak += 1
        max_streak = max(max_streak, streak)
    else:
        streak = 0

sharpe = df_t['pnl_pct'].mean() / (df_t['pnl_pct'].std() + 1e-9)

print(f"\n{'='*60}")
print(f"  BACKTEST SONUCLARI")
print(f"{'='*60}")
print(f"  Toplam Islem      : {total}")
print(f"  Hedefe Ulasti     : {wins}  (%{win_rate:.1f})")
print(f"  Stop Oldu         : {stops}  (%{100-win_rate:.1f})")
print(f"  Timeout (kapat)   : {timeouts}")
print(f"{'─'*60}")
print(f"  Ortalama Kazanc   : +%{avg_win:.2f}" if not np.isnan(avg_win) else "  Ortalama Kazanc  : —")
print(f"  Ortalama Kayip    : %{avg_loss:.2f}" if not np.isnan(avg_loss) else "  Ortalama Kayip   : —")
print(f"  Timeout Ort.      : %{avg_to:.2f}" if not np.isnan(avg_to) else "  Timeout Ort.     : —")
print(f"{'─'*60}")
print(f"  Islem Basi EV     : %{total_ev:.2f}  ({'POZITIF' if total_ev > 0 else 'NEGATIF'})")
print(f"  Ard. Maks. Kayip  : {max_streak} islem")
print(f"  Sharpe Orani      : {sharpe:.2f}")
print(f"{'─'*60}")

top5 = df_t.groupby('ticker')['pnl_pct'].mean().sort_values(ascending=False).head(5)
bot5 = df_t.groupby('ticker')['pnl_pct'].mean().sort_values().head(5)
print(f"\n  En Iyi 5 Hisse:")
for tic, pnl in top5.items():
    print(f"     {tic:<10} +%{pnl:.2f}")
print(f"\n  En Kotu 5 Hisse:")
for tic, pnl in bot5.items():
    print(f"     {tic:<10} %{pnl:.2f}")

out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backtest_results.csv')
df_t.to_csv(out_file, index=False)
print(f"\n  Kayit edildi -> backtest_results.csv")
print(f"{'='*60}\n")
