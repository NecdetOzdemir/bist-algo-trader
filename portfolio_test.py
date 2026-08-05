"""
BIST AI Trader - Portfoy Simülasyonu
=====================================
Bu script kullanıcının spesifik döngüsel portföy mantığını test eder:
- 100.000 TL başlangıç sermayesi
- Portföy kapasitesi: 5 Hisse
- Her gün portföydeki hisseler kontrol edilir (Stop, Target, 15 Gün Timeout).
- Eğer bir hisse satılırsa (slot boşalırsa), aynı gün tarama yapılır.
- Kalan nakit boş slot sayısına bölünerek en iyi (portföyde olmayan) yeni hisseler alınır.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import ta
import warnings, sys, os
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from universe import BIST_100

START_DATE   = "2024-06-01"
END_DATE     = "2025-07-31"
DATA_START   = "2023-07-01"
ATR_STOP     = 1.5
ATR_TP       = 3.0
MAX_HOLD     = 15
MAX_SLOTS    = 5
INITIAL_CASH = 100000.0

def calc_indicators(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if len(df) < 210: return pd.DataFrame()
    m = ta.trend.MACD(close=df['Close'])
    df['macd']     = m.macd()
    df['macd_sig'] = m.macd_signal()
    df['rsi']  = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()
    df['atr']  = ta.volatility.AverageTrueRange(df['High'],df['Low'],df['Close'],14).average_true_range()
    df['sma50'] = df['Close'].rolling(50).mean()
    df['sma200']= df['Close'].rolling(200).mean()
    df['vol10'] = df['Volume'].rolling(10).mean()
    df['rvol']  = df['Volume'] / (df['vol10']+1e-9)
    return df.dropna(subset=['rsi','atr','sma50','sma200'])

def composite(row):
    c = 0
    cl = row['Close']
    if cl > row['sma200']: c += 1
    if cl > row['sma50']:  c += 1
    if row['sma50'] > row['sma200']: c += 1
    rsi = row['rsi']
    if 40 <= rsi <= 65:    c += 2
    elif 30 <= rsi < 40:   c += 1
    if row['macd'] > row['macd_sig']: c += 1
    if row['rvol'] >= 1.20: c += 1
    return c

print("\nVeriler indiriliyor ve hesaplanıyor... (1-2 dakika surebilir)")
all_data = {}
n = len(BIST_100)
for idx, tic in enumerate(BIST_100):
    sys.stdout.write(f"\r  {idx+1}/{n} {tic:<14}")
    sys.stdout.flush()
    try:
        raw = yf.download(tic, start=DATA_START, end=END_DATE, progress=False, auto_adjust=True)
        if raw is not None and not raw.empty:
            df = calc_indicators(raw)
            if not df.empty:
                df = df.reset_index()
                df['Date'] = pd.to_datetime(df['Date']).dt.date
                df['ticker'] = tic.replace('.IS', '')
                all_data[tic.replace('.IS', '')] = df.set_index('Date')
    except:
        pass

print(f"\nToplam {len(all_data)} hisse verisi hazır.")

# Tüm günleri bul
all_dates = set()
for df in all_data.values():
    all_dates.update(df.index.tolist())
sorted_dates = sorted([d for d in all_dates if str(d) >= START_DATE])

portfolio = [] # dict: ticker, shares, entry_price, stop, target, days_held
cash = INITIAL_CASH
trade_history = []
portfolio_history = []

for i, today in enumerate(sorted_dates):
    # 1. Mevcut pozisyonlari guncelle / sat
    remaining_portfolio = []
    
    for pos in portfolio:
        tic = pos['ticker']
        if today not in all_data[tic].index:
            remaining_portfolio.append(pos)
            continue
        
        row = all_data[tic].loc[today]
        low = float(row['Low'])
        high = float(row['High'])
        close = float(row['Close'])
        
        pos['days_held'] += 1
        
        sold = False
        exit_price = 0
        outcome = ''
        
        if low <= pos['stop'] and high >= pos['target']:
            sold = True; exit_price = pos['stop']; outcome = 'stop'
        elif low <= pos['stop']:
            sold = True; exit_price = pos['stop']; outcome = 'stop'
        elif high >= pos['target']:
            sold = True; exit_price = pos['target']; outcome = 'target'
        elif pos['days_held'] >= MAX_HOLD:
            sold = True; exit_price = close; outcome = 'timeout'
            
        if sold:
            val = pos['shares'] * exit_price
            cash += val
            pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price'] * 100
            trade_history.append({
                'ticker': tic, 'entry_date': pos['entry_date'], 'exit_date': str(today),
                'entry': pos['entry_price'], 'exit': exit_price, 'outcome': outcome, 'pnl_pct': pnl_pct
            })
        else:
            remaining_portfolio.append(pos)
            
    portfolio = remaining_portfolio
    
    # 2. Bos yer varsa yeni hisse tara
    free_slots = MAX_SLOTS - len(portfolio)
    if free_slots > 0 and i < len(sorted_dates) - 1:
        next_day = sorted_dates[i+1]
        candidates = []
        current_tickers = [p['ticker'] for p in portfolio]
        
        for tic, df in all_data.items():
            if tic in current_tickers: continue
            if today not in df.index or next_day not in df.index: continue
            
            row = df.loc[today]
            c = composite(row)
            
            # Filtre: Strong_up ve Comp >= 5
            if c >= 5 and row['Close'] > row['sma50'] and row['sma50'] > row['sma200']:
                candidates.append({
                    'ticker': tic,
                    'comp': c,
                    'atr': float(row['atr']),
                    'next_open': float(df.loc[next_day]['Open'])
                })
        
        if candidates:
            candidates.sort(key=lambda x: x['comp'], reverse=True)
            to_buy = candidates[:free_slots]
            budget_per_slot = cash / free_slots if free_slots > 0 else 0
            
            for buy in to_buy:
                entry = buy['next_open']
                if pd.isna(entry) or entry <= 0: continue
                
                shares = budget_per_slot / entry
                if shares <= 0: continue
                
                cost = shares * entry
                cash -= cost
                
                portfolio.append({
                    'ticker': buy['ticker'],
                    'shares': shares,
                    'entry_price': entry,
                    'entry_date': str(next_day),
                    'stop': entry - ATR_STOP * buy['atr'],
                    'target': entry + ATR_TP * buy['atr'],
                    'days_held': 0
                })

    current_val = cash
    for pos in portfolio:
        tic = pos['ticker']
        if today in all_data[tic].index:
            current_val += pos['shares'] * float(all_data[tic].loc[today]['Close'])
        else:
            current_val += pos['shares'] * pos['entry_price']
            
    portfolio_history.append({'date': str(today), 'value': current_val})


df_hist = pd.DataFrame(portfolio_history)
final_val = df_hist['value'].iloc[-1]
net_profit_pct = (final_val - INITIAL_CASH) / INITIAL_CASH * 100

print(f"\n{'='*60}")
print(f"   PORTFOY SIMULASYONU SONUCU")
print(f"  {START_DATE} -> {END_DATE}")
print(f"{'='*60}")
print(f"  Baslangic Parasi : {INITIAL_CASH:,.2f} TL")
print(f"  Bitis Parasi     : {final_val:,.2f} TL")
print(f"  NET KAZANC       : %{net_profit_pct:.2f}")
print(f"{'='*60}")

if trade_history:
    df_t = pd.DataFrame(trade_history)
    wins = (df_t['outcome'] == 'target').sum()
    stops = (df_t['outcome'] == 'stop').sum()
    tos = (df_t['outcome'] == 'timeout').sum()
    total = len(df_t)
    
    print(f"  Toplam Islem     : {total}")
    print(f"  Win Rate         : %{wins/total*100:.1f} ({wins} Kar)")
    print(f"  Stop Sayisi      : {stops}")
    print(f"  Timeout (15 gun) : {tos}")
    print(f"  Ortalama Kar     : +%{df_t[df_t.outcome=='target']['pnl_pct'].mean():.2f}")
    print(f"  Ortalama Zarar   : %{df_t[df_t.outcome=='stop']['pnl_pct'].mean():.2f}")
    print(f"  Timeout Ort.     : +%{df_t[df_t.outcome=='timeout']['pnl_pct'].mean():.2f}")
else:
    print("  Hic islem yapilmadi.")
    
print(f"{'='*60}\n")
