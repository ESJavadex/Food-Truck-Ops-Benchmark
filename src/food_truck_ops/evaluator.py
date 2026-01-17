from typing import Dict, Any, List, Tuple

from .validate import build_lookup, validate_case, validate_plan


def _hour_location_map(route: List[Dict[str, Any]]) -> Dict[str, str]:
    mapping = {}
    for block in route:
        for hour in block["hours"]:
            mapping[hour] = block["location"]
    return mapping


def _ingredient_costs(ingredients: List[Dict[str, Any]]) -> Dict[str, float]:
    return {item["name"]: item["unit_cost"] for item in ingredients}


def _ingredient_units(ingredients: List[Dict[str, Any]]) -> Dict[str, int]:
    return {item["name"]: item["storage_units"] for item in ingredients}


def _menu_lookup(menu_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return build_lookup(menu_items, "item")


def _constraints_score(case: Dict[str, Any], plan: Dict[str, Any], hour_map: Dict[str, str]) -> Tuple[float, List[str]]:
    menu_items = _menu_lookup(case["menu_items"])
    selected_menu = [entry["item"] for entry in plan["menu"]]
    selected_set = set(selected_menu)

    total = len(case["constraints"]) if case["constraints"] else 0
    if total == 0:
        return 20.0, []

    failures = []
    passed = 0
    for constraint in case["constraints"]:
        ctype = constraint["type"]
        ok = True
        if ctype == "required_location_hours":
            location = constraint["location"]
            min_hours = constraint["min_hours"]
            hours = sum(1 for h, loc in hour_map.items() if loc == location)
            ok = hours >= min_hours
        elif ctype == "max_price":
            max_price = constraint["value"]
            ok = all(menu_items[item]["price"] <= max_price for item in selected_set)
        elif ctype == "forbidden_item_hours":
            item = constraint["item"]
            hours = set(constraint["hours"])
            if item in selected_set:
                ok = all(h not in hours for h in hour_map)
        elif ctype == "vegan_only_hours":
            hours = set(constraint["hours"])
            if any(h in hours for h in hour_map):
                ok = all(menu_items[item]["diet"] == "vegan" for item in selected_set)
        elif ctype == "max_menu_items":
            ok = len(selected_set) <= constraint["value"]
        elif ctype == "min_menu_items":
            ok = len(selected_set) >= constraint["value"]
        elif ctype == "must_include_item":
            ok = constraint["item"] in selected_set
        else:
            ok = False

        if ok:
            passed += 1
        else:
            failures.append(ctype)

    return (passed / total) * 20.0, failures


def _budget_and_capacity_ok(case: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[bool, str]:
    ingredients = _ingredient_costs(case["ingredients"])
    storage_units = _ingredient_units(case["ingredients"])
    total_cost = sum(ingredients[name] * qty for name, qty in plan["purchases"].items())
    total_storage = sum(storage_units[name] * qty for name, qty in plan["purchases"].items())
    if total_cost > case["budget"]:
        return False, "budget_exceeded"
    if total_storage > case["capacity_units"]:
        return False, "capacity_exceeded"
    return True, ""


def _simulate_sales(case: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[float, float, Dict[str, int]]:
    menu_items = _menu_lookup(case["menu_items"])
    ingredients = _ingredient_costs(case["ingredients"])
    remaining = {name: qty for name, qty in plan["purchases"].items()}
    hour_map = _hour_location_map(plan["route"])

    revenue = 0.0
    sold = {item: 0 for item in menu_items}
    locations = build_lookup(case["locations"], "name")
    menu_order = [entry["item"] for entry in plan["menu"]]

    for hour in case["hours"]:
        location = hour_map[hour]
        demand = locations[location]["hourly_demand"][hour]
        for item in menu_order:
            recipe = menu_items[item]["ingredients"]
            max_servings = min(remaining.get(ing, 0) // req for ing, req in recipe.items())
            to_sell = min(demand.get(item, 0), max_servings)
            if to_sell <= 0:
                continue
            for ing, req in recipe.items():
                remaining[ing] -= to_sell * req
            sold[item] += to_sell
            revenue += to_sell * menu_items[item]["price"]

    total_cost = sum(ingredients[name] * qty for name, qty in plan["purchases"].items())
    waste_cost = sum(ingredients[name] * qty for name, qty in remaining.items())
    profit = revenue - total_cost
    return profit, waste_cost, sold


def evaluate_case(case: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    ok, reason = validate_case(case)
    if not ok:
        return {"id": case.get("id", "unknown"), "total_score": 0.0, "error": reason}

    ok, reason = validate_plan(case, plan)
    if not ok:
        return {"id": case["id"], "total_score": 0.0, "error": reason}

    ok, reason = _budget_and_capacity_ok(case, plan)
    if not ok:
        return {"id": case["id"], "total_score": 0.0, "error": reason}

    hour_map = _hour_location_map(plan["route"])
    profit, waste_cost, sold = _simulate_sales(case, plan)
    total_cost = sum(item["unit_cost"] * plan["purchases"].get(item["name"], 0) for item in case["ingredients"])
    scale = case["profit_scale"]
    denom = max(scale["target"] - scale["floor"], 1)
    profit_score = max(0.0, min(1.0, (profit - scale["floor"]) / denom)) * 60.0
    waste_ratio = waste_cost / max(total_cost, 1.0)
    waste_score = max(0.0, min(1.0, 1.0 - waste_ratio)) * 20.0
    constraint_score, failures = _constraints_score(case, plan, hour_map)
    total = profit_score + waste_score + constraint_score

    return {
        "id": case["id"],
        "total_score": round(total, 2),
        "profit": round(profit, 2),
        "profit_score": round(profit_score, 2),
        "waste_cost": round(waste_cost, 2),
        "waste_score": round(waste_score, 2),
        "constraint_score": round(constraint_score, 2),
        "constraint_failures": failures,
        "sold": sold,
    }


def evaluate_all(cases: List[Dict[str, Any]], plans: List[Dict[str, Any]]) -> Dict[str, Any]:
    plan_map = {plan["id"]: plan for plan in plans if "id" in plan}
    results = []
    missing = []
    for case in cases:
        plan = plan_map.get(case["id"])
        if plan is None:
            missing.append(case["id"])
            results.append({"id": case["id"], "total_score": 0.0, "error": "missing_plan"})
            continue
        results.append(evaluate_case(case, plan))

    avg_score = sum(r["total_score"] for r in results) / max(len(results), 1)
    return {
        "avg_score": round(avg_score, 2),
        "results": results,
        "missing": missing,
    }
