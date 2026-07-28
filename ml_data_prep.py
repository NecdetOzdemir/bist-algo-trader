import yfinance as yf
import pandas as pd
import numpy as np
import ta
import os
import time
from datetime import datetime, timedelta
import sys

# Projemizdeki listeyi ice aktaralim
try:
    from universe import BIST_ALL
except ImportError:
    print("universe.py bulunamadi!")
    sys.exit(1)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'ml_data')
os.makedirs(DATA_DIR, exist_ok=True)

def add_technical_indicators(df):
    """Veriye teknik indikatörleri ve modelin öğreneceği özel özellikleri ekler."""
    # Dataframe'in temiz olduğundan emin olalım
    df = df.copy()
    
    # NaN'lari temizleyelim (yeni baslayan hisseler olabilir)
    df = df.dropna(subset=['Close', 'Volume'])
    if len(df) < 50:  # En az 50 gunluk verisi olmali
        return None

    # --- 1. Temel Trend İndikatörleri (MACD, RSI, vb.) ---
    # MACD
    macd = ta.trend.MACD(close=df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()
    
    # RSI
    df['RSI'] = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()
    
    # CCI (Commodity Channel Index - Aşırı alım/satım için)
    df['CCI'] = ta.trend.CCIIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=20).cci()
    
    # ADX (Trend gücü)
    adx = ta.trend.ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['ADX'] = adx.adx()
    
    # --- 2. Volatilite (Oynaklık) ---
    # ATR (Ortalama Gerçek Aralık - Stop mesafesi için kritik)
    df['ATR'] = ta.volatility.AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14).average_true_range()
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['BB_High'] = bb.bollinger_hband()
    df['BB_Low'] = bb.bollinger_lband()
    df['BB_Width'] = (df['BB_High'] - df['BB_Low']) / df['Close'] # Bant genisligi (Sıkışma tespiti)

    # Keltner Channels & TTM Squeeze (John F. Carter)
    kc_middle = df['Close'].rolling(window=20).mean()
    # Keltner genellikle 20 ATR veya 14 ATR kullanır, biz halihazırda hesaplanan 14 günlük ATR'yi kullanabiliriz.
    kc_upper = kc_middle + (1.5 * df['ATR'])
    kc_lower = kc_middle - (1.5 * df['ATR'])
    
    # Squeeze is ON (Oynaklık aşırı düştü, patlama yakındır)
    # BB'nin tamamı KC'nin içindeyse squeeze vardır.
    df['Squeeze_On'] = (df['BB_Low'] > kc_lower) & (df['BB_High'] < kc_upper)

    # --- 3. Hacim Anormallikleri (Manipülasyon ve Akıllı Para İzleri) ---
    # 10 günlük ve 20 günlük ortalama hacim
    df['Vol_10_SMA'] = df['Volume'].rolling(window=10).mean()
    df['Vol_20_SMA'] = df['Volume'].rolling(window=20).mean()
    
    # Göreceli Hacim (Relative Volume) - Bugunun hacmi ortalamanin kac kati?
    # ML modelinin tahtaci girisini anlayacagi yer burasi!
    df['Rel_Volume_10'] = np.where(df['Vol_10_SMA'] > 0, df['Volume'] / df['Vol_10_SMA'], 1)
    
    # VPA (Volume Price Analysis - Anna Coulling) Anomaly Detection
    # Mum gövdesi küçük ama hacim devasa ise bu kurumsal bir ayak izidir (Gizli Toplama / Dağıtma)
    candle_body = abs(df['Close'] - df['Open']) / df['Open']
    df['VPA_Anomaly'] = (candle_body < 0.015) & (df['Rel_Volume_10'] > 1.8)
    
    # Hacim Fiyat Trendi (VPT) veya MFI
    df['MFI'] = ta.volume.MFIIndicator(high=df['High'], low=df['Low'], close=df['Close'], volume=df['Volume'], window=14).money_flow_index()

    # --- 4. Fiyat Boşlukları (Gaps) ve Momentum ---
    # Düne göre % değişim
    df['Return_1d'] = df['Close'].pct_change()
    
    # Gap (Boşluklu açılış) %
    df['Gap_Pct'] = (df['Open'] - df['Close'].shift(1)) / df['Close'].shift(1)

    # NaN degerleri atalim (cunku hareketli ortalamalar ilk X gun icin NaN doner)
    df = df.dropna()
    return df


def fetch_macro_data(start_str, end_str):
    """BIST 100 ve USD/TRY verilerini çekip makro özellikleri hazırlar."""
    print("🌍 Makroekonomik veriler çekiliyor (BIST100 & USD/TRY)...")
    macro_tickers = ["XU100.IS", "TRY=X"]
    macro_data = yf.download(macro_tickers, start=start_str, end=end_str, group_by='ticker', auto_adjust=True, progress=False)
    
    # BIST 100
    df_bist = macro_data['XU100.IS'].copy()
    df_bist['bist_trend'] = df_bist['Close'].pct_change()
    df_bist['bist_volatility'] = (df_bist['High'] - df_bist['Low']) / df_bist['Close']
    df_bist = df_bist[['Close', 'bist_trend', 'bist_volatility']].rename(columns={'Close': 'bist_close'})
    
    # USD/TRY
    df_usd = macro_data['TRY=X'].copy()
    df_usd['usd_trend'] = df_usd['Close'].pct_change()
    df_usd = df_usd[['Close', 'usd_trend']].rename(columns={'Close': 'usd_close'})
    
    # Birlestir
    macro_df = pd.merge(df_bist, df_usd, left_index=True, right_index=True, how='left')
    # Dolar hafta sonu/tatil verisi olmayabilir, forward fill
    macro_df = macro_df.fillna(method='ffill')
    
    return macro_df

def fetch_and_prepare_data(tickers, years=5):
    """Tüm hisselerin verisini yfinance'tan çeker ve veri havuzunu hazırlar."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Tüm hisselere .IS ekleyelim
    yf_tickers = [f"{t}.IS" if not t.endswith(".IS") else t for t in tickers]
    
    print(f"\n📊 {len(yf_tickers)} hisse için {years} yıllık veri çekiliyor...")
    print("   Bu işlem yfinance üzerinden tek seferde yapılacak (Hızlı Mod).")
    
    # yf.download ile toplu veri çekimi çok daha hızlıdır
    data = yf.download(
        yf_tickers,
        start=start_str,
        end=end_str,
        group_by='ticker',
        auto_adjust=True,
        threads=True,
        progress=True
    )
    
    all_dataframes = []
    
    print("\n⚙️ İndikatörler ve özellikler (Feature Engineering) hesaplanıyor...")
    
    for tk in yf_tickers:
        try:
            # Eger tek hisse seklinde donduyse (liste boyutu 1 ise) veya multi-index ise:
            if len(yf_tickers) == 1:
                df_stock = data.copy()
            else:
                if tk not in data.columns.levels[0]:
                    continue
                df_stock = data[tk].copy()
            
            # Veri yoksa gec
            if df_stock.empty or len(df_stock.dropna()) < 100:
                continue
                
            # Özellikleri hesapla
            df_features = add_technical_indicators(df_stock)
            
            if df_features is not None and not df_features.empty:
                # Ticker bilgisini kolon olarak ekle
                df_features['tic'] = tk.replace('.IS', '')
                # Tarih indeksini kolona al
                df_features.reset_index(inplace=True)
                
                # FinRL formatına uyum için kolon isimlerini küçük harf yap
                # df_features.columns = [c.lower() if c != 'Date' else 'date' for c in df_features.columns]
                
                all_dataframes.append(df_features)
                
        except Exception as e:
            print(f"   [!] {tk} hesaplanırken hata: {e}")
            continue

    if not all_dataframes:
        print("❌ Hiç geçerli veri bulunamadı.")
        return None

    # Tüm hisselerin verisini tek bir devasa tabloda (Data Lake) birleştir
    final_df = pd.concat(all_dataframes, ignore_index=True)
    
    # Makro verileri ekle (Tarih üzerinden)
    macro_df = fetch_macro_data(start_str, end_str)
    macro_df.reset_index(inplace=True)
    macro_df.rename(columns={'Date': 'date', 'index': 'date'}, inplace=True, errors='ignore')
    macro_df['date'] = macro_df['date'].astype(str)
    
    # FinRL için zorunlu kolon formatı
    if 'Date' in final_df.columns:
        final_df.rename(columns={'Date': 'date'}, inplace=True)
    final_df['date'] = final_df['date'].astype(str)
    
    # Makro birleştirme
    final_df = pd.merge(final_df, macro_df, on='date', how='left')
    final_df = final_df.fillna(method='ffill').dropna()
    
    # Enflasyondan Arındırılmış Kapanış Fiyatı (Hisse Fiyatı / USDTRY)
    final_df['close_usd'] = final_df['Close'] / final_df['usd_close']
    
    # FinRL fiyat ve hacim isimlerini kucuk harf ister
    final_df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    }, inplace=True)

    # --- TRAIN / VALIDATION / TEST SPLIT BİLGİSİ ---
    # Bu aşamada veriyi bölmüyoruz, ama sıralı tarihte olduğu için
    # rl_env.py dosyasında 2019-2022 (Train), 2023 (Validation), 2024 (Test)
    # olarak tarihten kolayca kesebileceğiz.
    final_df = final_df.sort_values(['date', 'tic']).reset_index(drop=True)

    print(f"\n✅ Data Lake (Veri Havuzu) Hazır!")
    print(f"   Toplam Satır Sayısı: {len(final_df)}")
    print(f"   Hisse Sayısı: {final_df['tic'].nunique()}")
    print(f"   Özellik (Feature) Sayısı: {len(final_df.columns)}")
    
    return final_df

if __name__ == "__main__":
    print("="*60)
    print(" 🚀 BIST MAKİNE ÖĞRENMESİ (RL) VERİ HAVUZU OLUŞTURUCU")
    print("="*60)
    
    # Hizli test icin eger istersen listeyi kesebilirsin
    tickers_to_fetch = BIST_ALL
    
    # Veriyi cek ve hazirla
    dataset = fetch_and_prepare_data(tickers_to_fetch, years=5)
    
    if dataset is not None:
        # Kaydet
        output_file = os.path.join(DATA_DIR, 'bist_rl_dataset.parquet')
        print(f"\n💾 Veriler parquet formatında kaydediliyor: {output_file}")
        
        # Parquet formatı, devasa verileri sıkıştırarak kaydetmek için en iyi formattır
        dataset.to_parquet(output_file, index=False)
        
        print("\n🎉 İŞLEM BAŞARILI. Model (Ajan) eğitimi için veri hazır.")
