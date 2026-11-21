# Stock ticker reference

The backtest takes two Yahoo Finance ticker symbols. Use the tables below to find the symbols for the companies you want to test.

## Enter your two tickers

- **Windows prompts** — Double-click `Run Pairs Trading.cmd`, enter one symbol at each prompt, and press Enter after each. Press Enter twice to use the defaults, `KO` and `PEP`.
- **Windows PowerShell** — After [setup](README.md#install-and-run), run `& ".\Run Pairs Trading.cmd" KO PEP` from the repository folder.
- **macOS or Linux** — After [setup](README.md#install-and-run), run `.venv/bin/python pairs_trading.py KO PEP` from the repository folder.

Choose two different companies and keep the order you want. The first ticker is the buy-and-hold benchmark and its currency is used to value both stocks.

## Example pairs

These are examples for running the backtest. The algorithm tests each pair for cointegration and may produce zero trades.

| Companies | First ticker | Second ticker |
| --- | --- | --- |
| Coca-Cola and PepsiCo | `KO` | `PEP` |
| ExxonMobil and Chevron | `XOM` | `CVX` |
| Nvidia and AMD | `NVDA` | `AMD` |
| JPMorgan Chase and Bank of America | `JPM` | `BAC` |
| Visa and Mastercard | `V` | `MA` |
| Ford and General Motors | `F` | `GM` |
| UPS and FedEx | `UPS` | `FDX` |
| Shell and BP (London) | `SHEL.L` | `BP.L` |
| Tesco and Sainsbury’s (London) | `TSCO.L` | `SBRY.L` |
| Toyota and Honda (Tokyo) | `7203.T` | `7267.T` |

## Look up a company

For a company outside this list, search its name in [Yahoo Finance Symbol Lookup](https://uk.finance.yahoo.com/lookup/). Check the exchange and share class, then copy the full symbol. Keep exchange suffixes such as `.L` for London and `.T` for Tokyo, and punctuation such as the hyphen in `BRK-B`. `GOOGL` and `GOOG` are two share classes of the same company, Alphabet. See [Yahoo Finance’s exchange suffix list](https://uk.help.yahoo.com/kb/exchanges-markets-covered-yahoo-finance-sln2310.html) for other markets.

### US listings

| Company | Yahoo Finance ticker | Industry |
| --- | --- | --- |
| Alphabet (Google), Class A | [`GOOGL`](https://uk.finance.yahoo.com/quote/GOOGL/) | Internet services |
| Alphabet (Google), Class C | [`GOOG`](https://uk.finance.yahoo.com/quote/GOOG/) | Internet services |
| AMD (Advanced Micro Devices) | [`AMD`](https://uk.finance.yahoo.com/quote/AMD/) | Semiconductors |
| Apple | [`AAPL`](https://uk.finance.yahoo.com/quote/AAPL/) | Consumer technology |
| Bank of America | [`BAC`](https://uk.finance.yahoo.com/quote/BAC/) | Banking |
| Berkshire Hathaway, Class B | [`BRK-B`](https://uk.finance.yahoo.com/quote/BRK-B/) | Diversified holding company |
| Chevron | [`CVX`](https://uk.finance.yahoo.com/quote/CVX/) | Oil and gas |
| Coca-Cola | [`KO`](https://uk.finance.yahoo.com/quote/KO/) | Beverages |
| ExxonMobil | [`XOM`](https://uk.finance.yahoo.com/quote/XOM/) | Oil and gas |
| FedEx | [`FDX`](https://uk.finance.yahoo.com/quote/FDX/) | Parcel delivery |
| Ford Motor | [`F`](https://uk.finance.yahoo.com/quote/F/) | Automakers |
| General Motors | [`GM`](https://uk.finance.yahoo.com/quote/GM/) | Automakers |
| JPMorgan Chase | [`JPM`](https://uk.finance.yahoo.com/quote/JPM/) | Banking |
| Mastercard | [`MA`](https://uk.finance.yahoo.com/quote/MA/) | Payments |
| Microsoft | [`MSFT`](https://uk.finance.yahoo.com/quote/MSFT/) | Software and cloud |
| Nvidia | [`NVDA`](https://uk.finance.yahoo.com/quote/NVDA/) | Semiconductors |
| PepsiCo | [`PEP`](https://uk.finance.yahoo.com/quote/PEP/) | Food and beverages |
| UPS (United Parcel Service) | [`UPS`](https://uk.finance.yahoo.com/quote/UPS/) | Parcel delivery |
| Visa | [`V`](https://uk.finance.yahoo.com/quote/V/) | Payments |

### London Stock Exchange

| Company | Yahoo Finance ticker | Industry |
| --- | --- | --- |
| AstraZeneca | [`AZN.L`](https://uk.finance.yahoo.com/quote/AZN.L/) | Pharmaceuticals |
| Barclays | [`BARC.L`](https://uk.finance.yahoo.com/quote/BARC.L/) | Banking |
| BP | [`BP.L`](https://uk.finance.yahoo.com/quote/BP.L/) | Oil and gas |
| BT Group | [`BT-A.L`](https://uk.finance.yahoo.com/quote/BT-A.L/) | Telecoms |
| GSK | [`GSK.L`](https://uk.finance.yahoo.com/quote/GSK.L/) | Pharmaceuticals |
| HSBC Holdings | [`HSBA.L`](https://uk.finance.yahoo.com/quote/HSBA.L/) | Banking |
| J Sainsbury (Sainsbury’s) | [`SBRY.L`](https://uk.finance.yahoo.com/quote/SBRY.L/) | Supermarkets |
| Shell | [`SHEL.L`](https://uk.finance.yahoo.com/quote/SHEL.L/) | Oil and gas |
| Tesco | [`TSCO.L`](https://uk.finance.yahoo.com/quote/TSCO.L/) | Supermarkets |
| Unilever | [`ULVR.L`](https://uk.finance.yahoo.com/quote/ULVR.L/) | Consumer goods |
| Vodafone | [`VOD.L`](https://uk.finance.yahoo.com/quote/VOD.L/) | Telecoms |

### Tokyo Stock Exchange

| Company | Yahoo Finance ticker | Industry |
| --- | --- | --- |
| Honda Motor | [`7267.T`](https://uk.finance.yahoo.com/quote/7267.T/) | Automakers |
| Toyota Motor | [`7203.T`](https://uk.finance.yahoo.com/quote/7203.T/) | Automakers |
