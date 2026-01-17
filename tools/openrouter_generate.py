import argparse
import json
import os
import time
import urllib.request

from food_truck_ops.io import load_jsonl, write_jsonl


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


def _build_prompt(case: dict) -> str:
    return (
        "You are planning a food truck day. Return ONLY valid JSON.\n"
        "Output format:\n"
        "{"
        '"id": "...",'
        '"menu":[{"item":"..."}],'
        '"purchases":{"ingredient": quantity_int},'
        '"route":[{"location":"...","hours":["HH",...]}]'
        "}\n\n"
        "Case:\n"
        f"{json.dumps(case, ensure_ascii=True)}\n"
        "Rules:\n"
        "- Use only menu_items and ingredients from the case.\n"
        "- Cover every hour exactly once in route.\n"
        "- Respect budget, capacity_units, and constraints.\n"
        "- Keep JSON compact, no extra keys.\n"
    )

def _build_repair_prompt(case: dict, raw: str) -> str:
    return (
        "You must return ONLY a valid JSON object for the plan.\n"
        "If the previous text is not valid JSON, ignore it and produce a correct JSON plan.\n"
        "Output format:\n"
        "{"
        '"id": "...",'
        '"menu":[{"item":"..."}],'
        '"purchases":{"ingredient": quantity_int},'
        '"route":[{"location":"...","hours":["HH",...]}]'
        "}\n\n"
        "Case:\n"
        f"{json.dumps(case, ensure_ascii=True)}\n"
        "Previous text:\n"
        f"{raw}\n"
        "Rules:\n"
        "- Use only menu_items and ingredients from the case.\n"
        "- Cover every hour exactly once in route.\n"
        "- Respect budget, capacity_units, and constraints.\n"
        "- JSON only.\n"
    )

def _extract_message_text(message: dict) -> str:
    content = message.get("content")
    if content:
        return content
    reasoning = message.get("reasoning") or ""
    if reasoning:
        return reasoning
    details = message.get("reasoning_details") or []
    if details:
        joined = "\n".join(d.get("text", "") for d in details if d.get("text"))
        if joined:
            return joined
    return ""


def _call_openrouter(api_key: str, model: str, prompt: str, max_tokens: int, temperature: float) -> dict:
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise planner that returns strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    response_format = os.environ.get("OPENROUTER_RESPONSE_FORMAT")
    if response_format == "json":
        payload["response_format"] = {"type": "json_object"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
    if not body:
        raise RuntimeError("Empty response body from OpenRouter.")
    result = json.loads(body)
    if "error" in result:
        raise RuntimeError(f"OpenRouter error: {result['error']}")
    message = result["choices"][0]["message"]
    text = _extract_message_text(message)
    if not text:
        raise RuntimeError(f"Empty content from model response: {result}")
    return {
        "text": text,
        "usage": result.get("usage", {}),
        "raw": result,
    }


def _strip_think_blocks(text: str) -> str:
    start_tag = "<think>"
    end_tag = "</think>"
    while True:
        start = text.find(start_tag)
        if start == -1:
            break
        end = text.find(end_tag, start + len(start_tag))
        if end == -1:
            text = text[:start]
            break
        text = text[:start] + text[end + len(end_tag) :]
    return text


def _extract_first_json(text: str) -> str:
    text = _strip_think_blocks(text.strip())
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text


def _parse_json(text: str) -> dict:
    candidate = _extract_first_json(text)
    return json.loads(candidate)


def _normalize_plan(parsed: object) -> dict:
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list) and parsed:
        first = parsed[0]
        if isinstance(first, dict):
            return first
    raise ValueError("Parsed JSON is not an object plan.")


def _safe_model_id(model: str) -> str:
    return model.replace("/", "__").replace(":", "__")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Food Truck Ops plans via OpenRouter.")
    parser.add_argument("--cases", default="data/food_truck_ops_cases.jsonl")
    parser.add_argument("--out", default="predictions/openrouter_preds.jsonl")
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-tokens", type=int, default=800)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--meta-out", default="", help="Optional JSON file for run metadata")
    parser.add_argument(
        "--response-format",
        choices=["none", "json"],
        default="none",
        help="Pass response_format to OpenRouter (json uses json_object).",
    )
    args = parser.parse_args()

    _load_env(".env")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENROUTER_API_KEY env var.")

    if args.response_format == "json":
        os.environ["OPENROUTER_RESPONSE_FORMAT"] = "json"
    cases = load_jsonl(args.cases)
    outputs = []
    usage_rows = []
    start_time = time.time()
    for case in cases:
        prompt = _build_prompt(case)
        raw = ""
        plan = None
        for attempt in range(args.retries + 1):
            response = _call_openrouter(api_key, args.model, prompt, args.max_tokens, args.temperature)
            raw = response["text"]
            try:
                plan = _normalize_plan(_parse_json(raw))
                usage = response.get("usage", {})
                usage_rows.append(
                    {
                        "id": case["id"],
                        "total_tokens": usage.get("total_tokens", 0),
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "cost_usd": usage.get("cost", 0),
                    }
                )
                break
            except json.JSONDecodeError:
                prompt = _build_repair_prompt(case, raw)
                time.sleep(args.sleep)
            except ValueError:
                prompt = _build_repair_prompt(case, raw)
                time.sleep(args.sleep)
        if plan is None:
            failed_dir = os.path.join(os.path.dirname(args.out), "failed")
            os.makedirs(failed_dir, exist_ok=True)
            failed_path = os.path.join(failed_dir, f"{case['id']}.txt")
            with open(failed_path, "w", encoding="utf-8") as f:
                f.write(raw)
            raise SystemExit(f"Failed to parse JSON for case {case['id']}. See {failed_path}")
        if "id" not in plan:
            plan["id"] = case["id"]
        outputs.append(plan)
        time.sleep(args.sleep)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    write_jsonl(args.out, outputs)

    runtime = round(time.time() - start_time, 3)
    totals = {
        "tokens_total": sum(r["total_tokens"] for r in usage_rows),
        "prompt_tokens_total": sum(r["prompt_tokens"] for r in usage_rows),
        "completion_tokens_total": sum(r["completion_tokens"] for r in usage_rows),
        "cost_usd_total": round(sum(r["cost_usd"] for r in usage_rows), 6),
        "runtime_sec": runtime,
        "requests": len(usage_rows),
        "model": args.model,
    }
    meta = {"totals": totals, "per_case": usage_rows}
    meta_path = args.meta_out
    if not meta_path:
        base = _safe_model_id(args.model)
        meta_path = os.path.join(os.path.dirname(args.out), f"{base}_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=True, indent=2)


if __name__ == "__main__":
    main()
