import argparse
import sys

from food_truck_ops.io import load_jsonl
from food_truck_ops.validate import validate_case


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Food Truck Ops cases.")
    parser.add_argument("--cases", default="data/food_truck_ops_cases.jsonl")
    args = parser.parse_args()

    cases = load_jsonl(args.cases)
    ok = True
    for case in cases:
        valid, reason = validate_case(case)
        if not valid:
            ok = False
            print(f"{case.get('id','unknown')}: {reason}")

    if not ok:
        sys.exit(1)

    print(f"validated {len(cases)} cases")


if __name__ == "__main__":
    main()
