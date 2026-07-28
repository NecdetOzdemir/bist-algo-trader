import yfinance as yf
import pandas as pd
end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
start_date = (pd.Timestamp.now() - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
print(f"Start: {start_date}, End: {end_date}")
df = yf.download("TOASO.IS", start=start_date, end=end_date, progress=False)
print("WITH END DATE:")
print(df[['Open', 'High', 'Low', 'Close']].tail())

df2 = yf.download("TOASO.IS", period="5d", progress=False)
print("\nWITH PERIOD=5d:")
print(df2[['Open', 'High', 'Low', 'Close']].tail())
