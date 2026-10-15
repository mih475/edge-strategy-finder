import os
import databento as db


DATASET = "OPRA.PILLAR"
SYMBOLS = ["SPY.OPT"]
STYPE_IN = "parent"
YEARS = range(2018, 2027)
SCHEMAS = ["cbbo-1m", "statistics", "definition"]


def main():
    key = os.getenv("DATABENTO_API_KEY")
    if not key:
        raise RuntimeError("DATABENTO_API_KEY is not set in this shell.")

    client = db.Historical(key)

    print("=== DATABENTO SPY OPTIONS HISTORICAL COST CHECK ===")
    print("Dataset:", DATASET)
    print("Parent symbol:", SYMBOLS[0])
    print("This script only queries Databento metadata. It does NOT download market data.\n")

    print("Current OPRA unit prices ($/GB):")
    prices = client.metadata.list_unit_prices(dataset=DATASET)
    for row in prices:
        mode = getattr(row, "mode", None)
        unit_prices = getattr(row, "unit_prices", None)
        if mode is None and isinstance(row, dict):
            mode = row.get("mode")
            unit_prices = row.get("unit_prices")
        if str(mode) == "historical" or mode == "historical":
            print(unit_prices)
    print()

    grand_total = 0.0
    schema_totals = {s: 0.0 for s in SCHEMAS}

    for year in YEARS:
        start = f"{year}-01-01"
        end = f"{year + 1}-01-01"
        print(f"--- {year} ---")
        for schema in SCHEMAS:
            try:
                cost = client.metadata.get_cost(
                    dataset=DATASET,
                    symbols=SYMBOLS,
                    schema=schema,
                    start=start,
                    end=end,
                    stype_in=STYPE_IN,
                )
                size = client.metadata.get_billable_size(
                    dataset=DATASET,
                    symbols=SYMBOLS,
                    schema=schema,
                    start=start,
                    end=end,
                    stype_in=STYPE_IN,
                )
                gb = float(size) / 1_000_000_000.0
                cost = float(cost)
                schema_totals[schema] += cost
                grand_total += cost
                print(f"{schema:12s}  ${cost:9.4f}   {gb:10.4f} GB billable")
            except Exception as exc:
                print(f"{schema:12s}  ERROR: {exc}")
        print()

    print("=== TOTALS 2018-2026 ===")
    for schema, total in schema_totals.items():
        print(f"{schema:12s}  ${total:9.4f}")
    print(f"ALL SCHEMAS   ${grand_total:9.4f}")

    print("\nRecommended baseline purchase if cost is acceptable:")
    print("1) CBBO-1m: minute NBBO bid/ask and last sale for SPY options")
    print("2) Definition: strike, expiration, put/call and contract metadata")
    print("3) Statistics: primarily open interest history")
    print("No data is downloaded by this estimator.")


if __name__ == "__main__":
    main()
