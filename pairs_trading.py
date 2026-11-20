"""Screen two stock tickers for cointegration and backtest a long/short strategy.

Compare the strategy with buy-and-hold on later dates. Print a performance
report and save a PNG of the spread z-score and both equity curves.
"""

import argparse
from datetime import date
import os
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
import yfinance as yf
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_PAIR = ("KO", "PEP")
FORMATION_DAYS = 252       # aligned closes used only for calibration
WINDOW = 60                # rolling window (trading days) for z-score mean/std
ENTRY_Z = 1.5              # open a trade when |z| exceeds this
EXIT_Z = 0.0               # close the trade when z crosses back over this level
ALPHA = 0.05               # significance level for the cointegration test
TRADING_DAYS = 252         # annualisation factor

# Chart colours
SURFACE, GRID, BASELINE = "#fcfcfb", "#e1e0d9", "#c3c2b7"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
BLUE, ORANGE, RED = "#2a78d6", "#eb6834", "#e34948"


# ---------------------------------------------------------------------------
# 1. Data ingestion
# ---------------------------------------------------------------------------
def download_close(symbol, start, end):
    """Read adjusted daily closes and the exchange's quote currency."""
    asset = yf.Ticker(symbol)
    try:
        history = asset.history(start=start, end=end, interval="1d", auto_adjust=True,
                                actions=False, timeout=20)
        if history.empty or "Close" not in history:
            raise ValueError("no daily closing prices were returned")
        currency = asset.history_metadata.get("currency")
    except Exception as exc:
        raise ValueError(f"Could not load {symbol} from Yahoo Finance ({exc}). "
                         "Check the exchange ticker, dates and connection.") from exc
    if not currency:
        raise ValueError(f"Yahoo Finance supplied no quote currency for {symbol}.")
    close = history["Close"].rename(symbol)
    close.index = close.index.tz_localize(None).normalize()
    close = close[~close.index.duplicated(keep="last")].sort_index()
    close = close.where(np.isfinite(close) & (close > 0)).dropna()
    if close.empty:
        raise ValueError(f"{symbol} has no usable adjusted closes in the selected period.")
    # Some exchanges quote shares in hundredths of a currency unit.
    minor_units = {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ZAC": "ZAR",
                   "ILA": "ILS", "ILa": "ILS", "USc": "USD"}
    if currency in minor_units:
        return close / 100, minor_units[currency]
    return close, currency


def load_prices(ticker_a, ticker_b, start, end):
    """Align both legs and, if needed, value the hedge leg in A's currency."""
    first, currency_a = download_close(ticker_a, start, end)
    second, currency_b = download_close(ticker_b, start, end)
    if currency_a != currency_b:
        fx_symbol = f"{currency_b}{currency_a}=X"
        fx, fx_currency = download_close(fx_symbol, start, end)
        if fx_currency != currency_a:
            raise ValueError(f"Unexpected quote currency {fx_currency} for {fx_symbol}.")
        second = (second * fx).rename(ticker_b)
        print(f"Converted {ticker_b} from {currency_b} to {currency_a} using {fx_symbol}.")
    print(f"Both price series are measured in {currency_a}.")
    return pd.concat([first, second], axis=1, join="inner").dropna().sort_index()


# ---------------------------------------------------------------------------
# 2. Cointegration check
# ---------------------------------------------------------------------------
def cointegration_test(a, b, alpha):
    """Engle-Granger two-step test. H0: the pair is NOT cointegrated."""
    if a.nunique() < 2 or b.nunique() < 2:
        raise ValueError("A stock has a constant formation price. Try a longer period or another ticker.")
    t_stat, p_value, crit = coint(a, b, return_results=False)
    if not np.isfinite([t_stat, p_value]).all():
        raise ValueError("The test is undefined for these prices. Check for identical or "
                         "nearly proportional listings and try another pair.")
    print(f"Engle-Granger t-stat : {t_stat:.4f}")
    print(f"Critical values      : 1%={crit[0]:.3f}  5%={crit[1]:.3f}  10%={crit[2]:.3f}")
    print(f"p-value              : {p_value:.4f}")
    if p_value < alpha:
        print(f"The formation data support cointegration at the {alpha:.0%} level.")
    else:
        print(f"The formation data provide insufficient evidence of cointegration at {alpha:.0%}.")
    return p_value


# ---------------------------------------------------------------------------
# 3. Hedge ratio, spread and z-score
# ---------------------------------------------------------------------------
def hedge_ratio(a, b):
    """OLS of A on B (with intercept); the slope is the number of B shares hedging one A share."""
    model = sm.OLS(a, sm.add_constant(b)).fit()
    return model.params[b.name], model.rsquared


def rolling_zscore(spread, window):
    """Normalise the spread by its trailing mean and standard deviation (uses past data only)."""
    mean = spread.rolling(window).mean()
    std = spread.rolling(window).std()
    return (spread - mean) / std.where(std > 0)


# ---------------------------------------------------------------------------
# 4. Signal generation
# ---------------------------------------------------------------------------
def generate_positions(z, entry, exit_level):
    """State machine: +1 = long spread, -1 = short spread, 0 = flat.

    The position for day t is decided from the z-score at the close of day t.
    """
    positions = np.zeros(len(z))
    current = 0
    for i, zi in enumerate(z.to_numpy()):
        if np.isnan(zi):
            current = 0  # warm-up period: no z-score yet
        else:
            # Exit once z has reverted back across the mean
            if (current == 1 and zi >= exit_level) or (current == -1 and zi <= exit_level):
                current = 0
            # Entry rules (also allows a same-day flip if z gaps straight to the opposite band)
            if current == 0:
                if zi < -entry:
                    current = 1   # spread is cheap: buy A, sell B
                elif zi > entry:
                    current = -1  # spread is rich: sell A, buy B
        positions[i] = current
    return pd.Series(positions, index=z.index, name="position")


def trade_spans(positions, side):
    """(entry_date, exit_date) for every trade on one side (+1 long, -1 short)."""
    is_side = (positions == side).to_numpy().astype(int)
    edges = np.diff(np.concatenate([[0], is_side, [0]]))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)  # first day after the run, i.e. the exit close
    idx = positions.index
    return [(idx[s], idx[min(e, len(idx) - 1)]) for s, e in zip(starts, ends)]


# ---------------------------------------------------------------------------
# 5. Backtest and performance metrics
# ---------------------------------------------------------------------------
def backtest(prices, positions, beta, col_a, col_b):
    """Daily returns of holding +1 share of A and -beta shares of B per unit of spread position."""
    returns = prices.pct_change()
    # Capital weight of each leg, normalised by gross exposure |A| + |beta * B|
    gross = prices[col_a] + abs(beta) * prices[col_b]
    w_a = prices[col_a] / gross
    w_b = -beta * prices[col_b] / gross
    # Weights fixed at yesterday's close earn today's asset returns
    spread_return = w_a.shift(1) * returns[col_a] + w_b.shift(1) * returns[col_b]
    # Look-ahead guard: a signal formed at the close of t-1 only earns the return from t-1 to t
    return positions.shift(1) * spread_return


def performance(returns):
    """Total return, CAGR, annualised volatility, Sharpe (rf = 0) and max drawdown."""
    equity = (1 + returns).cumprod()
    # The first observation is the opening equity of 1, before any holding interval.
    earned = returns.iloc[1:]
    daily_std = earned.std()
    return {
        "Total Return": equity.iloc[-1] - 1,
        "Annualized Return": equity.iloc[-1] ** (TRADING_DAYS / len(earned)) - 1,
        "Annualized Volatility": daily_std * np.sqrt(TRADING_DAYS),
        "Annualized Sharpe": earned.mean() / daily_std * np.sqrt(TRADING_DAYS) if daily_std > 0 else np.nan,
        "Max Drawdown": (equity / equity.cummax() - 1).min(),
    }


def print_report(strat_perf, bench_perf, bench_label):
    formats = {"Total Return": "{:.2%}", "Annualized Return": "{:.2%}",
               "Annualized Volatility": "{:.2%}", "Annualized Sharpe": "{:.2f}",
               "Max Drawdown": "{:.2%}"}
    print(f"\n{'Metric':<24}{'Strategy':>12}{bench_label:>20}")
    print("-" * 56)
    for key, fmt in formats.items():
        strategy = fmt.format(strat_perf[key]) if np.isfinite(strat_perf[key]) else "n/a"
        benchmark = fmt.format(bench_perf[key]) if np.isfinite(bench_perf[key]) else "n/a"
        print(f"{key:<24}{strategy:>12}{benchmark:>20}")


# ---------------------------------------------------------------------------
# 6. Visualisation
# ---------------------------------------------------------------------------
def plot_dashboard(zscore, positions, strat_eq, bench_eq, strat_perf, bench_perf, beta, p_value,
                   ticker_a, ticker_b, screen_result, output, show):
    if sys.platform == "win32" or not show:
        plt.switch_backend("Agg")
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "axes.edgecolor": BASELINE, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 10, "legend.frameon": False,
    })
    fig, (ax_z, ax_eq) = plt.subplots(2, 1, figsize=(14, 9), sharex=True, layout="constrained")

    # Panel 1: z-score with entry/exit levels; shaded bands show when a trade was open
    for side, color, label in [(1, BLUE, "Long spread open"), (-1, RED, "Short spread open")]:
        for k, (t0, t1) in enumerate(trade_spans(positions, side)):
            ax_z.axvspan(t0, t1, color=color, alpha=0.10, lw=0, label=label if k == 0 else None)
    ax_z.plot(zscore.index, zscore, color=INK_2, lw=1.0, label="Spread z-score")
    ax_z.axhline(ENTRY_Z, color=RED, ls="--", lw=1.4, label=f"Short entry (z > +{ENTRY_Z:g})")
    ax_z.axhline(-ENTRY_Z, color=BLUE, ls="--", lw=1.4, label=f"Long entry (z < \u2212{ENTRY_Z:g})")
    ax_z.axhline(EXIT_Z, color=INK, lw=1.0, label=f"Exit (z crosses {EXIT_Z:g})")
    ax_z.set_ylabel("Z-score (\u03c3 from rolling mean)")
    ax_z.set_title(f"Rolling {WINDOW}-day z-score of spread = {ticker_a} \u2212 ({beta:.3f} \u00d7 {ticker_b})",
                   loc="left", fontsize=11)
    ax_z.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))

    # Panel 2: growth of $1 for the strategy vs buy-and-hold of asset A
    ax_eq.axhline(1.0, color=BASELINE, lw=1.0)
    for eq, perf, color, label in [(strat_eq, strat_perf, BLUE, "Pairs strategy"),
                                   (bench_eq, bench_perf, ORANGE, f"Buy & hold {ticker_a}")]:
        sharpe = perf['Annualized Sharpe']
        sharpe_text = f"{sharpe:.2f}" if np.isfinite(sharpe) else "n/a"
        ax_eq.plot(eq.index, eq, color=color, lw=1.8,
                   label=f"{label}  (Sharpe {sharpe_text})")
        # Direct label: final total return at the end of each line
        ax_eq.annotate(f"{perf['Total Return']:+.1%}", xy=(eq.index[-1], eq.iloc[-1]),
                       xytext=(6, 0), textcoords="offset points", va="center", color=INK_2)
    ax_eq.set_ylabel("Growth of 1 unit of capital")
    ax_eq.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.2f}"))
    ax_eq.set_title("Cumulative equity curve", loc="left", fontsize=11)
    ax_eq.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))

    locator = mdates.AutoDateLocator()
    ax_eq.xaxis.set_major_locator(locator)
    ax_eq.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    fig.suptitle(f"{ticker_a} / {ticker_b}    |    {screen_result}\n"
                 f"Formation p = {p_value:.4f}    Hedge ratio = {beta:.3f}",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.savefig(output, format="png", dpi=150)
    print(f"Dashboard saved to {output.resolve()}")
    if show:
        if sys.platform == "win32":
            os.startfile(output.resolve())
        else:
            plt.show()
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_pair(prices, formation_days, output, show):
    ticker_a, ticker_b = prices.columns
    if len(prices) < formation_days + 3:
        raise ValueError(f"Only {len(prices)} common price dates for {ticker_a}/{ticker_b}. "
                         f"Need {formation_days} for formation and at least 3 for evaluation. "
                         "Extend the dates or reduce --formation-days.")
    a, b = prices[ticker_a], prices[ticker_b]
    training = prices.iloc[:formation_days]
    print(f"\n{ticker_a} / {ticker_b} | {len(prices)} common daily closes")
    print(f"Formation: {training.index[0]:%Y-%m-%d} to {training.index[-1]:%Y-%m-%d} "
          f"({formation_days} closes)")
    p_value = cointegration_test(training[ticker_a], training[ticker_b], ALPHA)
    beta, r_squared = hedge_ratio(training[ticker_a], training[ticker_b])
    spread = a - beta * b
    zscore = rolling_zscore(spread, WINDOW).iloc[formation_days:]
    print(f"\nOLS hedge ratio: {beta:.4f}  (R-squared = {r_squared:.3f})")
    print(f"Spread = {ticker_a} - ({beta:.4f} x {ticker_b})")
    positions = pd.Series(0.0, index=zscore.index, name="position")
    if p_value >= ALPHA:
        screen_result = "No trades: weak evidence of mean reversion"
    elif beta <= 0:
        screen_result = "No trades: hedge does not produce opposing legs"
    else:
        screen_result = "Passed formation screen"
        positions = generate_positions(zscore, ENTRY_Z, EXIT_Z)
    print(screen_result)
    positions.iloc[-1] = 0  # Close the book at the final evaluation close.
    evaluation = prices.loc[zscore.index]
    strat_ret = backtest(evaluation, positions, beta, ticker_a, ticker_b).fillna(0.0)
    bench_ret = evaluation[ticker_a].pct_change().fillna(0.0)
    strat_eq = (1 + strat_ret).cumprod()
    bench_eq = (1 + bench_ret).cumprod()

    n_long, n_short = len(trade_spans(positions, 1)), len(trade_spans(positions, -1))
    print(f"\nEvaluation: {zscore.index[0]:%Y-%m-%d} to {zscore.index[-1]:%Y-%m-%d}")
    print(f"Trades: {n_long + n_short} ({n_long} long spread, {n_short} short spread). "
          f"Time in market: {positions.iloc[:-1].ne(0).mean():.1%}")

    strat_perf, bench_perf = performance(strat_ret), performance(bench_ret)
    print_report(strat_perf, bench_perf, f"Buy & Hold {ticker_a}")

    # 6. Dashboard
    plot_dashboard(zscore, positions, strat_eq, bench_eq, strat_perf, bench_perf, beta, p_value,
                   ticker_a, ticker_b, screen_result, output, show)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", metavar="TICKER", help="two Yahoo Finance symbols, in order")
    parser.add_argument("--start", type=date.fromisoformat, help="first date (default: five years before --end)")
    parser.add_argument("--end", type=date.fromisoformat, default=date.today(), help="exclusive end date (default: today)")
    parser.add_argument("--formation-days", type=int, default=FORMATION_DAYS, help="common closes for the initial fit (default: 252)")
    parser.add_argument("--output", type=Path, help="dashboard PNG path (default: named for the pair)")
    parser.add_argument("--no-show", action="store_true", help="save the dashboard without opening it")
    args = parser.parse_args(argv)
    symbols = args.tickers
    if not symbols and sys.stdin.isatty():
        print("Enter two Yahoo Finance tickers. Press Enter to use the examples.")
        symbols = [input(f"{label} [{default}]: ").strip() or default
                   for label, default in zip(("First ticker", "Second ticker"), DEFAULT_PAIR)]
    ticker_pair = [symbol.strip().upper() for symbol in symbols or DEFAULT_PAIR]
    if len(ticker_pair) != 2 or ticker_pair[0] == ticker_pair[1]:
        parser.error("Choose two different stock tickers, for example KO PEP.")
    if any(not re.fullmatch(r"[A-Z0-9][A-Z0-9.&_+\-]*", symbol) for symbol in ticker_pair):
        parser.error("Use stock symbols such as BRK-B, VOD.L or 7203.T.")
    start = args.start or (pd.Timestamp(args.end) - pd.DateOffset(years=5)).date()
    if start >= args.end:
        parser.error("--start must be earlier than --end.")
    if args.formation_days < WINDOW:
        parser.error(f"--formation-days must be at least {WINDOW}.")
    output = args.output or Path(f"pairs_{ticker_pair[0]}_{ticker_pair[1]}.png")
    if output.suffix.lower() != ".png":
        parser.error("--output must be a .png file.")
    try:
        prices = load_prices(*ticker_pair, start, args.end)
        run_pair(prices, args.formation_days, output, not args.no_show)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
