import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import pickle
import traceback

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'ml_models')
DATA_DIR = os.path.join(BASE_DIR, 'ml_data')

# Modelleri önbelleğe al (Uygulama açılırken 1 kere yüklenir)
xgb_model = None
xgb_1day_model = None
try:
    with open(os.path.join(MODEL_DIR, 'xgb_selector.pkl'), 'rb') as f:
        xgb_model = pickle.load(f)
except Exception as e:
    print(f"Uyarı: XGBoost (5 gün) modeli yüklenemedi. ({e})")

try:
    with open(os.path.join(MODEL_DIR, 'xgb_1day_model.pkl'), 'rb') as f:
        xgb_1day_model = pickle.load(f)
    print("✅ 1 Günlük Yön Modeli yüklendi.")
except Exception as e:
    print(f"Uyarı: XGBoost (1 gün) modeli yüklenemedi. ({e})")

xgb_hourly_model = None
hourly_features = []
try:
    with open(os.path.join(MODEL_DIR, 'xgb_hourly_model.pkl'), 'rb') as f:
        xgb_hourly_model = pickle.load(f)
    import json
    with open(os.path.join(MODEL_DIR, 'hourly_features.json'), 'r') as f:
        hourly_features = json.load(f)
    print("✅ Saatlik XGBoost Modeli yüklendi.")
except Exception as e:
    print(f"Uyarı: XGBoost (Saatlik) modeli yüklenemedi. ({e})")

# ml_data_prep'ten işlemleri çekiyoruz
sys.path.append(BASE_DIR)
try:
    from ml_data_prep import add_technical_indicators, fetch_macro_data
    from ml_hourly_prep import add_hourly_indicators
except ImportError:
    print("ml_data_prep veya ml_hourly_prep bulunamadı, script çalışmayabilir.")

@app.route('/')
def index():
    return render_template('index.html')

def get_hourly_prediction(tic):
    """Saatlik veri çeker ve xgb_hourly_model ile anlık (3 saatlik) tahmin yapar."""
    if not xgb_hourly_model or not hourly_features:
        return 50.0  # Nötr

    try:
        # Macro data
        dfs = {}
        for t in ['XU100.IS', 'TRY=X']:
            df = yf.download(t, period='7d', interval='1h', progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.index.tz:
                df.index = df.index.tz_convert('UTC').tz_localize(None)
            dfs[t] = df

        bist = dfs['XU100.IS']
        usd = dfs['TRY=X']
        macro = pd.DataFrame({
            'bist_close': bist['Close'],
            'bist_trend': bist['Close'].pct_change(),
            'bist_volatility': (bist['High'] - bist['Low']) / bist['Close'],
            'usd_close': usd['Close'],
            'usd_trend': usd['Close'].pct_change()
        }).ffill()

        # Stock data
        df = yf.download(tic, period='15d', interval='1h', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.index.tz:
            df.index = df.index.tz_convert('UTC').tz_localize(None)

        df = df.join(macro, how='left').ffill()
        if 'usd_close' in df.columns:
            df['Close_USD'] = df['Close'] / df['usd_close'].replace(0, np.nan)

        df = add_hourly_indicators(df)
        if df is None or df.empty:
            return 50.0

        df.columns = [c.lower() for c in df.columns]
        latest = df.iloc[-1]
        
        X = pd.DataFrame([latest[hourly_features].values], columns=hourly_features).fillna(0)
        prob = float(xgb_hourly_model.predict_proba(X)[0][1])
        
        # Olasılığı 0-100'e yay (Model ~0.3 - ~0.65 arası veriyor)
        MIN_P, MAX_P = 0.35, 0.65
        scaled = (prob - MIN_P) / (MAX_P - MIN_P) * 100
        return max(0.0, min(100.0, scaled))
        
    except Exception as e:
        print(f"Saatlik tahmin hatası ({tic}): {e}")
        return 50.0


@app.route('/api/analyze/<ticker>')
def analyze_ticker(ticker):
    try:
        # Ticker formatı (.IS ekle)
        tic = ticker.upper().replace(' ', '')
        if not tic.endswith('.IS') and not tic.startswith('^'):
            tic += '.IS'
            
        # Son 200 günü çek (Hareketli ortalamalar 60 günlük veriye ihtiyaç duyar)
        end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=200)).strftime('%Y-%m-%d')
        
        df = yf.download(tic, start=start_date, end=end_date, progress=False)
        if df.empty:
            return jsonify({'error': 'Hisse senedi verisi bulunamadı. Kodu kontrol edin.'}), 404
            
        df = df.reset_index()
        # Sütun adları bazen MultiIndex gelebiliyor yfinance sürümüne göre, bunu düzeltelim
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Macro veri
        macro = fetch_macro_data(start_date, end_date)
        macro = macro.reset_index()
        
        df['Date'] = pd.to_datetime(df['Date'])
        macro['Date'] = pd.to_datetime(macro['Date'])
        
        df = pd.merge(df, macro, on='Date', how='left')
        df.fillna(method='ffill', inplace=True)
        
        # İndikatörler
        df = add_technical_indicators(df)
        if df is None or df.empty:
            return jsonify({'error': 'Teknik analiz için yeterli geçmiş veri yok.'}), 400
            
        df['close_usd'] = df['Close'] / df['usd_close']
        
        df.columns = [c.lower() for c in df.columns]
        latest_data = df.iloc[-1]
        
        # XGBoost Skor Hesaplama
        FEATURES = [
            'macd', 'macd_signal', 'macd_hist', 'rsi', 'cci', 'adx', 'atr',
            'bb_high', 'bb_low', 'bb_width', 'vol_10_sma', 'rel_volume_10',
            'mfi', 'return_1d', 'gap_pct', 'bist_trend', 'bist_volatility',
            'usd_trend', 'close_usd'
        ]
        
        score = 0
        if xgb_model:
            X = pd.DataFrame([latest_data[FEATURES].values], columns=FEATURES).fillna(0)
            raw_prob = float(xgb_model.predict_proba(X)[0][1])
            
            # Yapay zekanın ham tahminleri genellikle 0.35 ile 0.57 arasında yoğunlaşır.
            # Bunu kullanıcı dostu 0-100 aralığına ölçeklendiriyoruz.
            MIN_PROB = 0.35
            MAX_PROB = 0.57
            scaled_score = (raw_prob - MIN_PROB) / (MAX_PROB - MIN_PROB) * 100
            score = max(0.0, min(100.0, scaled_score))
        
        # 1 Günlük Yön Skoru — Ana tavsiye bu modelden geliyor!
        direction_prob = 0.5  # Varsayılan
        direction_score = 50
        if xgb_1day_model:
            X = pd.DataFrame([latest_data[FEATURES].values], columns=FEATURES).fillna(0)
            direction_prob = float(xgb_1day_model.predict_proba(X)[0][1])
            # Bu modelin probları 0.2-0.6 arasında, normalize edelim
            MIN_P, MAX_P = 0.20, 0.60
            direction_score = max(0.0, min(100.0, (direction_prob - MIN_P) / (MAX_P - MIN_P) * 100))
            
        # Saatlik model tahmini (Çok daha kısa vade)
        hourly_score = get_hourly_prediction(tic)
            
        # Yön tahmininde 1 günlük ve saatlik skoru harmanla
        # %60 Günlük, %40 Saatlik
        if xgb_1day_model and xgb_hourly_model:
            active_score = (direction_score * 0.6) + (hourly_score * 0.4)
        else:
            active_score = direction_score if xgb_1day_model else score
            
        # Fiyat ve İndikatörler
        current_price = float(latest_data['close'])
        atr = float(latest_data['atr'])
        rsi = float(latest_data['rsi'])
        macd = float(latest_data['macd'])
        macd_signal = float(latest_data['macd_signal'])
        mfi = float(latest_data['mfi'])
        rel_volume = float(latest_data.get('rel_volume_10', 1.0))
        
        # --- PIVOT POINT SEVİYELERİ (Bir önceki günün OHLC'siyle) ---
        # Tüm BIST profesyonelleri bu seviyelere bakar.
        # S1 destek, R1 direnctır. Fiyata çok daha yakın olurlar.
        prev = df.iloc[-2]  # Bir önceki gün
        prev_h = float(prev['high'])
        prev_l = float(prev['low'])
        prev_c = float(prev['close'])
        
        pp  = (prev_h + prev_l + prev_c) / 3
        r1  = round(2 * pp - prev_l, 2)   # İlk direnç (~%1-2 yukarı)
        r2  = round(pp + (prev_h - prev_l), 2)  # İkinci direnç (~%3-4 yukarı)
        s1  = round(2 * pp - prev_h, 2)   # İlk destek (~%1-2 aşağı)
        s2  = round(pp - (prev_h - prev_l), 2)  # İkinci destek (~%3-4 aşağı)
        pp  = round(pp, 2)
        
        # --- MANUPLASYON ANALİZİ (Shakeout tespiti) ---
        # Eğer hisse düştüyse bu sahte mi, gerçek mi?
        daily_return = float(latest_data.get('return_1d', 0))
        is_down_day = daily_return < -0.01  # %1'den fazla düşme
        
        shakeout_score = 0
        shakeout_signal = None
        shakeout_comment = None
        if is_down_day:
            if rel_volume < 0.60: shakeout_score += 2   # Düşük hacim = güçlü sahte sinyal
            if mfi > 50: shakeout_score += 2             # Para içeride kalmaya devam
            if rsi > 40: shakeout_score += 1             # RSI diverjansı
            
            if shakeout_score >= 4:
                shakeout_signal = "SHAKEOUT ⚠️"
                shakeout_comment = f"Bu düşüş SAHTE olabilir! Hacim ortalamanın %{rel_volume*100:.0f}'inde, para hissede kalmaya devam ediyor. {s1:.2f} TL kırılmadan satma."
            elif rel_volume > 1.30 and mfi < 35:
                shakeout_signal = "GERÇEK BASKI 🔴"
                shakeout_comment = f"Bu düşüş GERÇEK görünüyor. Yüksek hacimle satış var, akıllı para çıkıyor. {s2:.2f} TL stop düşünebilirsin."
            else:
                shakeout_signal = "BELİRSİZ 🟡"
                shakeout_comment = "Düşüşün güç kaynağı net değil. İhtiyatlı ol."
        
        # Yön tahmini: 1 Günlük model (ana) + MACD/RSI destekleyici sinyal
        bullish_points = 0
        if active_score > 50: bullish_points += 3  # 1 günlük modelden gelen ağırlıklı sinyal
        if macd > macd_signal: bullish_points += 1
        if 40 < rsi < 70: bullish_points += 1
        if rsi < 35: bullish_points += 2
        
        is_bullish = bullish_points >= 4
        
        # Tavsiye yorumu için aktif skoru kullan
        display_score = active_score
        
        # --- Trading Seviyeleri (Pivot Point Bazlı DİNAMİK) ---
        if is_bullish:
            if current_price < s1:
                entry = current_price
                stop_loss = s2
                take_profit = pp
            elif current_price < pp:
                entry = current_price
                stop_loss = s1
                take_profit = r1
            elif current_price < r1:
                entry = current_price
                stop_loss = pp
                take_profit = r2
            elif current_price < r2:
                entry = current_price
                stop_loss = r1
                take_profit = current_price * 1.04 # R2 kırılmış, yeni hedef
            else:
                entry = current_price
                stop_loss = r2
                take_profit = current_price * 1.04
        else:
            if current_price > r1:
                entry = current_price
                stop_loss = r2
                take_profit = pp
            elif current_price > pp:
                entry = current_price
                stop_loss = r1
                take_profit = s1
            elif current_price > s1:
                entry = current_price
                stop_loss = pp
                take_profit = s2
            else:
                entry = current_price
                stop_loss = s1
                take_profit = current_price * 0.96

        risk   = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0
        gain_pct = round(reward / entry * 100, 2) if entry > 0 else 0
        loss_pct = round(risk / entry * 100, 2) if entry > 0 else 0
        
        if display_score > 75: 
            action = "GÜÇLÜ AL 🚀"
            color = "#00ffa3"
            comment = f"Yapay zeka çok güçlü yükseliş bekliyor. {entry:.2f} seviyesinden alım yapıp {take_profit:.2f} hedeflenebilir. Stop: {stop_loss:.2f}"
        elif display_score > 58: 
            action = "AL 🟢"
            color = "#00d2ff"
            comment = f"Model yükseliş yönünde. Güncel fiyattan ({entry:.2f}) alım düşünülebilir. Hedef {take_profit:.2f}, Stop: {stop_loss:.2f}"
        elif display_score > 42: 
            action = "BEKLE 🟡"
            color = "#ffd700"
            comment = f"Model net bir yön görmüyor. Fiyat şu an {current_price:.2f}. Pivot noktası {pp:.2f} TL seviyesini izle."
        elif display_score > 28: 
            action = "SAT / ALMA 🟠"
            color = "#ff7b00"
            comment = f"Model düşüşü işaret ediyor. Yeni alımdan kaçın, elindeyse {stop_loss:.2f} seviyesini stop olarak izle."
        else: 
            action = "GÜÇLÜ ALMA 🔴"
            color = "#ff003c"
            comment = f"Güçlü aşağı sinyal. Elinde bu hisse varsa {s1:.2f} TL kırılırsa kes."
            
        return jsonify({
            'ticker': ticker.upper(),
            'score': round(display_score, 1),
            'action': action,
            'color': color,
            'comment': comment,
            'price': round(current_price, 2),
            'direction': 'up' if is_bullish else 'down',
            # Pivot Seviyeleri
            'pp': pp, 'r1': r1, 'r2': r2, 's1': s1, 's2': s2,
            # Trading Plan
            'entry': entry,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'rr_ratio': rr_ratio,
            'gain_pct': gain_pct,
            'loss_pct': loss_pct,
            # Manuplasyon Sinyali
            'shakeout_signal': shakeout_signal,
            'shakeout_comment': shakeout_comment if shakeout_signal else None,
            # Teknik Detaylar
            'rsi': round(rsi, 1),
            'macd': round(macd, 2),
            'mfi': round(mfi, 1),
            'rel_volume': round(rel_volume, 2),
            'atr': round(atr, 2),
            'date': latest_data['date'].strftime('%d %B %Y')
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f"Sunucu Hatası: {str(e)}"}), 500

@app.route('/api/recommendations')
def get_recommendations():
    try:
        data_path = os.path.join(DATA_DIR, 'bist_rl_dataset.parquet')
        if not os.path.exists(data_path):
            return jsonify({'status': 'error', 'message': 'Veri seti bulunamadı.'}), 404
            
        df = pd.read_parquet(data_path)
        
        # Sütunları küçük harfe çevir
        df.columns = [c.lower() for c in df.columns]
        
        # En güncel tarihi bul
        latest_date = df['date'].max()
        df_today = df[df['date'] == latest_date].copy()
        
        # close_usd sütununu ml_train de hesaplanmıştı ama garanti olsun diye kontrol edelim
        if 'close_usd' not in df_today.columns and 'usd_close' in df_today.columns:
            df_today['close_usd'] = df_today['close'] / df_today['usd_close']
            
        FEATURES = [
            'macd', 'macd_signal', 'macd_hist', 'rsi', 'cci', 'adx', 'atr',
            'bb_high', 'bb_low', 'bb_width', 'vol_10_sma', 'rel_volume_10',
            'mfi', 'return_1d', 'gap_pct', 'bist_trend', 'bist_volatility',
            'usd_trend', 'close_usd'
        ]
        
        if xgb_model:
            X_today = df_today[FEATURES].fillna(0)
            raw_probs = xgb_model.predict_proba(X_today)[:, 1]
            
            # Yüzdelik dilim (Percentile) hesaplayarak 0-100 arasına oturt
            # Böylece en yüksek hisse her zaman 100 puan, ortalama hisse 50 puan alır.
            df_today['score'] = pd.Series(raw_probs).rank(pct=True).values * 100
        else:
            df_today['score'] = 0
            
        top_stocks = df_today.nlargest(15, 'score')
        
        results = []
        for _, row in top_stocks.iterrows():
            tic = str(row['tic']).replace('.IS', '')
            results.append({
                'ticker': tic,
                'score': round(row['score'], 1)
            })
            
        return jsonify({
            'status': 'success',
            'date': str(latest_date),
            'list': results
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
