import argparse
import json
import os
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
    parser.add_argument("--tokens", type=int, default=0, help="Total tokens used for the run")
    parser.add_argument("--cost", type=float, default=0.0, help="Total cost for the run in USD")
    parser.add_argument("--runtime", type=float, default=0.0, help="Runtime in seconds")
    parser.add_argument("--meta", default="", help="Optional metadata JSON from generation")
    args = parser.parse_args()

    cases = load_jsonl(args.cases)
    plans = load_jsonl(args.preds)
    report = evaluate_all(cases, plans)
    tokens = args.tokens
    cost = args.cost
    runtime = args.runtime
    if args.meta:
        meta = _load_meta(args.meta)
        tokens = tokens or meta.get("tokens_total", 0)
        cost = cost or meta.get("cost_usd_total", 0)
        runtime = runtime or meta.get("runtime_sec", 0)
    report["model"] = args.model
    report["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report["tokens"] = tokens
    report["cost_usd"] = cost
    report["runtime_sec"] = runtime
    report.update(_derive_run_metrics(report))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=True, indent=2)

    _write_model_report(report, args.model)

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


def _safe_model_id(model: str) -> str:
    return model.replace("/", "__").replace(":", "__")


def _write_model_report(report: dict, model: str) -> None:
    out_dir = "leaderboard/reports"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{_safe_model_id(model)}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=True, indent=2)


def _derive_run_metrics(report: dict) -> dict:
    results = report.get("results", [])
    total = len(results)
    valid = [r for r in results if "error" not in r]
    constraint_full = [r for r in valid if r.get("constraint_score") == 20.0]
    success_rate = len(valid) / total if total else 0.0
    constraint_rate = len(constraint_full) / len(valid) if valid else 0.0
    return {
        "valid_rate": round(success_rate, 3),
        "constraint_success_rate": round(constraint_rate, 3),
        "valid_cases": len(valid),
        "total_cases": total,
    }


def _load_meta(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("totals", {}) if "totals" in data else data
    except FileNotFoundError:
        return {}


if __name__ == "__main__":
    main()
