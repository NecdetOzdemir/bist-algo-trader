"""
Flask API Sunucusu — BIST Trade Asistan
"""

from flask import Flask, request, jsonify, send_from_directory
import os
import json
from datetime import datetime

app = Flask(__name__, static_folder='static')

# ─── Yardımcı Fonksiyonlar ───────────────────────────────────────


def success(data: dict) -> tuple:
    data['status'] = 'ok'
    data['timestamp'] = datetime.now().strftime('%d.%m.%Y %H:%M')
    return jsonify(data), 200


def error(message: str, code: int = 400) -> tuple:
    return jsonify({'status': 'error', 'message': message}), code


# ─── Statik Dosya Sunumu ─────────────────────────────────────────


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


# ─── API Endpoint'leri ───────────────────────────────────────────


@app.route('/api/scan', methods=['GET'])
def api_scan():
    """
    Hisse tarayıcı.
    GET /api/scan?universe=bist30&top=15
    """
    try:
        from scanner import scan
        universe = request.args.get('universe', 'bist30')
        top_n    = int(request.args.get('top', 15))
        top_n    = min(top_n, 50)  # Max 50

        results = scan(universe, top_n)
        return success({
            'universe': universe,
            'count': len(results),
            'results': results,
        })
    except Exception as e:
        return error(f"Tarama hatası: {str(e)}")


@app.route('/api/analyze', methods=['GET'])
def api_analyze():
    """
    Tek hisse detaylı analiz.
    GET /api/analyze?ticker=THYAO
    """
    try:
        from analyzer import analyze
        ticker = request.args.get('ticker', '').strip()
        if not ticker:
            return error("Hisse kodu giriniz. Örn: /api/analyze?ticker=THYAO")

        result = analyze(ticker)
        if result.get('error'):
            return error(result.get('message', 'Analiz hatası'))

        return success(result)
    except Exception as e:
        return error(f"Analiz hatası: {str(e)}")


@app.route('/api/compare', methods=['GET'])
def api_compare():
    """
    İki hisseyi karşılaştır.
    GET /api/compare?ticker1=EREGL&ticker2=GARAN
    """
    try:
        from comparator import compare
        t1 = request.args.get('ticker1', '').strip()
        t2 = request.args.get('ticker2', '').strip()

        if not t1 or not t2:
            return error("İki hisse kodu giriniz. Örn: /api/compare?ticker1=EREGL&ticker2=GARAN")
        if t1.upper() == t2.upper():
            return error("Aynı iki hisseyi karşılaştıramazsınız.")

        result = compare(t1, t2)
        if result.get('error'):
            return error(result['error'])

        return success(result)
    except Exception as e:
        return error(f"Karşılaştırma hatası: {str(e)}")


@app.route('/api/risk', methods=['POST'])
def api_risk():
    """
    Risk ve pozisyon büyüklüğü hesapla.
    POST /api/risk
    Body: { account_size, entry_price, stop_price, target_price (opsiyonel), risk_pct }
    """
    try:
        from risk_calculator import calculate_with_target, calculate_position
        data = request.get_json()
        if not data:
            return error("JSON body gerekli")

        account = float(data.get('account_size', 0))
        entry   = float(data.get('entry_price', 0))
        stop    = float(data.get('stop_price', 0))
        target  = float(data.get('target_price', 0))
        risk_pct = float(data.get('risk_pct', 2.0))

        if account <= 0:
            return error("Hesap büyüklüğü sıfırdan büyük olmalı.")

        if target > 0:
            result = calculate_with_target(account, entry, stop, target, risk_pct)
        else:
            result = calculate_position(account, entry, stop, risk_pct)

        if result.get('error'):
            return error(result.get('message', 'Hesaplama hatası'))

        return success(result)
    except ValueError:
        return error("Geçersiz sayı formatı.")
    except Exception as e:
        return error(f"Risk hesaplama hatası: {str(e)}")


@app.route('/api/clear-cache', methods=['POST'])
def api_clear_cache():
    """Cache'i temizle — güncel veri için."""
    try:
        from data_fetcher import clear_cache
        ticker = request.args.get('ticker')
        clear_cache(ticker)
        msg = f"Cache temizlendi: {ticker}" if ticker else "Tüm cache temizlendi"
        return success({'message': msg})
    except Exception as e:
        return error(str(e))


@app.route('/api/health', methods=['GET'])
def api_health():
    """Sistem sağlık kontrolü."""
    return success({
        'system': 'BIST Trade Asistan',
        'version': '1.0.0',
        'message': 'Sistem çalışıyor ✅',
    })


# ─── Uygulama Başlatma ───────────────────────────────────────────


if __name__ == '__main__':
    print("=" * 55)
    print("  BIST Trade Asistan — Başlatılıyor")
    print("  http://localhost:5000")
    print("=" * 55)

    # Static klasörü oluştur
    os.makedirs('static', exist_ok=True)

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
    )
