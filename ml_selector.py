"""
ml_selector.py — KATMAN 1: XGBoost Hisse Seçici
────────────────────────────────────────────────
210 BIST hissesine bakarak "Bu hisse önümüzdeki 5 günde
BIST100'ü geçecek mi?" sorusunu tahmin eder.

Her gün skorlama yapıp en yüksek olasılıklı 30 hisseyi döndürür.
Bu liste doğrudan PPO (Katman 2) eğitimine beslenir.
"""

import os
import sys
import pandas as pd
import numpy as np
import pickle
import warnings
warnings.filterwarnings('ignore')

try:
    import xgboost as xgb
except ImportError:
    print("XGBoost yüklü değil. Yükleniyor...")
    os.system("pip3 install xgboost -q")
    import xgboost as xgb

from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, roc_auc_score

DATA_DIR  = os.path.join(os.path.dirname(__file__), 'ml_data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'ml_models')
os.makedirs(MODEL_DIR, exist_ok=True)

# Modelin göreceği özellikler (Teknik + Makro)
FEATURES = [
    'macd', 'macd_signal', 'macd_hist',
    'rsi', 'cci', 'adx', 'atr',
    'bb_high', 'bb_low', 'bb_width',
    'vol_10_sma', 'rel_volume_10', 'mfi',
    'return_1d', 'gap_pct',
    'bist_trend', 'bist_volatility', 'usd_trend', 'close_usd'
]

FORWARD_DAYS = 5   # Kaç gün sonrasına bakıyoruz?
TOP_N        = 30  # Her gün kaç hisse seçeceğiz?


def build_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hedef (Label) oluştur:
    Hisse, önümüzdeki 5 günde BIST100 getirisini geçiyor mu?
    Evet → 1 (Al sinyali)
    Hayır → 0 (Geçme)
    """
    df = df.sort_values(['tic', 'date']).copy()

    # Her hisse için N gün sonraki getiri
    df['future_return'] = (
        df.groupby('tic')['close']
          .transform(lambda x: x.shift(-FORWARD_DAYS) / x - 1)
    )

    # BIST100 getirisini referans al
    df['bist_future'] = (
        df.groupby('date')['bist_trend']
          .transform('mean')
          .rolling(FORWARD_DAYS).sum().shift(-FORWARD_DAYS)
    )

    # Label: Hisse, endeksi geçiyor mu?
    df['label'] = (df['future_return'] > df['bist_future']).astype(int)

    # Son N günü at (gelecek verisi yok)
    df = df.dropna(subset=['future_return', 'label'])
    return df


def train_selector():
    """XGBoost modelini eğit ve kaydet."""
    print("=" * 60)
    print(" 🔍 KATMAN 1: XGBoost Hisse Seçici Eğitimi")
    print("=" * 60)

    # --- 1. Veri Yükle ---
    path = os.path.join(DATA_DIR, 'bist_rl_dataset.parquet')
    if not os.path.exists(path):
        print("❌ Veri seti bulunamadı. Önce ml_data_prep.py çalıştırın.")
        sys.exit(1)

    print("📊 Veri yükleniyor...")
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    print(f"   {df['tic'].nunique()} hisse, {len(df):,} satır")

    # --- 2. Label Oluştur ---
    print(f"🏷️  Label oluşturuluyor (Gelecek {FORWARD_DAYS} gün BIST100'ü geçiyor mu?)...")
    df = build_labels(df)

    # --- 3. Train / Test Split ---
    train_df = df[df['date'] < '2024-01-01']
    test_df  = df[df['date'] >= '2024-01-01']

    X_train = train_df[FEATURES].fillna(0)
    y_train = train_df['label']
    X_test  = test_df[FEATURES].fillna(0)
    y_test  = test_df['label']

    print(f"   Eğitim: {len(X_train):,} örnek | Test: {len(X_test):,} örnek")
    print(f"   Pozitif (Al) oranı — Eğitim: {y_train.mean():.1%} | Test: {y_test.mean():.1%}")

    # --- 4. XGBoost Modeli ---
    print("\n🧠 XGBoost modeli eğitiliyor...")
    model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=20,   # Aşırı öğrenmeyi önle (Küçük hisseler için kritik)
        scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),  # Dengesiz sınıf
        eval_metric='auc',
        early_stopping_rounds=30,
        random_state=42,
        n_jobs=-1,
        device='cuda'   # XGBoost tablo verisinde GPU'dan ciddi fayda sağlar (5-10x hız)
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50
    )

    # --- 5. Değerlendirme ---
    y_pred      = model.predict(X_test)
    y_pred_prob = model.predict_proba(X_test)[:, 1]
    auc         = roc_auc_score(y_test, y_pred_prob)

    print("\n📊 TEST SONUÇLARI:")
    print(f"   AUC Skoru: {auc:.4f}  (0.5 = rastgele, 1.0 = mükemmel)")
    print("\n" + classification_report(y_test, y_pred, target_names=['Geçemez', 'BIST100 Geçer']))

    # --- 6. Özellik Önemleri ---
    feat_imp = pd.Series(model.feature_importances_, index=FEATURES)
    feat_imp = feat_imp.sort_values(ascending=False)
    print("🔑 En önemli 10 özellik:")
    for feat, imp in feat_imp.head(10).items():
        bar = "█" * int(imp * 200)
        print(f"   {feat:<20} {bar} {imp:.4f}")

    # --- 7. Kaydet ---
    save_path = os.path.join(MODEL_DIR, 'xgb_selector.pkl')
    with open(save_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n💾 Model kaydedildi: {save_path}")

    return model, test_df


def select_top_stocks(model, df_today: pd.DataFrame, top_n: int = TOP_N) -> list:
    """
    Bugünün verisiyle skorlama yap ve en iyi hisseleri döndür.
    
    Args:
        model: Eğitilmiş XGBoost modeli
        df_today: Bugünün özellik verisi (her hisse için 1 satır)
        top_n: Kaç hisse seçilecek?
    
    Returns:
        Seçilen hisse kodlarının listesi (en iyi → en az iyi sıralamasıyla)
    """
    X = df_today[FEATURES].fillna(0)
    probs = model.predict_proba(X)[:, 1]
    df_today = df_today.copy()
    df_today['score'] = probs
    top = df_today.nlargest(top_n, 'score')
    return top['tic'].tolist()


def run_daily_selection():
    """Son günün verisini kullanarak bugün için hisse seç."""
    model_path = os.path.join(MODEL_DIR, 'xgb_selector.pkl')
    if not os.path.exists(model_path):
        print("❌ Model bulunamadı. Önce train_selector() çalıştırın.")
        return

    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    df = pd.read_parquet(os.path.join(DATA_DIR, 'bist_rl_dataset.parquet'))
    df.columns = [c.lower() for c in df.columns]

    # Son günün verisi
    latest_date = df['date'].max()
    df_today    = df[df['date'] == latest_date]

    selected = select_top_stocks(model, df_today)

    print(f"\n📅 {latest_date} Tarihi İçin Seçilen En İyi {TOP_N} Hisse:")
    print("─" * 40)
    for i, tic in enumerate(selected, 1):
        print(f"   {i:2d}. {tic}")
    print("─" * 40)
    print(f"Bu hisseler PPO (Katman 2) eğitimine beslenecek.")
    return selected


if __name__ == "__main__":
    model, test_df = train_selector()
    print("\n" + "=" * 60)
    print(" 📅 GÜNLÜK SEÇIM TESTİ")
    print("=" * 60)
    run_daily_selection()
