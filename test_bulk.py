import time
import yfinance as yf
from universe import BIST_30

start = time.time()
print("Fetching daily...")
daily = yf.download(BIST_30, period="200d", group_by="ticker", threads=True, progress=False)
print(f"Daily done in {time.time()-start:.2f}s")

start = time.time()
print("Fetching hourly...")
hourly = yf.download(BIST_30, period="15d", interval="1h", group_by="ticker", threads=True, progress=False)
print(f"Hourly done in {time.time()-start:.2f}s")
