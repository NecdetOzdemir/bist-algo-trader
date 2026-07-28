import yfinance as yf
import pandas as pd
import numpy as np

def detect_smc(df):
    smc_data = {
        'ob_bullish': None,
        'ob_bearish': None,
        'fvg_bullish': None,
        'fvg_bearish': None,
        'liquidity_sweep': None,
        'smc_comment': []
    }
    
    if len(df) < 30:
        return smc_data
        
    df_recent = df.tail(30).copy()
    current_price = df.iloc[-1]['Close']
    
    # 1. Fair Value Gap (FVG)
    for i in range(2, len(df_recent)):
        c1_h = df_recent.iloc[i-2]['High']
        c1_l = df_recent.iloc[i-2]['Low']
        c3_h = df_recent.iloc[i]['High']
        c3_l = df_recent.iloc[i]['Low']
        
        # Bullish FVG (Gap up)
        if c3_l > c1_h:
            smc_data['fvg_bullish'] = round((c1_h + c3_l) / 2, 2)
            
        # Bearish FVG (Gap down)
        if c3_h < c1_l:
            smc_data['fvg_bearish'] = round((c1_l + c3_h) / 2, 2)
            
    # 2. Order Block (OB)
    # Simple logic: Find strong impulsive move (e.g. > 3% candle) 
    # and the OB is the opposite candle right before it.
    for i in range(1, len(df_recent)):
        prev_open = df_recent.iloc[i-1]['Open']
        prev_close = df_recent.iloc[i-1]['Close']
        curr_open = df_recent.iloc[i]['Open']
        curr_close = df_recent.iloc[i]['Close']
        curr_pct = (curr_close - curr_open) / curr_open
        
        if curr_pct > 0.035 and prev_close < prev_open:
            # Bullish OB (Last down candle before strong up move)
            smc_data['ob_bullish'] = round(df_recent.iloc[i-1]['Low'], 2)
            
        if curr_pct < -0.035 and prev_close > prev_open:
            # Bearish OB (Last up candle before strong down move)
            smc_data['ob_bearish'] = round(df_recent.iloc[i-1]['High'], 2)
            
    # 3. Liquidity Sweep
    # Last 3 days low sweeps below a 20-day lowest low but closes above it.
    past_low = df_recent.iloc[:-3]['Low'].min()
    recent_candle = df_recent.iloc[-1]
    
    if recent_candle['Low'] < past_low and recent_candle['Close'] > past_low:
        smc_data['liquidity_sweep'] = "BULLISH_SWEEP"
    elif recent_candle['High'] > df_recent.iloc[:-3]['High'].max() and recent_candle['Close'] < df_recent.iloc[:-3]['High'].max():
        smc_data['liquidity_sweep'] = "BEARISH_SWEEP"

    # Generate comments
    if smc_data['ob_bullish'] and current_price > smc_data['ob_bullish'] and (current_price - smc_data['ob_bullish'])/current_price < 0.05:
        smc_data['smc_comment'].append(f"🐋 Fiyat, balinaların {smc_data['ob_bullish']} TL'deki Alıcı Emir Bloğuna (Order Block) çok yakın. Güçlü destek!")
    if smc_data['liquidity_sweep'] == 'BULLISH_SWEEP':
        smc_data['smc_comment'].append("🚨 Küçük yatırımcının stopları patlatıldı (Liquidity Sweep) ve fiyat hızla toparlandı. Yükseliş işareti!")
    if smc_data['fvg_bullish'] and current_price > smc_data['fvg_bullish'] and (current_price - smc_data['fvg_bullish'])/current_price < 0.04:
        smc_data['smc_comment'].append(f"🧲 Fiyat {smc_data['fvg_bullish']} TL'deki Dengesizlik Boşluğuna (FVG) mıknatıs gibi çekilip alım fırsatı verebilir.")
        
    if not smc_data['smc_comment']:
        smc_data['smc_comment'].append("Şu an piyasada net bir Balina (Akıllı Para) izi tespit edilmedi. Normal seyir devam ediyor.")

    return smc_data

df = yf.download("THYAO.IS", period="6mo", progress=False)
print(detect_smc(df))
