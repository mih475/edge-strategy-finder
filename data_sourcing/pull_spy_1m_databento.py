"""Pull 1-minute SPY bars from Databento for the EMA9+VWAP backtest.

Why this is cheap and safe:
  * schema 'ohlcv-1m' = aggregated 1-minute bars (NOT ticks/order-book), so the
    data volume is tiny - ~50-60 MB uncompressed for ~10 years of SPY.
  * The script calls Databento's get_cost() to get the dollar price BEFORE
    downloading, prints it, and ABORTS if it exceeds --max-cost (default $5).
    You physically cannot overspend your credit by running this.
  * Consolidated equities dataset (DBEQ.BASIC) so VWAP uses TOTAL volume, not a
    single venue - important, because VWAP is volume-weighted.

Setup (run once, on your machine, where the network + your key live):
    pip install databento
    set DATABENTO_API_KEY=db-xxxxxxxxxxxxxxxxxxxx        (Windows: set, no quotes)
  or pass --key db-xxxx on the command line.

Usage:
    # 1) TEST: pull ~1 month, see the real cost, write data/spy_1m_test.csv
    python data_sourcing/pull_spy_1m_databento.py --mode test

    # 2) FULL: estimate full-range cost, pull only if under --max-cost
    python data_sourcing/pull_spy_1m_databento.py --mode full --start 2016-01-01

Output CSV columns: datetime (ET), open, high, low, close, volume  -> data/spy_1m.csv
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import timedelta

import pandas as pd

# --- The dataset. DBEQ.BASIC is Databento's CONSOLIDATED US equities feed, which
# --- is what you want for an accurate (total-volume) VWAP. If your account prints
# --- a different equities dataset below (e.g. 'EQUS.SUMMARY', 'XNAS.ITCH'), set it
# --- here. The script lists available datasets on startup so you can see them.
DATASET = "DBEQ.BASIC"
SYMBOL = "SPY"
SCHEMA = "ohlcv-1m"


def _client(key: str | None):
    try:
        import databento as db
    except ImportError:
        sys.exit("databento not installed. Run:  pip install databento")
    key = key or os.environ.get("DATABENTO_API_KEY")
    if not key:
        sys.exit("No API key. Set DATABENTO_API_KEY env var or pass --key db-...")
    return db.Historical(key)


def main(argv=None):
    p = argparse.ArgumentParser(description="Pull 1-min SPY bars from Databento (cost-guarded)")
    p.add_argument("--mode", choices=["test", "full"], default="test")
    p.add_argument("--key", default=None, help="Databento API key (else env DATABENTO_API_KEY)")
    p.add_argument("--dataset", default=DATASET, help=f"default {DATASET}")
    p.add_argument("--start", default="2016-01-01", help="full mode start date (YYYY-MM-DD)")
    p.add_argument("--end", default=None, help="end date; default = latest available")
    p.add_argument("--max-cost", type=float, default=5.0,
                   help="abort if estimated cost exceeds this many USD (default 5)")
    p.add_argument("--all-hours", action="store_true",
                   help="keep extended hours too (default: regular session 09:30-16:00 ET only)")
    p.add_argument("--out", default="data/spy_1m.csv", help="output CSV path")
    args = p.parse_args(argv)

    client = _client(args.key)
    ds = args.dataset

    # What datasets does this account have? (so a wrong DATASET is obvious)
    try:
        datasets = client.metadata.list_datasets()
        print("Available datasets:", ", ".join(datasets))
    except Exception as e:
        print(f"(could not list datasets: {e})")

    # Available date range for this dataset
    rng = client.metadata.get_dataset_range(dataset=ds)
    avail_start = pd.Timestamp(rng["start"]).tz_convert("UTC") if pd.Timestamp(rng["start"]).tzinfo else pd.Timestamp(rng["start"], tz="UTC")
    avail_end = pd.Timestamp(rng["end"]).tz_convert("UTC") if pd.Timestamp(rng["end"]).tzinfo else pd.Timestamp(rng["end"], tz="UTC")
    print(f"\nDataset {ds} covers {avail_start.date()} -> {avail_end.date()}")

    if args.mode == "test":
        end = avail_end
        start = end - timedelta(days=30)
        out = args.out.replace(".csv", "_test.csv")
    else:
        start = max(pd.Timestamp(args.start, tz="UTC"), avail_start)
        end = pd.Timestamp(args.end, tz="UTC") if args.end else avail_end
        out = args.out

    start_s, end_s = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    print(f"Requesting {SYMBOL} {SCHEMA}  {start_s} -> {end_s}")

    # ---- COST CHECK (no data downloaded, no charge) ----
    cost = client.metadata.get_cost(
        dataset=ds, symbols=[SYMBOL], schema=SCHEMA, stype_in="raw_symbol",
        start=start_s, end=end_s,
    )
    print(f"\n>>> Estimated cost: ${cost:,.4f} USD")
    if cost > args.max_cost:
        sys.exit(f"ABORT: estimate ${cost:.2f} exceeds --max-cost ${args.max_cost:.2f}. "
                 f"Nothing was downloaded, nothing was charged. Re-run with a higher "
                 f"--max-cost if you're sure.")
    print(f"    (under the ${args.max_cost:.2f} cap - proceeding to download)\n")

    # ---- DOWNLOAD ----
    data = client.timeseries.get_range(
        dataset=ds, symbols=[SYMBOL], schema=SCHEMA, stype_in="raw_symbol",
        start=start_s, end=end_s,
    )
    df = data.to_df()  # tz-aware UTC index (ts_event), float prices, int volume
    if df.empty:
        sys.exit("No rows returned - check the symbol/dataset/date range.")

    # Normalize to the columns our backtest wants
    df = df.rename(columns={"ts_event": "datetime"})
    if df.index.name in ("ts_event", "datetime"):
        df = df.reset_index().rename(columns={"index": "datetime", "ts_event": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert("America/New_York")
    keep = ["datetime", "open", "high", "low", "close", "volume"]
    df = df[[c for c in keep if c in df.columns]].sort_values("datetime")

    if not args.all_hours:
        t = df["datetime"].dt.time
        import datetime as _dt
        rth = (t >= _dt.time(9, 30)) & (t < _dt.time(16, 0))
        df = df[rth]

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    df.to_csv(out, index=False)
    mb = os.path.getsize(out) / 1e6
    print(f"Saved {len(df):,} rows -> {out}  ({mb:.1f} MB)")
    print(f"Range: {df['datetime'].iloc[0]} -> {df['datetime'].iloc[-1]}")
    print(f"Actual billed cost was ${cost:,.4f} (as estimated above).")


if __name__ == "__main__":
    main()
