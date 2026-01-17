from typing import Dict, Any, List, Tuple


def build_lookup(items: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    return {item[key]: item for item in items}


def validate_case(case: Dict[str, Any]) -> Tuple[bool, str]:
    required = ["id", "hours", "budget", "capacity_units", "locations", "menu_items", "ingredients", "constraints", "profit_scale"]
    for field in required:
        if field not in case:
            return False, f"missing field: {field}"
    if not case["hours"]:
        return False, "hours empty"
    return True, ""


def validate_plan(case: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[bool, str]:
    if "menu" not in plan or "purchases" not in plan or "route" not in plan:
        return False, "plan must include menu, purchases, route"

    menu_items = build_lookup(case["menu_items"], "item")
    ingredients = build_lookup(case["ingredients"], "name")
    locations = {loc["name"] for loc in case["locations"]}

    menu = plan["menu"]
    if not isinstance(menu, list) or not menu:
        return False, "menu must be a non-empty list"
    for entry in menu:
        if "item" not in entry:
            return False, "menu entry missing item"
        if entry["item"] not in menu_items:
            return False, f"unknown menu item: {entry['item']}"

    purchases = plan["purchases"]
    if not isinstance(purchases, dict):
        return False, "purchases must be an object"
    for name, qty in purchases.items():
        if name not in ingredients:
            return False, f"unknown ingredient: {name}"
        if not isinstance(qty, int) or qty < 0:
            return False, f"invalid purchase quantity: {name}"

    route = plan["route"]
    if not isinstance(route, list) or not route:
        return False, "route must be a non-empty list"

    hour_to_location = {}
    for block in route:
        if "location" not in block or "hours" not in block:
            return False, "route block missing location/hours"
        if block["location"] not in locations:
            return False, f"unknown location: {block['location']}"
        if not isinstance(block["hours"], list) or not block["hours"]:
            return False, "route hours must be a non-empty list"
        for hour in block["hours"]:
            if hour in hour_to_location:
                return False, f"hour duplicated in route: {hour}"
            hour_to_location[hour] = block["location"]

    missing = [h for h in case["hours"] if h not in hour_to_location]
    if missing:
        return False, "route does not cover all hours"

    return True, ""
