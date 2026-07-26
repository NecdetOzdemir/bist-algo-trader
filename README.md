# BIST Algo Trader (AI Destekli)

Bu proje, Borsa İstanbul (BIST) hisseleri için **XGBoost Makine Öğrenmesi** kullanarak yön tahmini ve dinamik al/sat noktaları (Trade Planı) üreten yapay zeka destekli bir analiz aracıdır.

## Özellikler

- **Çift Modelli Yapay Zeka:** 
  - *Günlük Model:* 1 gün sonrasının trendini öngörür.
  - *Saatlik Model:* 3 saatlik çok kısa vadeli hareketleri (intraday) analiz eder.
- **Dinamik Pivot Seviyeleri:** Fiyatın güncel durumuna göre matematiksel olarak mantıklı giriş (Entry), hedef (Take Profit) ve zarar-kes (Stop-Loss) seviyeleri belirler.
- **Silkeleme (Shakeout) Tespiti:** Hacim, RSI ve Para Akışı (MFI) indikatörlerini birleştirerek sahte düşüşleri (büyük yatırımcı manipülasyonlarını) tespit eder ve uyarır.
- **Web Arayüzü:** Flask tabanlı modern bir arayüz ile her şey tek bir tıklamayla analiz edilebilir.

## Kurulum ve Kullanım

### 1. Gereksinimleri Yükleyin
Proje dizininde terminali açıp gerekli kütüphaneleri yükleyin:
```bash
pip install -r requirements.txt
```

### 2. Yapay Zeka Modellerini Eğitin (Opsiyonel / Gerekliyse)
Verileri güncelleyip modelleri kendi cihazınızda eğitmek isterseniz:
```bash
# 1 Günlük Model Eğitimi (BIST100 - 5 Yıllık Veri)
python3 ml_train_1day.py

# Saatlik Model Eğitimi (BIST100 - Son 2 Yıllık Veri)
python3 ml_hourly_prep.py
python3 ml_train_hourly.py
```
*Not: İndirilen veriler `ml_data/` klasörüne, eğitilen modeller `ml_models/` klasörüne kaydedilir (büyük boyutlu oldukları için GitHub'a yüklenmemiştir).*

### 3. Web Arayüzünü Başlatın
Aşağıdaki komutla Flask sunucusunu başlatın:
```bash
python3 web_app.py
```
Tarayıcınızda [http://localhost:5000](http://localhost:5000) adresine giderek sistemi kullanmaya başlayabilirsiniz.

## Dosya Yapısı

- `web_app.py`: Ana web sunucusu ve API mantığı.
- `ml_data_prep.py` / `ml_hourly_prep.py`: Yahoo Finance üzerinden veri çekme ve teknik indikatörleri hesaplama işlemleri.
- `ml_train_1day.py` / `ml_train_hourly.py`: Makine öğrenmesi (XGBoost) algoritmalarını eğiten dosyalar.
- `universe.py`: Taranacak ve desteklenen BIST hisse listeleri.
- `ml_direction_backtest.py`: Geçmiş veriler üzerinde yapay zekanın başarısını test eden simülasyon (Backtest) aracı.
- `templates/` ve `static/`: Web sitesi arayüz tasarımı (HTML/CSS/JS).

---
*Yasal Uyarı: Bu araç eğitim ve araştırma amaçlıdır, yatırım tavsiyesi içermez.*
