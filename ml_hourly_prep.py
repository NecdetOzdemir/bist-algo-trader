"""
ml_hourly_prep.py — Saatlik Veri İndirme (RAM Güvenli + Kaldığı Yerden Devam)
═══════════════════════════════════════════════════════════════════════════════
RAM Korumaları:
  1. Her hisse işlenince ANINDA diske eklenir (append modu)
  2. Hangi hisselerin işlendiği checkpoint.json'a kaydedilir
  3. Çökme/kapanma durumunda kaldığı yerden devam eder
  4. RAM %80'i geçerse 15 saniye bekler, gc.collect() yapar
  5. Hisse başına ~50MB RAM → swap olmadığı için kritik

Kullanım:
  python3 ml_hourly_prep.py           → Baştan başla (veya devam et)
  python3 ml_hourly_prep.py --reset   → Checkpoint'i sil, baştan başla
"""

import os
import gc
import sys
import json
import time
import warnings
import pandas as pd
import numpy as np
import yfinance as yf
import psutil
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from universe import BIST_100

DATA_DIR   = os.path.join(os.path.dirname(__file__), 'ml_data')
os.makedirs(DATA_DIR, exist_ok=True)

OUT_PATH        = os.path.join(DATA_DIR, 'bist_hourly_dataset.parquet')
CHECKPOINT_PATH = os.path.join(DATA_DIR, 'hourly_checkpoint.json')

PERIOD   = '730d'   # 2 yıllık veri
INTERVAL = '1h'

RAM_WARN_PCT  = 75   # Bu seviyede uyarı ver
RAM_PAUSE_PCT = 82   # Bu seviyede 15 sn bekle ve temizle
RAM_STOP_PCT  = 90   # Bu seviyede durdur (veri bütünlüğünü koru)

MACRO_TICKERS = ['XU100.IS', 'TRY=X']


# ══════════════════════════════════════════════════════
# Checkpoint Yönetimi
# ══════════════════════════════════════════════════════

def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            return set(json.load(f).get('done', []))
    return set()

def save_checkpoint(done_set):
    with open(CHECKPOINT_PATH, 'w') as f:
        json.dump({'done': list(done_set)}, f)

def reset_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)
    if os.path.exists(OUT_PATH):
        os.remove(OUT_PATH)
    print("🗑️  Checkpoint ve dataset sıfırlandı.")


# ══════════════════════════════════════════════════════
# RAM Kontrolü
# ══════════════════════════════════════════════════════

def check_ram(tic_name=""):
    """RAM durumunu kontrol et. Kritik seviyede dur."""
    pct = psutil.virtual_memory().percent
    avail_gb = psutil.virtual_memory().available / 1e9

    if pct >= RAM_STOP_PCT:
        print(f"\n🛑 RAM KRİTİK (%{pct:.0f}, {avail_gb:.1f}GB boş)! Güvenli çıkış yapılıyor...")
        print(f"   ✅ Checkpoint kaydedildi. 'python3 ml_hourly_prep.py' ile devam edebilirsin.")
        sys.exit(0)

    if pct >= RAM_PAUSE_PCT:
        print(f"   ⚠️  RAM %{pct:.0f} — 15 saniye bekleniyor, bellek temizleniyor...")
        gc.collect()
        time.sleep(15)
        gc.collect()

    if pct >= RAM_WARN_PCT:
        print(f"   💛 RAM: %{pct:.0f} ({avail_gb:.1f}GB boş)")

    return pct


# ══════════════════════════════════════════════════════
# Teknik İndikatörler (Saatlik periyot için)
# ══════════════════════════════════════════════════════

def _rsi(series, period=14):
    delta = series.diff()
    gain  = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _adx(high, low, close, period=14):
    try:
        tr  = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.ewm(span=period, adjust=False).mean()
        up  = high.diff(); down = -low.diff()
        pdm = up.where((up > down) & (up > 0), 0)
        ndm = down.where((down > up) & (down > 0), 0)
        pdi = 100 * pdm.ewm(span=period, adjust=False).mean() / atr
        ndi = 100 * ndm.ewm(span=period, adjust=False).mean() / atr
        dx  = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
        return dx.ewm(span=period, adjust=False).mean()
    except:
        return pd.Series(np.nan, index=high.index)

def add_hourly_indicators(df: pd.DataFrame) -> pd.DataFrame:
    try:
        c, h, l, v = df['Close'], df['High'], df['Low'], df['Volume']
        # MACD
        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        df['MACD']        = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist']   = df['MACD'] - df['MACD_Signal']
        # RSI
        df['RSI'] = _rsi(c, 14)
        # Bollinger (20 saatlik ≈ 2.5 gün)
        ma20 = c.rolling(20).mean(); std20 = c.rolling(20).std()
        df['BB_High']  = ma20 + 2*std20
        df['BB_Low']   = ma20 - 2*std20
        df['BB_Width'] = (df['BB_High'] - df['BB_Low']) / ma20
        # ATR
        tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
        df['ATR'] = tr.ewm(span=14, adjust=False).mean()
        # Hacim
        df['Vol_10_SMA']    = v.rolling(10).mean()
        df['Rel_Volume_10'] = v / df['Vol_10_SMA'].replace(0, np.nan)
        # CCI
        tp = (h+l+c)/3
        df['CCI'] = (tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean()))))
        # ADX
        df['ADX'] = _adx(h, l, c, 14)
        # MFI
        mf  = tp * v
        pmf = mf.where(tp > tp.shift(1), 0).rolling(14).sum()
        nmf = mf.where(tp < tp.shift(1), 0).rolling(14).sum()
        df['MFI'] = 100 - (100 / (1 + pmf / nmf.replace(0, np.nan)))
        # Return & Gap
        df['Return_1h'] = c.pct_change()
        df['Gap_Pct']   = (df['Open'] - c.shift(1)) / c.shift(1)
        # Saat bilgisi (gün içi örüntüler)
        df['Hour']            = df.index.hour
        df['Is_Opening_Hour'] = (df['Hour'] == 9).astype(int)
        df['Is_Closing_Hour'] = (df['Hour'] == 17).astype(int)

        return df.dropna()
    except Exception as e:
        print(f"         ⚠️  İndikatör hatası: {e}")
        return None


# ══════════════════════════════════════════════════════
# Makro Veri
# ══════════════════════════════════════════════════════

def fetch_macro_hourly():
    print("📡 Makro veri çekiliyor (XU100 + USDTRY)...")
    dfs = {}
    for t in MACRO_TICKERS:
        try:
            df = yf.download(t, period=PERIOD, interval=INTERVAL, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.index.tz:
                df.index = df.index.tz_convert('UTC').tz_localize(None)
            dfs[t] = df
            time.sleep(0.5)
        except Exception as e:
            print(f"   ⚠️  {t}: {e}")

    if 'XU100.IS' not in dfs or 'TRY=X' not in dfs:
        print("❌ Makro veri eksik!")
        return None

    bist = dfs['XU100.IS']
    usd  = dfs['TRY=X']

    macro = pd.DataFrame({
        'bist_close':      bist['Close'],
        'bist_trend':      bist['Close'].pct_change(),
        'bist_volatility': (bist['High'] - bist['Low']) / bist['Close'],
        'usd_close':       usd['Close'],
        'usd_trend':       usd['Close'].pct_change(),
    }).ffill()

    print(f"   ✅ Makro: {len(macro)} bar ({macro.index[0].date()} → {macro.index[-1].date()})")
    return macro


# ══════════════════════════════════════════════════════
# Tek Hisse İşleme
# ══════════════════════════════════════════════════════

def process_one(tic, macro_df):
    df = yf.download(tic, period=PERIOD, interval=INTERVAL, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.empty or len(df) < 200:
        return None

    # Timezone normalize
    if df.index.tz:
        df.index = df.index.tz_convert('UTC').tz_localize(None)

    # Makro birleştir
    df = df.join(macro_df, how='left').ffill()
    if 'usd_close' in df.columns:
        df['Close_USD'] = df['Close'] / df['usd_close'].replace(0, np.nan)

    df = add_hourly_indicators(df)
    if df is None or df.empty:
        return None

    df['tic']  = tic.replace('.IS', '')
    df['date'] = df.index
    return df.reset_index(drop=True)


# ══════════════════════════════════════════════════════
# Ana Fonksiyon
# ══════════════════════════════════════════════════════

def main():
    # --reset argümanı
    if '--reset' in sys.argv:
        reset_checkpoint()

    done_set = load_checkpoint()
    remaining = [t for t in BIST_100 if t.replace('.IS','') not in done_set]

    print("=" * 65)
    print(" 📊 BIST SAATLİK VERİ İNDİRME (2 Yıl)")
    print(f" Toplam hisse : {len(BIST_100)}")
    print(f" İşlenmiş     : {len(done_set)} (checkpoint'ten devam)")
    print(f" Kalan        : {len(remaining)}")
    print(f" RAM koruması : AÇIK (Stop: %{RAM_STOP_PCT}, Pause: %{RAM_PAUSE_PCT})")
    print("=" * 65)

    if not remaining:
        print("\n✅ Tüm hisseler zaten işlenmiş! Çıkılıyor.")
        return

    macro_df = fetch_macro_hourly()
    if macro_df is None:
        sys.exit(1)

    total = len(remaining)
    success = 0

    for i, tic in enumerate(remaining, 1):
        tic_clean = tic.replace('.IS', '')
        ram_pct   = check_ram(tic_clean)  # RAM'i kontrol et, gerekirse dur

        print(f"\n[{i:3d}/{total}] {tic_clean:<10} | RAM: %{ram_pct:.0f}", end=" | ")

        try:
            df = process_one(tic, macro_df)

            if df is None:
                print("Yetersiz veri, atlanıyor.")
                done_set.add(tic_clean)
                save_checkpoint(done_set)
                continue

            # ─── ANINDA DİSKE YAZ (Append modu) ───
            if os.path.exists(OUT_PATH):
                existing = pd.read_parquet(OUT_PATH)
                combined = pd.concat([existing, df], ignore_index=True)
                del existing
            else:
                combined = df

            combined.to_parquet(OUT_PATH, index=False)
            del combined, df
            gc.collect()

            # ─── CHECKPOINT GÜNCELLE ───
            done_set.add(tic_clean)
            save_checkpoint(done_set)

            success += 1
            print(f"✅ Kaydedildi.")

        except Exception as e:
            print(f"❌ Hata: {e}")
            time.sleep(1)

        time.sleep(0.5)  # Rate limit koruması

    print(f"\n{'='*65}")
    print(f" ✅ TAMAMLANDI: {success}/{total} hisse başarıyla işlendi.")
    if os.path.exists(OUT_PATH):
        final = pd.read_parquet(OUT_PATH)
        print(f" Toplam satır : {len(final):,}")
        print(f" Hisse sayısı : {final['tic'].nunique()}")
        del final
    print(f" Kaydedildi   : {OUT_PATH}")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
