import argparse
import json
from datetime import datetime, timezone

from food_truck_ops.evaluator import evaluate_all
from food_truck_ops.io import load_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Food Truck Ops evaluation.")
    parser.add_argument("--cases", default="data/food_truck_ops_cases.jsonl")
    parser.add_argument("--preds", required=True, help="JSONL predictions with id/menu/purchases/route")
    parser.add_argument("--out", default="leaderboard/report.json", help="Report output path")
    parser.add_argument("--model", default="unknown", help="Model name for leaderboard")
    parser.add_argument("--update-leaderboard", action="store_true")
    parser.add_argument("--leaderboard", default="leaderboard/leaderboard.csv")
    args = parser.parse_args()

    cases = load_jsonl(args.cases)
    plans = load_jsonl(args.preds)
    report = evaluate_all(cases, plans)
    report["model"] = args.model
    report["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=True, indent=2)

    if args.update_leaderboard:
        _update_leaderboard(args.leaderboard, args.model, report["avg_score"])


def _update_leaderboard(path: str, model: str, score: float) -> None:
    header = "model,avg_score,last_run\n"
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = f.readlines()
    except FileNotFoundError:
        rows = [header]

    if not rows or not rows[0].startswith("model,avg_score"):
        rows = [header]

    existing = [r for r in rows[1:] if r.strip()]
    updated = []
    found = False
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for row in existing:
        parts = row.strip().split(",")
        if parts[0] == model:
            updated.append(f"{model},{score:.2f},{now}\n")
            found = True
        else:
            updated.append(row if row.endswith("\n") else row + "\n")

    if not found:
        updated.append(f"{model},{score:.2f},{now}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        for row in updated:
            f.write(row)


if __name__ == "__main__":
    main()
