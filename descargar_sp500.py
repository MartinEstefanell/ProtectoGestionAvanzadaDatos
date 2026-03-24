import yfinance as yf

df = yf.download("^GSPC", start="2022-01-01", end="2022-12-31")

df.to_csv("sp500_2022.csv")