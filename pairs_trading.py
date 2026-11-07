"""
Pairs Trading Strategy & Backtester (KO vs PEP)

Pipeline: download prices -> Engle-Granger cointegration test -> OLS hedge ratio
-> rolling z-score of the spread -> z-score entry/exit rules -> backtest -> dashboard.

Install: pip install yfinance pandas numpy statsmodels matplotlib
"""

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
TICKER_A = "KO"            # Asset A: dependent variable in the hedge regression
TICKER_B = "PEP"           # Asset B: hedge asset
START_DATE = "2020-01-01"  # 5 years of daily data
END_DATE = "2025-01-01"
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
def load_prices(ticker_a, ticker_b, start, end):
    """Download adjusted closes for both tickers and align them on common dates."""
    # auto_adjust=True folds splits and dividends into 'Close', i.e. the adjusted close.
    # threads=False avoids yfinance's "database is locked" cache error on parallel downloads.
    raw = yf.download([ticker_a, ticker_b], start=start, end=end,
                      auto_adjust=True, progress=False, threads=False)
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no data; check the tickers and your connection.")
    prices = raw["Close"][[ticker_a, ticker_b]]
    # Keep only dates where both legs have a price, in chronological order
    prices = prices.dropna().sort_index()
    if len(prices) <= WINDOW:
        raise RuntimeError(f"Only {len(prices)} aligned rows downloaded; need more than {WINDOW}. "
                           "One of the tickers probably failed to download; try again.")
    return prices


# ---------------------------------------------------------------------------
# 2. Cointegration check
# ---------------------------------------------------------------------------
def cointegration_test(a, b, alpha):
    """Engle-Granger two-step test. H0: the pair is NOT cointegrated."""
    t_stat, p_value, crit = coint(a, b)
    print(f"Engle-Granger t-stat : {t_stat:.4f}")
    print(f"Critical values      : 1%={crit[0]:.3f}  5%={crit[1]:.3f}  10%={crit[2]:.3f}")
    print(f"p-value              : {p_value:.4f}")
    if p_value < alpha:
        print(f"Result: {a.name}/{b.name} ARE cointegrated at the {alpha:.0%} level.")
    else:
        print(f"Result: {a.name}/{b.name} are NOT cointegrated at the {alpha:.0%} level; "
              "mean reversion is not statistically supported, so treat the backtest as illustrative.")
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
    return (spread - mean) / std


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
    daily_std = returns.std()
    return {
        "Total Return": equity.iloc[-1] - 1,
        "Annualized Return": equity.iloc[-1] ** (TRADING_DAYS / len(returns)) - 1,
        "Annualized Volatility": daily_std * np.sqrt(TRADING_DAYS),
        "Annualized Sharpe": returns.mean() / daily_std * np.sqrt(TRADING_DAYS) if daily_std > 0 else np.nan,
        "Max Drawdown": (equity / equity.cummax() - 1).min(),
    }


def print_report(strat_perf, bench_perf, bench_label):
    formats = {"Total Return": "{:.2%}", "Annualized Return": "{:.2%}",
               "Annualized Volatility": "{:.2%}", "Annualized Sharpe": "{:.2f}",
               "Max Drawdown": "{:.2%}"}
    print(f"\n{'Metric':<24}{'Strategy':>12}{bench_label:>20}")
    print("-" * 56)
    for key, fmt in formats.items():
        print(f"{key:<24}{fmt.format(strat_perf[key]):>12}{fmt.format(bench_perf[key]):>20}")


# ---------------------------------------------------------------------------
# 6. Visualisation
# ---------------------------------------------------------------------------
def plot_dashboard(zscore, positions, strat_eq, bench_eq, strat_perf, bench_perf, beta, p_value):
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
    ax_z.set_title(f"Rolling {WINDOW}-day z-score of spread = {TICKER_A} \u2212 {beta:.3f} \u00d7 {TICKER_B}",
                   loc="left", fontsize=11)
    ax_z.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))

    # Panel 2: growth of $1 for the strategy vs buy-and-hold of asset A
    ax_eq.axhline(1.0, color=BASELINE, lw=1.0)
    for eq, perf, color, label in [(strat_eq, strat_perf, BLUE, "Pairs strategy"),
                                   (bench_eq, bench_perf, ORANGE, f"Buy & hold {TICKER_A}")]:
        ax_eq.plot(eq.index, eq, color=color, lw=1.8,
                   label=f"{label}  (Sharpe {perf['Annualized Sharpe']:.2f})")
        # Direct label: final total return at the end of each line
        ax_eq.annotate(f"{perf['Total Return']:+.1%}", xy=(eq.index[-1], eq.iloc[-1]),
                       xytext=(6, 0), textcoords="offset points", va="center", color=INK_2)
    ax_eq.set_ylabel("Growth of $1")
    ax_eq.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:.2f}"))
    ax_eq.set_title("Cumulative equity curve", loc="left", fontsize=11)
    ax_eq.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))

    locator = mdates.AutoDateLocator()
    ax_eq.xaxis.set_major_locator(locator)
    ax_eq.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    fig.suptitle(f"Pairs Trading Dashboard: {TICKER_A} / {TICKER_B}    "
                 f"Engle-Granger p = {p_value:.3f}    hedge ratio = {beta:.3f}",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.savefig("pairs_trading_dashboard.png", dpi=150)
    plt.show()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # 1. Data
    prices = load_prices(TICKER_A, TICKER_B, START_DATE, END_DATE)
    a, b = prices[TICKER_A], prices[TICKER_B]
    print(f"Loaded {len(prices)} aligned trading days: "
          f"{prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d}")

    # 2. Cointegration
    print("\n--- Engle-Granger cointegration test ---")
    p_value = cointegration_test(a, b, ALPHA)

    # 3. Hedge ratio, spread, z-score
    # Note: the hedge ratio is fitted on the full sample, as specified. For a strictly
    # out-of-sample test, fit it on a training window or use a rolling regression.
    beta, r_squared = hedge_ratio(a, b)
    spread = a - beta * b
    zscore = rolling_zscore(spread, WINDOW)
    print(f"\nOLS hedge ratio: {beta:.4f}  (R-squared = {r_squared:.3f})")
    print(f"Spread = {TICKER_A} - {beta:.4f} x {TICKER_B}")

    # 4. Signals
    positions = generate_positions(zscore, ENTRY_Z, EXIT_Z)

    # 5. Backtest, evaluated from the first day with a valid z-score
    start = zscore.first_valid_index()
    strat_ret = backtest(prices, positions, beta, TICKER_A, TICKER_B).loc[start:].fillna(0.0)
    bench_ret = a.loc[start:].pct_change().fillna(0.0)
    strat_eq = (1 + strat_ret).cumprod()
    bench_eq = (1 + bench_ret).cumprod()

    positions = positions.loc[start:]
    zscore = zscore.loc[start:]
    n_long, n_short = len(trade_spans(positions, 1)), len(trade_spans(positions, -1))
    print(f"\nBacktest period: {start:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d}")
    print(f"Trades: {n_long + n_short} ({n_long} long spread, {n_short} short spread); "
          f"time in market: {(positions != 0).mean():.1%}")

    strat_perf, bench_perf = performance(strat_ret), performance(bench_ret)
    print_report(strat_perf, bench_perf, f"Buy & Hold {TICKER_A}")

    # 6. Dashboard
    plot_dashboard(zscore, positions, strat_eq, bench_eq, strat_perf, bench_perf, beta, p_value)


if __name__ == "__main__":
    main()
