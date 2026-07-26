import os
import sys
import pandas as pd
import numpy as np
import time
import pickle
import glob
import gc
import torch
from stable_baselines3.common.callbacks import BaseCallback, CallbackList

# CPU darboğazını ve RAM şişmesini önlemek için PyTorch thread sayısını sınırla
torch.set_num_threads(2)

from finrl.meta.env_stock_trading.env_stocktrading import StockTradingEnv
from finrl.agents.stablebaselines3.models import DRLAgent
from stable_baselines3.common.logger import configure
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback


DATA_DIR = os.path.join(os.path.dirname(__file__), 'ml_data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'ml_models')
os.makedirs(MODEL_DIR, exist_ok=True)

def train_bist_model():
    print("="*60)
    print(" 🤖 BIST YAPAY ZEKA (PPO) EĞİTİMİ BAŞLIYOR")
    print("="*60)
    
    # 1. Veri Havuzunu (Data Lake) Yükle
    data_path = os.path.join(DATA_DIR, 'bist_rl_dataset.parquet')
    if not os.path.exists(data_path):
        print(f"❌ Veri seti bulunamadı: {data_path}")
        print("Lütfen önce ml_data_prep.py dosyasını çalıştırın.")
        sys.exit(1)
        
    print("📊 Veri havuzu yükleniyor...")
    df = pd.read_parquet(data_path)
    
    # FinRL, kolon adlarının kucuk harf olmasini bekler
    df.columns = [c.lower() for c in df.columns]
    
    # FinRL DataFrame'in 'day' adında 0'dan başlayan bir indekse sahip olmasını ister
    unique_dates = df['date'].sort_values().unique()
    date_to_day = {date: i for i, date in enumerate(unique_dates)}
    df['day'] = df['date'].map(date_to_day)
    
    # 2. Tarihlere Göre Train/Validation Ayrımı
    # KRİTİK: PPO (Katman 2) sadece XGBoost'un seçtiği TOP 30 hisse için çalışır.
    # Bu state space'i 4159'dan ~630'a düşürür ve eğitimi 6x hızlandırır.
    selector_path = os.path.join(MODEL_DIR, 'xgb_selector.pkl')
    if os.path.exists(selector_path):
        import pickle
        with open(selector_path, 'rb') as f:
            selector_model = pickle.load(f)

        FEATURES = [
            'macd', 'macd_signal', 'macd_hist', 'rsi', 'cci', 'adx', 'atr',
            'bb_high', 'bb_low', 'bb_width', 'vol_10_sma', 'rel_volume_10',
            'mfi', 'return_1d', 'gap_pct', 'bist_trend', 'bist_volatility',
            'usd_trend', 'close_usd'
        ]
        latest_date = df['date'].max()
        df_today    = df[df['date'] == latest_date].copy()
        X_today     = df_today[FEATURES].fillna(0)
        df_today['score'] = selector_model.predict_proba(X_today)[:, 1]
        SELECTED_TICKERS = df_today.nlargest(30, 'score')['tic'].tolist()
        print(f"\n🤖 XGBoost Katman 1 → Seçilen 30 Hisse:")
        print(f"   {SELECTED_TICKERS}")
    else:
        # XGBoost modeli yoksa BIST30 kullan
        SELECTED_TICKERS = [
            'AKBNK', 'ARCLK', 'ASELS', 'BIMAS', 'EKGYO', 'EREGL', 'FROTO',
            'GARAN', 'HALKB', 'ISCTR', 'KCHOL', 'KRDMD', 'MGROS', 'OTKAR',
            'PETKM', 'PGSUS', 'SAHOL', 'SASA', 'SISE', 'TAVHL', 'TCELL',
            'THYAO', 'TKFEN', 'TOASO', 'TTKOM', 'TUPRS', 'VAKBN', 'VESTL',
            'YKBNK', 'ZOREN'
        ]
        print("\u26a0️ XGBoost modeli bulunamadı. BIST30 kullanılıyor.")

    train_data = df[
        (df['date'] >= '2019-01-01') &
        (df['date'] <= '2023-12-31') &
        (df['tic'].isin(SELECTED_TICKERS))
    ].copy()
    trade_data = df[
        (df['date'] >= '2024-01-01') &
        (df['tic'].isin(SELECTED_TICKERS))
    ].copy()
    
    # Eğitime başlamadan önce verinin TAM DİKDÖRTGEN (Rectangular) olması lazım.
    # Yani her 'day' için tam olarak 'stock_dim' kadar satır olmalı.
    def make_rectangular(data):
        unique_tics = data['tic'].unique()
        unique_days = data['day'].unique()
        
        # Tüm kombinasyonları oluştur
        idx = pd.MultiIndex.from_product([unique_days, unique_tics], names=['day', 'tic'])
        
        # Tekil olmayan indeksleri sil
        data = data.drop_duplicates(subset=['day', 'tic'])
        
        # Olan verileri yerleştir
        data = data.set_index(['day', 'tic']).reindex(idx).reset_index()
        
        # Tarihleri geri doldur (day'e göre)
        day_date_map = {d: date for date, d in date_to_day.items()}
        data['date'] = data['day'].map(day_date_map)
        
        # NaN değerleri önceki günün fiyatıyla doldur (hisse o gün işleme kapalıysa)
        data = data.sort_values(['tic', 'day'])
        data = data.fillna(method='ffill').fillna(method='bfill')
        
        # FinRL için date ve tic sırasına göre diz
        data = data.sort_values(['day', 'tic']).reset_index(drop=True)
        # KRİTİK: FinRL df.loc[day] ile veriyi çeker. Bu yüzden index 'day' olmalı.
        data.index = data['day'].values
        return data

    print("🛠️ Veri yapısı FinRL için dikdörtgen (Rectangular) formata çevriliyor...")
    train_data = make_rectangular(train_data)
    trade_data = make_rectangular(trade_data)
    
    print(f"   Eğitim (Train) Verisi: {train_data.date.min()} - {train_data.date.max()} ({len(train_data)} satır)")
    print(f"   Test (Trade) Verisi:   {trade_data.date.min()} - {trade_data.date.max()} ({len(trade_data)} satır)")
    
    # 3. RL Ortamının (Environment) Özelliklerini Belirle
    # Modelin öğreneceği (göreceği) özellikler
    features = [
        'macd', 'macd_signal', 'macd_hist', 'rsi', 'cci', 'adx', 
        'atr', 'bb_high', 'bb_low', 'bb_width', 
        'vol_10_sma', 'rel_volume_10', 'mfi', 'return_1d', 'gap_pct',
        'bist_trend', 'bist_volatility', 'usd_trend', 'close_usd'
    ]
    
    # Benzersiz hisse sayisi
    stock_dimension = len(train_data['tic'].unique())
    state_space = 1 + 2*stock_dimension + len(features)*stock_dimension
    
    print(f"\n⚙️ Çevre (Environment) Ayarları:")
    print(f"   Hisse Sayısı: {stock_dimension}")
    print(f"   Aksiyon Uzayı (Al/Sat/Tut): {stock_dimension}")
    print(f"   Durum (State) Uzayı: {state_space} boyutlu matris")
    
    # Borsa kurallari (Komisyon vs)
    env_kwargs = {
        "hmax": 10000,              # Tek seferde maksimum alınabilecek hisse adedi
        "initial_amount": 100000,   # 100.000 TL başlangıç sermayesi
        "num_stock_shares": [0] * stock_dimension, # Başlangıçta hisse yok
        "buy_cost_pct": [0.002] * stock_dimension, # Binde 2 Alım komisyonu
        "sell_cost_pct": [0.002] * stock_dimension, # Binde 2 Satım komisyonu
        "state_space": state_space,
        "stock_dim": stock_dimension,
        "tech_indicator_list": features,
        "action_space": stock_dimension,
        "reward_scaling": 1e-4,    # Ödülü normalize etmek için
        "print_verbosity": 1       # Her 1000 adımda log bas
    }

    print("\n🏗️ Sanal Borsa Ortamı (Simulator) Kuruluyor...")
    # Tek ortam - Sistem çökmesini önlemek için SubprocVecEnv yerine tekli env
    e_train_gym = StockTradingEnv(df=train_data, **env_kwargs)
    env_train, _ = e_train_gym.get_sb_env()
    agent = DRLAgent(env=env_train)

    # PPO Parametreleri - Hafif konfigürasyon (sistem sağlığı öncelikli)
    PPO_PARAMS = {
        "n_steps": 1024,
        "ent_coef": 0.01,
        "learning_rate": 0.00025,
        "batch_size": 128,
        "n_epochs": 10,
        "device": "cpu"
    }

    # Otomatik Devam Etme (Auto-Resume) Mantığı
    checkpoint_dir = os.path.join(MODEL_DIR, "checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    latest_model_path = None
    checkpoints = glob.glob(os.path.join(checkpoint_dir, "*.zip"))
    if checkpoints:
        latest_model_path = max(checkpoints, key=os.path.getmtime)
        
    if latest_model_path:
        print(f"\n🔄 Önceki eğitim bulundu! Kaldığı yerden devam ediliyor: {latest_model_path}")
        model_ppo = PPO.load(latest_model_path, env=env_train, **PPO_PARAMS)
    else:
        model_ppo = agent.get_model("ppo", model_kwargs=PPO_PARAMS)
        
    # Her 50.000 adımda bir kaydet
    checkpoint_callback = CheckpointCallback(
        save_freq=50000,
        save_path=checkpoint_dir,
        name_prefix="ppo_bist"
    )
    
    # RAM şişmesini (Memory Leak) önlemek için Çöp Toplayıcı (Garbage Collector)
    class MemoryCleanerCallback(BaseCallback):
        def _on_rollout_end(self) -> bool:
            gc.collect()
            return True
        def _on_step(self) -> bool:
            return True
            
    callback_list = CallbackList([checkpoint_callback, MemoryCleanerCallback()])
    
    # Loglama için (tensorboard RAM şişirdiği için kaldırıldı, sadece csv tutuluyor)
    tmp_path = os.path.join(MODEL_DIR, "ppo_logs")
    new_logger = configure(tmp_path, ["stdout", "csv"])
    model_ppo.set_logger(new_logger)

    print("\n🚀 Model Borsa İstanbul verisiyle öğrenmeye (Training) başlıyor...")
    print("⏳ Bu işlem hisse sayısına ve CPU gücüne bağlı olarak uzun sürebilir.")
    
    start_time = time.time()
    
    # Model eğitimi (Total timesteps = Ne kadar pratik yapacağı)
    # Gerçek eğitimde bu değer 1.000.000 (1 Milyon) falan olmalıdır
    TOTAL_TIMESTEPS = 2_000_000
    CHUNK_SIZE = 50_000
    CHUNKS = TOTAL_TIMESTEPS // CHUNK_SIZE

    print(f"\n🚀 Eğitim başlıyor! Hedef: {TOTAL_TIMESTEPS:,} adım ({CHUNKS} parça)")
    print(f"   📊 İlerlemeyi takip etmek için: http://localhost:7654")
    
    for i in range(CHUNKS):
        print(f"\n---> EĞİTİM BÖLÜMÜ {i+1}/{CHUNKS} BAŞLIYOR <---")
        # 1. Eğit
        trained_ppo = model_ppo.learn(
            total_timesteps=CHUNK_SIZE, 
            tb_log_name='ppo_bist',
            callback=callback_list,
            reset_num_timesteps=False
        )
        
        # 2. RAM Sızıntısını (Memory Leak) Kesin Olarak Yok Et: Ortamı sil ve baştan yarat!
        print("🧹 RAM Temizleniyor (FinRL hafıza sızıntısı engellemesi)...")
        del env_train
        del e_train_gym
        gc.collect()
        
        # 3. Ortamı taze olarak yeniden kur
        e_train_gym = StockTradingEnv(df=train_data, **env_kwargs)
        env_train, _ = e_train_gym.get_sb_env()
        model_ppo.set_env(env_train)
    
    training_time = time.time() - start_time
    print(f"\n✅ Eğitim {training_time:.2f} saniyede tamamlandı!")

    # 5. Ağırlıkları (Weights) Kaydet
    save_path = os.path.join(MODEL_DIR, "bist_ppo_model.zip")
    trained_ppo.save(save_path)
    print(f"💾 Eğitilmiş Yapay Zeka Beyni kaydedildi: {save_path}")
    print("Artık bu model ile 2024 (Test) verisinde işlem yapabiliriz!")

if __name__ == "__main__":
    train_bist_model()
