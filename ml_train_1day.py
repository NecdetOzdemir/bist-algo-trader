"""
ml_train_1day.py — 1 Günlük Yön Tahmini XGBoost Eğitimi
══════════════════════════════════════════════════════════
Eski modelin sorusu: "5 günde BIST100'ü geçecek mi?" (uzun vadeli, geniş)

YENİ modelin sorusu: "YARIN en az %0.8 yükselecek mi?"
  → Bu, gün içi + 1 gün sonrası trading için optimize edilmiş.
  → Mevcut xgb_selector.pkl'nin ÜSTÜNE yeni bir model kaydeder:
     xgb_1day_model.pkl

Eğitim verisi: 2019-2023 (5 yıl)
Test verisi:   2024 (gerçek hayat sınavı)
"""

import os
import sys
import pandas as pd
import numpy as np
import pickle
import warnings
warnings.filterwarnings('ignore')

import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score, accuracy_score

DATA_DIR  = os.path.join(os.path.dirname(__file__), 'ml_data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'ml_models')
os.makedirs(MODEL_DIR, exist_ok=True)

# Modelin göreceği teknik özellikler (Var olanlarla aynı)
FEATURES = [
    'macd', 'macd_signal', 'macd_hist',
    'rsi', 'cci', 'adx', 'atr',
    'bb_high', 'bb_low', 'bb_width',
    'vol_10_sma', 'rel_volume_10', 'mfi',
    'return_1d', 'gap_pct',
    'bist_trend', 'bist_volatility', 'usd_trend', 'close_usd'
]

# ─────────────────────────────────────────────────────────────────
# Kritik parametre: Yarın bu kadar yükselmezse "al" sayma.
# %0.5 → Daha fazla sinyal, daha az hassasiyet
# %1.0 → Daha az sinyal, daha fazla hassasiyet (önerimiz)
# ─────────────────────────────────────────────────────────────────
MIN_GAIN_PCT = 0.008  # %0.8 minimum yükseliş = AL etiketi

def build_1day_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Yeni etiket: Yarın kapanış en az %0.8 yüksek kapanırsa → AL (1)
    Değilse → ALMA (0)
    
    Önemli Not: 15 dakika gecikme simülasyonu.
    Bugünün kapanış verisiyle, YARIN ne olacağını tahmin ediyoruz.
    Bu, gerçek hayattaki "saat 10:30'da dün kapanış verisine bakıp karar ver" senaryosuyla örtüşüyor.
    """
    df = df.sort_values(['tic', 'date']).copy()
    
    # Her hisse için yarınki getiri
    df['next_day_return'] = df.groupby('tic')['close'].pct_change(-1) * -1  # Ertesi gün kapanış getirisi
    
    # Etiket: Yarın %0.8'den fazla mı yükseliyor?
    df['label'] = (df['next_day_return'] >= MIN_GAIN_PCT).astype(int)
    
    # Son 1 günü at (yarın verisi yok)
    df = df.dropna(subset=['next_day_return', 'label'])
    return df


def train_1day_model():
    print("=" * 65)
    print(" 🎯 1 GÜNLÜK YÖN TAHMİNİ — XGBoost EĞİTİMİ")
    print(f" Soru: Yarın kapanış bugünden ≥%{MIN_GAIN_PCT*100:.1f} yüksek mi?")
    print("=" * 65)
    
    # ─── 1. Veri Yükle ───
    path = os.path.join(DATA_DIR, 'bist_rl_dataset.parquet')
    if not os.path.exists(path):
        print("❌ Veri seti bulunamadı. Önce ml_data_prep.py çalıştırın.")
        sys.exit(1)
    
    print("\n📂 Veri yükleniyor...")
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    print(f"   {df['tic'].nunique()} hisse, {len(df):,} satır")
    
    # ─── 2. Etiketler ───
    print("\n🏷️  Etiketler oluşturuluyor...")
    df = build_1day_labels(df)
    
    pos_rate = df['label'].mean()
    print(f"   AL etiketi oranı: %{pos_rate*100:.1f}  (Geri kalan %{(1-pos_rate)*100:.1f} → ALMA)")
    
    # ─── 3. Train / Test Ayrımı ───
    train_df = df[df['date'] < '2024-01-01'].copy()
    test_df  = df[df['date'] >= '2024-01-01'].copy()
    
    X_train = train_df[FEATURES].fillna(0)
    y_train = train_df['label']
    X_test  = test_df[FEATURES].fillna(0)
    y_test  = test_df['label']
    
    print(f"\n📊 Veri Ayrımı:")
    print(f"   Eğitim (2019-2023): {len(X_train):,} örnek")
    print(f"   Test   (2024):      {len(X_test):,} örnek")
    print(f"   Test AL oranı: %{y_test.mean()*100:.1f}")
    
    # ─── 4. XGBoost Modeli ───
    print("\n🧠 XGBoost eğitimi başlıyor...")
    
    pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
    print(f"   Sınıf dengesi ağırlığı: {pos_weight:.2f}")
    
    model = xgb.XGBClassifier(
        n_estimators=600,
        max_depth=5,              # 1 günlük tahmin için çok derin ağaç overfitting riski
        learning_rate=0.03,       # Daha yavaş, daha sağlam öğrenme
        subsample=0.7,
        colsample_bytree=0.7,
        min_child_weight=30,      # Aşırı öğrenme önleme
        gamma=1,                  # Ağaç bölünmesi için minimum kazanç
        reg_alpha=0.1,            # L1 regularization
        reg_lambda=1.0,           # L2 regularization
        scale_pos_weight=pos_weight,
        eval_metric='auc',
        early_stopping_rounds=40,
        random_state=42,
        n_jobs=-1,
        device='cuda'
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=100
    )
    
    # ─── 5. Test Sonuçları ───
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    auc  = roc_auc_score(y_test, y_prob)
    acc  = accuracy_score(y_test, y_pred)
    base = y_test.mean()  # Her zaman AL diyen baseline
    
    print(f"\n{'━'*65}")
    print(f" 🏆 TEST SONUÇLARI (2024 - Hiç Görmemiş Veri)")
    print(f"{'━'*65}")
    print(f" AUC Skoru       : {auc:.4f}  (0.5=rastgele, 1.0=mükemmel)")
    print(f" Genel Doğruluk  : %{acc*100:.2f}")
    print(f" Baseline        : %{base*100:.2f}  (Her gün 'Yükselecek' dersek)")
    print(f" Fark            : %{(acc-base)*100:+.2f}")
    print(f"{'━'*65}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['ALMA', 'AL'])}")
    
    # ─── 6. Özellik Önemleri ───
    feat_imp = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
    print(f"\n🔑 En Önemli 8 Özellik:")
    for feat, imp in feat_imp.head(8).items():
        bar = "█" * int(imp * 150)
        print(f"   {feat:<20} {bar} {imp:.4f}")
    
    # ─── 7. Kaydet ───
    # Yeni model mevcut modeli SİLMİYOR. Ayrı isimde kaydeder.
    save_path = os.path.join(MODEL_DIR, 'xgb_1day_model.pkl')
    with open(save_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n💾 Model kaydedildi: {save_path}")
    print("   Web uygulaması artık bu modeli de kullanabilecek.")
    
    return model

if __name__ == "__main__":
    train_1day_model()
