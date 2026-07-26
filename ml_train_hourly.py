"""
ml_train_hourly.py — Saatlik XGBoost Eğitimi
═════════════════════════════════════════════
Soru: "Önümüzdeki 3 saatte en az +%0.8 yükselecek mi?"

Eğitim: 2023-09 → 2025-12
Test  : 2026-01 → 2026-07 (gerçek hayat sınavı)

Çıktı: ml_models/xgb_hourly_model.pkl
"""

import os
import sys
import gc
import pickle
import warnings
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')

import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score, accuracy_score

DATA_DIR  = os.path.join(os.path.dirname(__file__), 'ml_data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'ml_models')
os.makedirs(MODEL_DIR, exist_ok=True)

# ─── Saatlik indikatör kolonları ───
FEATURES = [
    'macd', 'macd_signal', 'macd_hist',
    'rsi', 'cci', 'adx', 'atr',
    'bb_high', 'bb_low', 'bb_width',
    'vol_10_sma', 'rel_volume_10', 'mfi',
    'return_1h', 'gap_pct',
    'bist_trend', 'bist_volatility', 'usd_trend', 'close_usd',
    'hour', 'is_opening_hour', 'is_closing_hour'  # Gün içi örüntüler için
]

# ─── Etiket parametresi ───
# Önümüzdeki N saatte M% yükselmezse ALMA
FORWARD_BARS  = 3      # 3 saat sonrasına bak
MIN_GAIN_PCT  = 0.008  # en az +%0.8

def build_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Saatlik label:
    Bir sonraki 3 saatin maksimum fiyatı, şimdiki kapanıştan +%0.8 
    veya daha fazlaysa → AL (1), değilse ALMA (0)
    
    Not: max kullanmak, "tam 3 saat beklemeye gerek yok" demek.
    Eğer o 3 saat içinde herhangi bir anda hedefe ulaşırsa kâr edilmiş sayılır.
    """
    df = df.sort_values(['tic', 'date']).copy()
    
    # Sonraki 3 bardaki en yüksek fiyat
    df['max_high_3h'] = df.groupby('tic')['high'].transform(
        lambda x: x.rolling(FORWARD_BARS, min_periods=1).max().shift(-FORWARD_BARS)
    )
    
    df['future_gain'] = (df['max_high_3h'] - df['close']) / df['close']
    df['label']       = (df['future_gain'] >= MIN_GAIN_PCT).astype(int)
    
    return df.dropna(subset=['label'])


def main():
    print("=" * 65)
    print(" ⚡ SAATLİK XGBoost EĞİTİMİ")
    print(f" Soru: Önümüzdeki {FORWARD_BARS} saatte ≥%{MIN_GAIN_PCT*100:.1f} kazanç var mı?")
    print("=" * 65)
    
    # ─── Veri ───
    path = os.path.join(DATA_DIR, 'bist_hourly_dataset.parquet')
    print(f"\n📂 Veri yükleniyor: {path}")
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    print(f"   {df['tic'].nunique()} hisse, {len(df):,} satır")
    
    # ─── Etiket ───
    print(f"\n🏷️  Etiketler oluşturuluyor...")
    df = build_labels(df)
    pos_rate = df['label'].mean()
    print(f"   AL oranı  : %{pos_rate*100:.1f}")
    print(f"   ALMA oranı: %{(1-pos_rate)*100:.1f}")
    
    # ─── Eksik feature kontrolü ───
    missing = [f for f in FEATURES if f not in df.columns]
    if missing:
        print(f"\n⚠️  Eksik feature'lar: {missing}")
        FEATURES_USED = [f for f in FEATURES if f in df.columns]
        print(f"   Bunlar çıkarılacak. Kullanılacak: {len(FEATURES_USED)} özellik")
    else:
        FEATURES_USED = FEATURES
        print(f"   Tüm {len(FEATURES_USED)} özellik mevcut ✅")
    
    # ─── Train / Test Ayrımı ───
    train_df = df[df['date'] < '2026-01-01'].copy()
    test_df  = df[df['date'] >= '2026-01-01'].copy()
    
    X_train = train_df[FEATURES_USED].fillna(0)
    y_train = train_df['label']
    X_test  = test_df[FEATURES_USED].fillna(0)
    y_test  = test_df['label']
    
    del train_df, test_df, df
    gc.collect()
    
    print(f"\n📊 Veri Ayrımı:")
    print(f"   Eğitim (2023-2025): {len(X_train):,} örnek  | AL: %{y_train.mean()*100:.1f}")
    print(f"   Test   (2026):      {len(X_test):,} örnek   | AL: %{y_test.mean()*100:.1f}")
    
    # ─── XGBoost ───
    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    print(f"\n🧠 XGBoost eğitiliyor...")
    print(f"   Sınıf ağırlığı: {pos_weight:.2f}  | CPU çekirdekleri: 8/16 (diğerleri sistem için)")
    
    model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=5,
        learning_rate=0.04,
        subsample=0.75,
        colsample_bytree=0.75,
        min_child_weight=40,     # Daha yüksek → overfitting azaltır
        gamma=1.5,
        reg_alpha=0.1,
        reg_lambda=1.5,
        scale_pos_weight=pos_weight,
        eval_metric='auc',
        early_stopping_rounds=30,
        random_state=42,
        n_jobs=8,                # 16 CPU'nun 8'ini kullan (sistem için pay bırak)
        device='cuda'
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50
    )
    
    del X_train, y_train
    gc.collect()
    
    # ─── Sonuçlar ───
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    auc  = roc_auc_score(y_test, y_prob)
    acc  = accuracy_score(y_test, y_pred)
    base = y_test.mean()
    
    print(f"\n{'━'*65}")
    print(f" 🏆 TEST SONUÇLARI (2026 — Hiç görmemiş saatlik veri)")
    print(f"{'━'*65}")
    print(f" AUC Skoru       : {auc:.4f}")
    print(f" Genel Doğruluk  : %{acc*100:.2f}")
    print(f" Baseline (AL de): %{base*100:.2f}")
    print(f" Fark            : %{(acc-base)*100:+.2f}  {'✅' if acc > base else '❌'}")
    print(f"{'━'*65}")
    print(f"\n{classification_report(y_test, y_pred, target_names=['ALMA','AL'])}")
    
    # ─── Özellik Önemleri ───
    feat_imp = pd.Series(model.feature_importances_, index=FEATURES_USED).sort_values(ascending=False)
    print(f"🔑 En Önemli 8 Özellik:")
    for feat, imp in feat_imp.head(8).items():
        bar = "█" * int(imp * 150)
        print(f"   {feat:<22} {bar} {imp:.4f}")
    
    # ─── Kaydet ───
    save_path = os.path.join(MODEL_DIR, 'xgb_hourly_model.pkl')
    with open(save_path, 'wb') as f:
        pickle.dump(model, f)
    
    # Kullanılan feature listesini de kaydet (web app için)
    feat_path = os.path.join(MODEL_DIR, 'hourly_features.json')
    import json
    with open(feat_path, 'w') as f:
        json.dump(FEATURES_USED, f)
    
    print(f"\n💾 Model kaydedildi: {save_path}")
    print(f"💾 Feature listesi : {feat_path}")
    print("\n✅ Saatlik eğitim tamamlandı!")
    
    return model


if __name__ == "__main__":
    main()
