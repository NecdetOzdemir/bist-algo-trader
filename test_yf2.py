import yfinance as yf
import pandas as pd
end_date = (pd.Timestamp.now() + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
start_date = (pd.Timestamp.now() - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
df = yf.download("TOASO.IS", start=start_date, end=end_date, progress=False)
print("WITH END DATE + 1:")
print(df[['Open', 'High', 'Low', 'Close']].tail())
