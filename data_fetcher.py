"""
Veri çekme modülü — yfinance ile BIST hisse verilerini çeker.
Akıllı cache sistemi ile gereksiz istek yapar olmaz.
"""

import yfinance as yf
import pandas as pd
import json
import os
import time
from datetime import datetime, timedelta

# Cache dizini
CACHE_DIR = os.path.join(os.path.dirname(__file__), '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# Bellek içi cache (uygulama açıkken tekrar istek atmaz)
_memory_cache: dict = {}

# Cache süresi (dakika) - günlük veri gün içinde değişmez
CACHE_MINUTES_DAILY = 60       # Günlük veri: 60 dk
CACHE_MINUTES_INTRADAY = 20    # 5dk veri: 20 dk


def _cache_path(ticker: str, suffix: str) -> str:
    safe = ticker.replace('.', '_')
    return os.path.join(CACHE_DIR, f"{safe}_{suffix}.json")


def _is_cache_valid(path: str, minutes: int) -> bool:
    if not os.path.exists(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < (minutes * 60)


def _save_cache(path: str, data: dict):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except Exception:
        pass


def _load_cache(path: str) -> dict | None:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def get_daily_data(ticker: str, period: str = "6mo") -> pd.DataFrame | None:
    """
    Günlük OHLCV verisi çeker. Cache'de varsa diskten okur.
    Pivot hesaplamaları, EMA, RSI için kullanılır.
    """
    cache_key = f"{ticker}_daily_{period}"

    # Bellek cache kontrolü
    if cache_key in _memory_cache:
        ts, df = _memory_cache[cache_key]
        if time.time() - ts < CACHE_MINUTES_DAILY * 60:
            return df

    # Disk cache kontrolü
    cache_file = _cache_path(ticker, f"daily_{period}")
    if _is_cache_valid(cache_file, CACHE_MINUTES_DAILY):
        cached = _load_cache(cache_file)
        if cached:
            try:
                df = pd.DataFrame(cached['data'])
                df.index = pd.to_datetime(df.index)
                _memory_cache[cache_key] = (time.time(), df)
                return df
            except Exception:
                pass

    # Yeni veri çek
    try:
        df = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False
        )

        if df is None or df.empty:
            return None

        # MultiIndex'i düzelt
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Gerekli sütunlar var mı kontrol et
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required:
            if col not in df.columns:
                return None

        # Eksik verileri temizle
        df = df.dropna(subset=['Close', 'High', 'Low', 'Volume'])
        df = df[df['Volume'] > 0]

        if len(df) < 10:
            return None

        # Cache'e kaydet
        _save_cache(cache_file, {
            'ticker': ticker,
            'fetched_at': datetime.now().isoformat(),
            'data': df.to_dict()
        })
        _memory_cache[cache_key] = (time.time(), df)

        return df

    except Exception as e:
        print(f"[DataFetcher] {ticker} verisi çekilemedi: {e}")
        return None


def get_current_price(ticker: str) -> float | None:
    """
    En güncel fiyatı döndürür (gecikmeli).
    Önce günlük verinin son kapanışını kullanır.
    """
    df = get_daily_data(ticker, period="5d")
    if df is None or df.empty:
        return None
    return float(df['Close'].iloc[-1])


def get_stock_info(ticker: str) -> dict:
    """
    Hisse bilgilerini (şirket adı, piyasa değeri vb.) döndürür.
    Cache'li çalışır.
    """
    cache_key = f"{ticker}_info"

    # Bellek cache kontrolü (24 saat geçerli)
    if cache_key in _memory_cache:
        ts, info = _memory_cache[cache_key]
        if time.time() - ts < 24 * 3600:
            return info

    cache_file = _cache_path(ticker, "info")
    if _is_cache_valid(cache_file, 24 * 60):
        cached = _load_cache(cache_file)
        if cached:
            _memory_cache[cache_key] = (time.time(), cached)
            return cached

    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        result = {
            'ticker': ticker,
            'name': info.get('longName', ticker.replace('.IS', '')),
            'market_cap': info.get('marketCap', 0),
            'currency': info.get('currency', 'TRY'),
            'exchange': info.get('exchange', 'IST'),
        }

        _save_cache(cache_file, result)
        _memory_cache[cache_key] = (time.time(), result)
        return result

    except Exception:
        return {
            'ticker': ticker,
            'name': ticker.replace('.IS', ''),
            'market_cap': 0,
            'currency': 'TRY',
            'exchange': 'IST',
        }


def clear_cache(ticker: str = None):
    """Cache'i temizler. ticker=None ise tüm cache'i temizler."""
    global _memory_cache

    if ticker is None:
        _memory_cache.clear()
        for f in os.listdir(CACHE_DIR):
            try:
                os.remove(os.path.join(CACHE_DIR, f))
            except Exception:
                pass
    else:
        keys_to_delete = [k for k in _memory_cache if k.startswith(ticker)]
        for k in keys_to_delete:
            del _memory_cache[k]


def get_batch_data(tickers: list, period: str = "6mo") -> dict:
    """
    Birden fazla hisse için veri çeker.
    Returns: {ticker: DataFrame}
    """
    results = {}
    for ticker in tickers:
        df = get_daily_data(ticker, period=period)
        if df is not None:
            results[ticker] = df
    return results
