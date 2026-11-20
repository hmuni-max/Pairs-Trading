# Pairs Trading

Choose two Yahoo Finance stock tickers to test a long/short pairs strategy. The program checks whether their prices have historically moved together in a way that makes the gap between them tend to close. It then evaluates the strategy on later dates and compares it with buying and holding the first stock.

## What a run produces

- **A terminal report** with the dates used for fitting and evaluation, the Engle–Granger test result and p-value, the hedge ratio, long and short trade counts, and time in the market. A table compares total return, annualized return and volatility, Sharpe ratio, and maximum drawdown.
- **A PNG dashboard** with two panels. The top shows how far the price spread is from its rolling mean, the entry and exit levels, and shading while a trade is open. The bottom shows the growth of one unit of capital for the strategy and the benchmark. If a pair fails the screen, the dashboard gives the reason and the strategy line stays flat.

### Example · Coca-Cola and PepsiCo

Using prices from January 2020 through December 2024, the first 252 shared closes gave `KO` and `PEP` a cointegration p-value of **0.4125**, above the 0.05 cutoff. The backtest therefore recorded **zero trades**. The dashed lines in the top panel show where trades could have opened had the pair passed the screen. Yahoo may revise adjusted prices, so reruns can differ slightly.

![KO and PEP dashboard showing the spread crossing its entry thresholds while the screened-out strategy stays in cash](pairs_trading_dashboard.png)

## Install and run

Clone or download the repository, then open a terminal in its folder. These commands use Python 3.12. The program needs internet access to retrieve prices from Yahoo Finance.

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
& ".\Run Pairs Trading.cmd" XOM CVX
```

After setup, you can also double-click **Run Pairs Trading.cmd** to enter the two tickers at the prompts. Press Enter twice for `KO` and `PEP`.

**macOS or Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python pairs_trading.py XOM CVX
```

Companies can be from different industries or exchanges. Use Yahoo Finance's listing symbols, such as `BRK-B`, `ULVR.L`, or `7203.T`. Ticker order matters. The first stock is the benchmark, and its currency is used to value both stocks.

### Reproduce the dashboard above

From an environment with the requirements installed, run the following command. On Windows, the launcher accepts the same tickers and options.

```bash
python pairs_trading.py KO PEP --start 2020-01-01 --end 2025-01-01 --output pairs_trading_dashboard.png --no-show
```

| Option | Default and behavior |
| --- | --- |
| `--start`, `--end` | The five years ending today. The start date is included and the end date is excluded. |
| `--formation-days N` | Use the first 252 common closes to fit the pair. The minimum is 60, with at least three further closes for evaluation. |
| `--output FILE.png` | Save `pairs_<FIRST>_<SECOND>.png` in the working directory. A new run with the same filename replaces the previous chart. |
| `--no-show` | Save the chart without opening it. By default the program also displays it. |

## How the backtest works

1. **Align prices.** Use split- and dividend-adjusted daily closes. Convert the second stock to the first stock's currency using historical FX rates when necessary, and keep dates with all required prices.
2. **Screen the pair.** On the formation period, apply the Engle–Granger cointegration test and fit the first stock's price on the second with an intercept. A p-value below 0.05 and a positive hedge ratio qualify the pair for the long/short strategy.
3. **Simulate later trades.** Hold the fitted hedge ratio fixed. Calculate the spread as the first price minus the hedge ratio times the second price. Buy the spread below a trailing 60-day z-score of −1.5, sell it short above +1.5, and exit when it crosses zero. Each position earns returns from the next close-to-close interval. Close any open position at the final evaluation close.

Results assume execution at the signal close, zero interest on cash, and no transaction costs, slippage or short-borrow fees. Markets in different time zones may close hours apart on a shared date. A pair can pass by chance, especially when testing many combinations, and a historical relationship can change.
