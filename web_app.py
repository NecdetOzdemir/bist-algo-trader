import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from flask import Flask, jsonify, request, render_template

# YFinance için sahte tarayıcı (Cloud IP'lerin banlanmasını engeller)
yf_session = requests.Session()
yf_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
})
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
        return 50.0
    
    try:
        # Son 15 gün saatlik verisi al
        df_h = yf.download(tic, period="15d", interval="1h", progress=False, session=yf_session)
        if df_h.empty: return 50.0
        
        # Sütunları düzelt (MultiIndex engelle)
        if isinstance(df_h.columns, pd.MultiIndex):
            df_h.columns = df_h.columns.get_level_values(0)
            
        df_h = add_hourly_indicators(df_h)
        if df_h.empty: return 50.0
        
        latest_h = df_h.iloc[-1:]
        X = latest_h[hourly_features].fillna(0)
        
        prob = xgb_hourly_model.predict_proba(X)[0][1]
        
        # Olasılığı 0-100 arasına ölçekle (0.35 ile 0.55 arasını esnet)
        score = (prob - 0.35) * (100 / (0.55 - 0.35))
        return max(0, min(100, score))
        
    except Exception as e:
        print(f"Saatlik tahmin hatası ({tic}): {e}")
        return 50.0

def detect_smc(df):
    """
    Smart Money Concepts (SMC) tespit algoritması.
    Balinaların piyasaya bıraktığı ayak izlerini (Order Block, FVG, Liquidity Sweep) arar.
    """
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
    current_price = float(df.iloc[-1]['Close'])
    
    # 1. Fair Value Gap (FVG)
    for i in range(2, len(df_recent)):
        c1_h = float(df_recent.iloc[i-2]['High'])
        c1_l = float(df_recent.iloc[i-2]['Low'])
        c3_h = float(df_recent.iloc[i]['High'])
        c3_l = float(df_recent.iloc[i]['Low'])
        
        # Bullish FVG (Gap up)
        if c3_l > c1_h:
            smc_data['fvg_bullish'] = round((c1_h + c3_l) / 2, 2)
            
        # Bearish FVG (Gap down)
        if c3_h < c1_l:
            smc_data['fvg_bearish'] = round((c1_l + c3_h) / 2, 2)
            
    # 2. Order Block (OB)
    for i in range(1, len(df_recent)):
        prev_open = float(df_recent.iloc[i-1]['Open'])
        prev_close = float(df_recent.iloc[i-1]['Close'])
        curr_open = float(df_recent.iloc[i]['Open'])
        curr_close = float(df_recent.iloc[i]['Close'])
        
        # Hacim veya sıçrama varsa
        if curr_open > 0:
            curr_pct = (curr_close - curr_open) / curr_open
            if curr_pct > 0.035 and prev_close < prev_open:
                # Bullish OB (Son kırmızı mum)
                smc_data['ob_bullish'] = round(float(df_recent.iloc[i-1]['Low']), 2)
                
            if curr_pct < -0.035 and prev_close > prev_open:
                # Bearish OB (Son yeşil mum)
                smc_data['ob_bearish'] = round(float(df_recent.iloc[i-1]['High']), 2)
            
    # 3. Liquidity Sweep
    past_low = float(df_recent.iloc[:-3]['Low'].min())
    past_high = float(df_recent.iloc[:-3]['High'].max())
    recent_candle = df_recent.iloc[-1]
    
    if float(recent_candle['Low']) < past_low and float(recent_candle['Close']) > past_low:
        smc_data['liquidity_sweep'] = "BULLISH_SWEEP"
    elif float(recent_candle['High']) > past_high and float(recent_candle['Close']) < past_high:
        smc_data['liquidity_sweep'] = "BEARISH_SWEEP"

    # Yorum Üret
    if smc_data['ob_bullish'] and current_price > smc_data['ob_bullish'] and (current_price - smc_data['ob_bullish'])/current_price < 0.08:
        smc_data['smc_comment'].append(f"Fiyat, balinaların {smc_data['ob_bullish']} TL'deki Alıcı Emir Bloğuna (Order Block) çok yakın. Burası güçlü bir sıçrama (alım) tahtasıdır.")
    if smc_data['liquidity_sweep'] == 'BULLISH_SWEEP':
        smc_data['smc_comment'].append("Son düşüşte küçük yatırımcının stopları kasıtlı olarak patlatıldı (Likidite Avı) ve fiyat toparlandı. Balinalar malı topladı, yön yukarı olabilir.")
    if smc_data['fvg_bullish'] and current_price > smc_data['fvg_bullish'] and (current_price - smc_data['fvg_bullish'])/current_price < 0.05:
        smc_data['smc_comment'].append(f"Fiyat {smc_data['fvg_bullish']} TL'deki Dengesizlik Boşluğuna (FVG) doğru çekiliyor. Bu boşluk dolduğunda sert tepki alımı gelebilir.")
        
    return smc_data

@app.route('/api/analyze/<ticker>')
def analyze_ticker(ticker):
    data, status_code = get_ticker_analysis_data(ticker)
    return jsonify(data), status_code

def get_ticker_analysis_data(ticker):
    try:
        # Ticker formatı (.IS ekle)
        tic = ticker.upper().replace(' ', '')
        if not tic.endswith('.IS') and not tic.startswith('^'):
            tic += '.IS'
            
        # Son 1 yıllık (yaklaşık 250 işlem günü) veriyi çek ki hareketli ortalamalar doğru hesaplansın.
        # "period" kullanmak bugünün canlı fiyatının (eğer borsa açıksa) dahil edilmesini garanti eder.
        df = yf.download(tic, period="1y", progress=False, session=yf_session)
        if df.empty:
            return {'error': 'Hisse senedi verisi bulunamadı. Kodu kontrol edin.'}, 404
            
        df = df.reset_index()
        # Sütun adları bazen MultiIndex gelebiliyor yfinance sürümüne göre, bunu düzeltelim
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Macro veri
        end_date = (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=200)).strftime('%Y-%m-%d')
        macro = fetch_macro_data(start_date, end_date)
        macro = macro.reset_index()
        
        df['Date'] = pd.to_datetime(df['Date'])
        macro['Date'] = pd.to_datetime(macro['Date'])
        
        df = pd.merge(df, macro, on='Date', how='left')
        df.fillna(method='ffill', inplace=True)
        
        # SMC (Akıllı Para) Analizi (Tüm veriler varken hesapla)
        smc_data = detect_smc(df)
        
        # İndikatörler
        df = add_technical_indicators(df)
        if df is None or df.empty:
            return {'error': 'Teknik analiz için yeterli geçmiş veri yok.'}, 400
            
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

        # --- SMA Hesapla ---
        sma20  = float(df['close'].rolling(20).mean().iloc[-1])
        sma50  = float(df['close'].rolling(50).mean().iloc[-1])
        sma200_series = df['close'].rolling(200).mean()
        sma200 = float(sma200_series.iloc[-1]) if len(df) >= 200 else sma50
        if current_price > sma50 and sma50 > sma200:
            sma_trend = 'strong_up'
        elif current_price > sma50:
            sma_trend = 'up'
        else:
            sma_trend = 'down'

        # ============================================================
        # KUANTUM CERCEVE — Composite Score + ATR Stop + EV + Kelly
        # ============================================================
        comp = 0
        if current_price > sma200: comp += 1
        if current_price > sma50:  comp += 1
        if sma50 > sma200:         comp += 1
        if 40 <= rsi <= 65:        comp += 2
        elif 30 <= rsi < 40:       comp += 1
        if macd > macd_signal:     comp += 1
        if rel_volume >= 1.20:     comp += 1
        ai_contrib = min(3, int(active_score / 100 * 3 + 0.5))
        comp += ai_contrib
        # comp: 0-10 arasi

        # ATR Tabanli Stop/Hedef (RR: 1:2)
        atr_stop = round(current_price - 1.5 * atr, 2)
        atr_tp   = round(current_price + 3.0 * atr, 2)
        atr_stop_pct = round((current_price - atr_stop) / current_price * 100, 2)
        atr_tp_pct   = round((atr_tp - current_price) / current_price * 100, 2)

        # Expected Value (EV)
        win_rate  = min(0.60, max(0.40, active_score / 100))
        loss_rate = 1.0 - win_rate
        ev_pct = round(win_rate * atr_tp_pct - loss_rate * atr_stop_pct, 2)

        # Kelly Kriteri (Yarim Kelly)
        kelly_full = (win_rate * 2.0 - loss_rate) / 2.0
        kelly_half = max(0.0, round(kelly_full * 0.5 * 100, 1))

        # Sabit %2/%4 (yedek)
        plan_stop = round(current_price * 0.98, 2)
        plan_tp   = round(current_price * 1.04, 2)
        
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
        
        # Camarilla (L3/H3 - Frank Ochoa 'Pivot Boss')
        # Balinaların en sevdiği destek/direnç noktaları
        cam_range = prev_h - prev_l
        cam_h3 = round(prev_c + cam_range * (1.1 / 4), 2)
        cam_l3 = round(prev_c - cam_range * (1.1 / 4), 2)
        
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
                
        # --- VPA ve TTM Squeeze (Akıllı Para Sinyalleri) ---
        if latest_data.get('vpa_anomaly', False):
            smc_data['smc_comment'].append(f"🔍 VPA ANORMALLİĞİ: Mum boyutu çok küçük olmasına rağmen hacim devasa! Balinalar burada {current_price:.2f} seviyesinde gizlice mal topluyor (Akümülasyon) olabilir.")
            
        if latest_data.get('squeeze_on', False):
            smc_data['smc_comment'].append(f"🔥 TTM SQUEEZE: Hisse son 20 günün en dar aralığına sıkıştı (Bollinger, Keltner'in içine girdi). Yakında çok sert bir yöne patlama (Breakout) bekleniyor!")
        
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
        entry = current_price
        
        # Sadece LONG (Alım) yönlü mantıklı seviyeler
        if current_price <= s2:
            stop_loss = current_price * 0.97
            take_profit = s1
        elif current_price <= s1:
            stop_loss = s2
            take_profit = pp
        elif current_price <= pp:
            stop_loss = s1
            take_profit = r1
        elif current_price <= r1:
            stop_loss = pp
            take_profit = r2
        elif current_price <= r2:
            stop_loss = r1
            take_profit = current_price * 1.03
        else:
            stop_loss = r2
            take_profit = current_price * 1.03
            
        # GÜVENLİK KİLİDİ: Stop loss asla giriş fiyatından büyük veya eşit olamaz!
        if stop_loss >= entry:
            stop_loss = entry * 0.98
            
        # GÜVENLİK KİLİDİ: Take profit asla giriş fiyatından küçük veya eşit olamaz!
        if take_profit <= entry:
            take_profit = entry * 1.03

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
            
        return {
            'ticker': ticker.upper().replace('.IS', ''),
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
            'return_1d': round(latest_data['return_1d'], 4) if 'return_1d' in latest_data else 0,
            'date': latest_data['date'].strftime('%d %B %Y'),
            # SMC Verileri
            'smc_comments': smc_data['smc_comment'],
            'cam_h3': cam_h3,
            'cam_l3': cam_l3,
            # SMA ve Sabah Planı
            'sma20': round(sma20, 2),
            'sma50': round(sma50, 2),
            'sma200': round(sma200, 2),
            'sma_trend': sma_trend,
            'plan_stop': plan_stop,
            'plan_tp': plan_tp,
            # Kuantum Çerçeve
            'composite_score': comp,           # 0-10 arası çok faktörlü puan
            'atr_stop': atr_stop,              # ATR tabanlı stop fiyatı
            'atr_tp': atr_tp,                  # ATR tabanlı hedef fiyat
            'atr_stop_pct': atr_stop_pct,      # Stop mesafesi (%)
            'atr_tp_pct': atr_tp_pct,          # Hedef mesafesi (%)
            'ev_pct': ev_pct,                  # Beklenen Değer (EV) %
            'kelly_half': kelly_half,          # Önerilen pozisyon büyüklüğü (Yarım Kelly %)
            'win_rate_est': round(win_rate * 100, 1),  # Tahmini kazanma olasılığı %
        }, 200
        
    except Exception as e:
        traceback.print_exc()
        return {'error': f"Sunucu Hatası: {str(e)}"}, 500

import concurrent.futures
import threading
import time
from universe import BIST_100

CACHE = {
    'scan_results': [],
    'top_scores': [],
    'last_updated': 0,
    'is_scanning': False
}

def background_scanner():
    """Arka planda her 15 dakikada bir BIST100'ü tarar ve cache'e yazar."""
    while True:
        try:
            print("[CACHE BOT] Arka plan taraması başlatılıyor...")
            CACHE['is_scanning'] = True
            
            results = []
            for tic in BIST_100:
                try:
                    data, status_code = get_ticker_analysis_data(tic.replace('.IS', ''))
                    if status_code == 200 and 'error' not in data:
                        results.append(data)
                except Exception:
                    pass
                # Sunucunun donmaması (Kullanıcının yaptığı işlemlere CPU kalması) için ufak bir nefes payı:
                time.sleep(0.5)
            
            # Tarama Filtreleri
            scan_filtered = [d for d in results if 20 < d.get('rsi', 100) < 40 and d.get('score', 0) > 55 and d.get('return_1d', 0) > -0.05]
            top_filtered = [d for d in results if d.get('score', 0) > 55]
            
            CACHE['scan_results'] = sorted(scan_filtered, key=lambda x: x.get('score', 0), reverse=True)
            CACHE['top_scores'] = sorted(top_filtered, key=lambda x: x.get('score', 0), reverse=True)[:10]
            CACHE['last_updated'] = time.time()
            CACHE['is_scanning'] = False
            
            print("[CACHE BOT] Tarama bitti. Veriler hazır.")
        except Exception as e:
            print(f"[CACHE BOT] Hata: {e}")
            CACHE['is_scanning'] = False
            
        time.sleep(900) # 15 dakika (900 saniye) bekle

# GÜÇLÜ SUNUCUYA GEÇENE KADAR ARKA PLAN BOTUNU DEVRE DIŞI BIRAKTIK
# threading.Thread(target=background_scanner, daemon=True).start()

@app.route('/api/scan_chunk')
def scan_chunk():
    """Render'ın 50 saniye zaman aşımına takılmamak için hisseleri parça parça tarayan endpoint"""
    start = int(request.args.get('start', 0))
    limit = int(request.args.get('limit', 15))
    
    chunk_tickers = BIST_100[start:start+limit]
    results = []
    
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_tic = {executor.submit(get_ticker_analysis_data, tic.replace('.IS', '')): tic for tic in chunk_tickers}
        for future in concurrent.futures.as_completed(future_to_tic):
            try:
                data, status_code = future.result()
                if status_code == 200 and 'error' not in data:
                    results.append(data)
            except Exception:
                pass
                
    return jsonify({'results': results})

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
