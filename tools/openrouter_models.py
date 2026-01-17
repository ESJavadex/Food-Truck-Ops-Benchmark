import argparse
import json
import os
import urllib.request


def _load_env(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key and key not in os.environ:
                os.environ[key] = value


def _fetch_models(api_key: str) -> dict:
    url = "https://openrouter.ai/api/v1/models"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _match(name: str, needles: list[str]) -> bool:
    if not needles:
        return True
    name_lower = name.lower()
    return any(n.lower() in name_lower for n in needles)


def main() -> None:
    parser = argparse.ArgumentParser(description="List OpenRouter model IDs.")
    parser.add_argument("--filter", nargs="*", default=[], help="Substring filter(s)")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    _load_env(".env")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENROUTER_API_KEY env var.")

    data = _fetch_models(api_key)
    models = data.get("data", [])
    results = []
    for model in models:
        model_id = model.get("id", "")
        if _match(model_id, args.filter):
            results.append(model_id)

    for model_id in results[: args.limit]:
        print(model_id)


if __name__ == "__main__":
    main()
