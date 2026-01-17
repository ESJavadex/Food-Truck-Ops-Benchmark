import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed


def _safe_model_id(model: str) -> str:
    return model.replace("/", "__").replace(":", "__")


def _load_models(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("models", [])


def _run_one(model: str, args: argparse.Namespace) -> dict:
    safe = _safe_model_id(model)
    preds = os.path.join(args.preds_dir, f"{safe}.jsonl")
    meta = os.path.join(args.preds_dir, f"{safe}_meta.json")
    gen_cmd = [
        "python",
        "tools/openrouter_generate.py",
        "--cases",
        args.cases,
        "--model",
        model,
        "--out",
        preds,
        "--response-format",
        args.response_format,
        "--temperature",
        str(args.temperature),
        "--retries",
        str(args.retries),
    ]
    eval_cmd = [
        "python",
        "tools/run_eval.py",
        "--preds",
        preds,
        "--model",
        model,
        "--update-leaderboard",
        "--meta",
        meta,
    ]
    subprocess.run(gen_cmd, check=True)
    subprocess.run(eval_cmd, check=True)
    return {"model": model, "preds": preds}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multiple models in parallel.")
    parser.add_argument("--models", required=True, help="JSON file with models list")
    parser.add_argument("--cases", default="data/food_truck_ops_cases.jsonl")
    parser.add_argument("--preds-dir", default="predictions")
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--response-format", choices=["none", "json"], default="json")
    args = parser.parse_args()

    os.makedirs(args.preds_dir, exist_ok=True)
    models = _load_models(args.models)
    if not models:
        raise SystemExit("No models found in models file.")

    results = []
    failures = []
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {executor.submit(_run_one, model, args): model for model in models}
        for future in as_completed(futures):
            model = futures[future]
            try:
                results.append(future.result())
            except subprocess.CalledProcessError as exc:
                failures.append({"model": model, "error": str(exc)})

    if failures:
        for failure in failures:
            print(f"FAILED {failure['model']}: {failure['error']}")
        raise SystemExit(1)

    for result in results:
        print(f"OK {result['model']} -> {result['preds']}")


if __name__ == "__main__":
    main()
