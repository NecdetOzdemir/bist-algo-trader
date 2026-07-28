import time
import requests
import concurrent.futures
from universe import BIST_30

def fetch(tic):
    # simulating by hitting local API for each ticker if we had it, or just yfinance
    pass

import yfinance as yf
def download_single(tic):
    df = yf.download(tic, period="200d", progress=False)
    return len(df)

start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    results = list(executor.map(download_single, BIST_30))
print(f"ThreadPool done in {time.time()-start:.2f}s")
