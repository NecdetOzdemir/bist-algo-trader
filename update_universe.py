"""
BIST Hisse Listesi Güncelleyici
Borsa İstanbul'dan güncel hisse listesini çeker ve universe.py'yi günceller.
"""

import requests
import pandas as pd
import time
import json
import os
import sys
from datetime import datetime

# Borsa İstanbul API endpoint (herkese açık, resmi)
BIST_API_URL = "https://www.isyatirim.com.tr/api/GetStocksInBist"

# Alternatif: Finturk / Collect API
BIST_COLLECT_URL = "https://fintables.com/api/stocks"

def fetch_from_tradingview() -> list:
    """TradingView'dan güncel BIST hisselerini çek (en güvenilir kaynak)."""
    headers = {
        'User-Agent': 'Mozilla/5.0',
    }
    try:
        url = 'https://scanner.tradingview.com/turkey/scan'
        payload = {
            'columns': ['name'],
            'filter': [{'left': 'type', 'operation': 'in_range', 'right': ['stock']}],
            'range': [0, 1000],
            'sort': {'sortBy': 'name', 'sortOrder': 'asc'}
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('data', [])
            tickers = [item['d'][0] for item in items]
            return [t.strip() for t in tickers if t.strip()]
    except Exception as e:
        print(f"  TradingView hatasi: {e}")
    return []

def try_all_sources() -> list:
    """Tüm kaynakları dene, birleştir ve tekrarları temizle."""
    all_tickers = set()

    print("\n1️⃣ TradingView API deneniyor...")
    t1 = fetch_from_tradingview()
    print(f"   → {len(t1)} hisse bulundu")
    all_tickers.update(t1)

    if not all_tickers:
        print("2️⃣ İş Yatırım API deneniyor...")
        t2 = fetch_from_isyatirim()
        print(f"   → {len(t2)} hisse bulundu")
        all_tickers.update(t2)


def validate_tickers_yfinance(tickers: list, suffix: str = '.IS') -> dict:
    """
    Her hissenin yfinance'ta gerçekten veri var mı kontrol et.
    Toplu indirme ile çok daha hızlı.
    """
    import yfinance as yf

    valid = []
    invalid = []
    total = len(tickers)

    print(f"\n  {total} hisse doğrulanıyor...")
    print("  (Bu işlem birkaç dakika sürebilir)\n")

    # 20'li gruplar halinde test et
    batch_size = 20
    for i in range(0, total, batch_size):
        batch = tickers[i:i+batch_size]
        batch_with_suffix = [f"{t}{suffix}" if not t.endswith(suffix) else t for t in batch]

        sys.stdout.write(f"\r  [{min(i+batch_size, total)}/{total}] Dogrulanıyor...  ")
        sys.stdout.flush()

        try:
            data = yf.download(
                batch_with_suffix,
                period="5d",
                auto_adjust=True,
                progress=False,
                threads=True,
                timeout=30,
            )
            # Hangi hisseler için veri geldi?
            if hasattr(data.columns, 'levels'):
                # Multi-level columns (birden fazla hisse)
                found_tickers = set()
                for col in data.columns:
                    tk = col[1] if isinstance(col, tuple) else col
                    if data[col].dropna().shape[0] > 0:
                        found_tickers.add(tk)
                for t in batch_with_suffix:
                    if t in found_tickers:
                        valid.append(t)
                    else:
                        invalid.append(t)
            else:
                # Tek hisse
                if not data.empty and data.dropna().shape[0] > 0:
                    valid.extend(batch_with_suffix)
                else:
                    invalid.extend(batch_with_suffix)
        except Exception:
            invalid.extend(batch_with_suffix)

        time.sleep(0.5)  # Rate limiting

    print(f"\n  ✅ Geçerli: {len(valid)} | ❌ Geçersiz/Delisted: {len(invalid)}")
    return {'valid': sorted(valid), 'invalid': sorted(invalid)}


def try_all_sources() -> list:
    """Tüm kaynakları dene, birleştir ve tekrarları temizle."""
    all_tickers = set()

    print("\n1️⃣ TradingView API deneniyor...")
    t1 = fetch_from_tradingview()
    print(f"   → {len(t1)} hisse bulundu")
    all_tickers.update(t1)

    if not all_tickers:
        print("  ⚠️ Kaynaklardan hisse bulunamadı.")

    # Temizle: rakam ve 4-5 harfli kodlar
    cleaned = set()
    for t in all_tickers:
        t = str(t).strip().upper()
        if 2 <= len(t) <= 8 and t.replace('.IS', '').isalpha():
            cleaned.add(t.replace('.IS', ''))

    return sorted(cleaned)


def update_universe_file(all_valid: list):
    """universe.py dosyasını güncel BIST_ALL listesi ile yeniden yazar."""
    import re
    
    path = os.path.join(os.path.dirname(__file__), 'universe.py')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # BIST_ALL array ini bul ve degistir
    # Python kodu formatlamak icin: her satirda 8 hisse
    formatted_list = "[\n"
    for i in range(0, len(all_valid), 8):
        row = [f'"{t}"' for t in all_valid[i:i+8]]
        formatted_list += "    " + ", ".join(row) + ",\n"
    formatted_list += "]"

    # Regex ile BIST_ALL = [ ... ] blogunu degistir
    new_content = re.sub(
        r'BIST_ALL\s*=\s*\[.*?\]',
        f'BIST_ALL = {formatted_list}',
        content,
        flags=re.DOTALL
    )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"\n✅ universe.py güncellendi: {len(all_valid)} hisse yazıldı.")


def main():
    print("=" * 60)
    print("  🔄 BIST HİSSE LİSTESİ GÜNCELLEYİCİ")
    print("=" * 60)

    # Mevcut listelerden başla
    from universe import BIST_30, BIST_100, BIST_ALL

    print(f"\n  Mevcut durum:")
    print(f"    BIST 30  : {len(BIST_30)} hisse")
    print(f"    BIST 100 : {len(BIST_100)} hisse")
    print(f"    BIST ALL : {len(BIST_ALL)} hisse")

    # Yeni kaynaklardan çek
    print("\n📡 Güncel BIST listesi çekiliyor...")
    new_tickers = try_all_sources()

    if new_tickers:
        print(f"\n  Toplam benzersiz kod: {len(new_tickers)}")
        # Mevcut listede olmayanları bul
        existing = set(t.replace('.IS','') for t in BIST_ALL)
        truly_new = [t for t in new_tickers if t not in existing]
        print(f"  Listede olmayan yeni hisse: {len(truly_new)}")
        if truly_new[:10]:
            print(f"  Örnekler: {truly_new[:10]}")
    else:
        print("\n  ⚠️ Online kaynaklardan veri alınamadı.")
        print("  Mevcut liste kullanılıyor. Alternatif: yfinance toplu doğrulama.")

    # yfinance doğrulaması yap (mevcut + yeni)
    print("\n🔍 yfinance'ta hangi hisseler çalışıyor kontrol ediliyor...")
    all_candidates = list(set(
        [t.replace('.IS','') for t in BIST_ALL] + new_tickers
    ))

    results = validate_tickers_yfinance(all_candidates)
    valid_tickers = results['valid']  # .IS suffixli

    # Dosyayi guncelle
    update_universe_file(valid_tickers)

    print(f"\n🎯 ÖZET:")
    print(f"   Önceki liste: {len(BIST_ALL)} hisse")
    print(f"   Güncel liste: {len(valid_tickers)} hisse")
    print(f"   Fark: {len(valid_tickers) - len(BIST_ALL):+} hisse")

    return valid_tickers


if __name__ == "__main__":
    main()
