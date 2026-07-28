import yfinance as yf
df = yf.download("TOASO.IS", period="6mo", progress=False)
print("WITH PERIOD:")
print(df[['Open', 'High', 'Low', 'Close']].tail())
