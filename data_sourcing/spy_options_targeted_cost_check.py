import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import databento as db


DATASET = "OPRA.PILLAR"
SYMBOLS = ["SPY.OPT"]
STYPE_IN = "parent"
SCHEMA = "cbbo-1m"
YEARS = [2021, 2022, 2023]
ET = ZoneInfo("America/New_York")

# Metadata cost estimates are documented as most accurate for ranges that are
# discrete multiples of 10 minutes, so use a conservative 10-minute window.
WINDOW_START = time(15, 50)
WINDOW_MINUTES = 10


def iter_weekdays(year):
    d = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    while d < end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def window(d):
    start = datetime.combine(d, WINDOW_START, tzinfo=ET)
    end = start + timedelta(minutes=WINDOW_MINUTES)
    return start.isoformat(), end.isoformat()


def cost_for_dates(client, dates, label):
    total = 0.0
    count = 0
    errors = 0
    for d in dates:
        start, end = window(d)
        try:
            cost = float(
                client.metadata.get_cost(
                    dataset=DATASET,
                    symbols=SYMBOLS,
                    schema=SCHEMA,
                    start=start,
                    end=end,
                    stype_in=STYPE_IN,
                )
            )
            total += cost
            count += 1
        except Exception as exc:
            errors += 1
            print(f"{label} {d}: ERROR {exc}")
    return total, count, errors


def main():
    key = os.getenv("DATABENTO_API_KEY")
    if not key:
        raise RuntimeError("DATABENTO_API_KEY is not set in this shell.")

    client = db.Historical(key)

    print("=== TARGETED SPY OPTIONS COST CHECK ===")
    print("This script only queries Databento metadata. It downloads nothing.")
    print("Dataset:", DATASET)
    print("Schema:", SCHEMA)
    print("Parent:", SYMBOLS[0])
    print(f"Window: {WINDOW_START.strftime('%H:%M')} ET for {WINDOW_MINUTES} minutes")
    print("Years:", YEARS)
    print()

    weekly_total = 0.0
    daily_total = 0.0

    for year in YEARS:
        weekdays = list(iter_weekdays(year))

        # Conservative weekly discovery schedule: one chain snapshot each Monday.
        # Exchange holidays simply return zero/no data; this is only a cost bound,
        # not the final trading calendar.
        mondays = [d for d in weekdays if d.weekday() == 0]
        w_cost, w_n, w_err = cost_for_dates(client, mondays, f"weekly-{year}")

        # Upper bound: full SPY chain snapshot every weekday. In the actual
        # two-pass backtest, after the spread is selected we will request only
        # the two held raw option symbols, so realized tracking cost should be
        # dramatically below this full-chain bound.
        d_cost, d_n, d_err = cost_for_dates(client, weekdays, f"daily-{year}")

        weekly_total += w_cost
        daily_total += d_cost

        print(f"--- {year} ---")
        print(f"weekly full-chain snapshots: ${w_cost:9.4f} across {w_n} weekday Mondays; errors={w_err}")
        print(f"daily  full-chain snapshots: ${d_cost:9.4f} across {d_n} weekdays; errors={d_err}")
        print()

    print("=== 2021-2023 TOTALS ===")
    print(f"Weekly full-chain discovery windows: ${weekly_total:9.4f}")
    print(f"Daily full-chain upper bound:        ${daily_total:9.4f}")
    print()

    print("Interpretation:")
    print("1) Weekly discovery is the relevant first-pass cost: it lets us choose the spread from the chain.")
    print("2) Daily full-chain is intentionally wasteful and serves only as an upper bound.")
    print("3) After choosing the two legs, request CBBO-1m only for those raw symbols on mark/exit dates.")
    print("4) Skip OPRA statistics/open-interest data in the baseline experiment.")
    print("5) Definitions are small and can be purchased separately after the snapshot cost is acceptable.")


if __name__ == "__main__":
    main()
