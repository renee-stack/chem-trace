from copy import deepcopy

# -----------------------------
# CONFIG
# -----------------------------

DEFAULT_REAGENT_COST = 20.0

PRICE_MAP = {
    "Pd catalyst": 120.0,
    "Palladium": 120.0,
    "Iron catalyst": 12.0,
    "Fe catalyst": 12.0,
    "Nickel catalyst": 40.0,
    "Ni catalyst": 40.0,
    "Copper catalyst": 18.0,
    "Cu catalyst": 18.0,
    "THF": 8.0,
    "DMF": 15.0,
    "DMSO": 10.0,
    "Toluene": 6.0,
    "Ethanol": 4.0,
    "Methanol": 5.0,
    "Acetonitrile": 9.0,
    "NaOH": 3.0,
    "K2CO3": 4.0,
    "HCl": 2.0,
    "H2SO4": 3.0,
    "Brominating agent": 30.0,
    "Rare ligand": 90.0,
    "Protected intermediate": 45.0,
    "Boronic acid": 25.0,
    "Amine coupling reagent": 35.0,
}

SUPPLY_RISK_MAP = {
    "Pd catalyst": "HIGH",
    "Palladium": "HIGH",
    "Rare ligand": "HIGH",
    "Protected intermediate": "HIGH",
    "Nickel catalyst": "MEDIUM",
    "Ni catalyst": "MEDIUM",
    "Boronic acid": "MEDIUM",
    "Amine coupling reagent": "MEDIUM",
    "DMF": "MEDIUM",
    "DMSO": "MEDIUM",
    "Iron catalyst": "LOW",
    "Fe catalyst": "LOW",
    "Copper catalyst": "LOW",
    "Cu catalyst": "LOW",
    "THF": "LOW",
    "Ethanol": "LOW",
    "Methanol": "LOW",
    "Toluene": "LOW",
    "NaOH": "LOW",
    "K2CO3": "LOW",
    "HCl": "LOW",
    "H2SO4": "LOW",
    "Acetonitrile": "LOW",
}

REGULATORY_RISK_MAP = {
    "Pd catalyst": "HIGH",
    "Palladium": "HIGH",
    "Brominating agent": "HIGH",
    "Rare ligand": "HIGH",
    "Nickel catalyst": "MEDIUM",
    "Ni catalyst": "MEDIUM",
    "DMF": "MEDIUM",
    "DMSO": "MEDIUM",
    "Protected intermediate": "MEDIUM",
    "Iron catalyst": "LOW",
    "Fe catalyst": "LOW",
    "Copper catalyst": "LOW",
    "Cu catalyst": "LOW",
    "THF": "LOW",
    "Ethanol": "LOW",
    "Methanol": "LOW",
    "NaOH": "LOW",
    "K2CO3": "LOW",
    "HCl": "LOW",
    "H2SO4": "LOW",
    "Acetonitrile": "LOW",
    "Boronic acid": "LOW",
    "Amine coupling reagent": "LOW",
}

RISK_SCORE_MAP = {"LOW": 100, "MEDIUM": 60, "HIGH": 20}


# -----------------------------
# COST FUNCTION
# -----------------------------

def add_costs(routes):
    routes = deepcopy(routes)

    for route in routes:
        base_cost = sum(PRICE_MAP.get(r, DEFAULT_REAGENT_COST) for r in route["reagents"])
        step_cost = route["step_count"] * 10
        yield_factor = 1 / max(route["yield_estimate"], 0.2)

        route["cost_per_gram"] = round((base_cost + step_cost) * yield_factor, 2)

    return routes


# -----------------------------
# RISK FUNCTION
# -----------------------------

def add_risks(routes):
    routes = deepcopy(routes)

    for route in routes:
        supply = "LOW"
        regulatory = "LOW"
        notes = []

        for r in route["reagents"]:
            s_risk = SUPPLY_RISK_MAP.get(r, "MEDIUM")
            r_risk = REGULATORY_RISK_MAP.get(r, "MEDIUM")

            if s_risk == "HIGH":
                supply = "HIGH"
            elif s_risk == "MEDIUM" and supply != "HIGH":
                supply = "MEDIUM"

            if r_risk == "HIGH":
                regulatory = "HIGH"
            elif r_risk == "MEDIUM" and regulatory != "HIGH":
                regulatory = "MEDIUM"

            if s_risk != "LOW" or r_risk != "LOW":
                notes.append(f"{r} introduces risk ({s_risk}/{r_risk})")

        route["supply_chain_risk"] = supply
        route["regulatory_risk"] = regulatory
        route["risk_notes"] = notes

    return routes


# -----------------------------
# SCORING
# -----------------------------

def score_route(route, min_cost, max_cost):
    cost = route["cost_per_gram"]

    if max_cost == min_cost:
        cost_score = 100
    else:
        cost_score = 100 * (max_cost - cost) / (max_cost - min_cost)

    yield_score = route["yield_estimate"] * 100
    step_score = max(0, 100 - (route["step_count"] - 1) * 15)

    risk_score = (
        RISK_SCORE_MAP[route["supply_chain_risk"]] +
        RISK_SCORE_MAP[route["regulatory_risk"]]
    ) / 2

    total = (
        0.35 * cost_score +
        0.25 * risk_score +
        0.20 * yield_score +
        0.20 * step_score
    )

    return round(total, 2)


# -----------------------------
# RANKING
# -----------------------------

def rank_routes(routes):
    routes = deepcopy(routes)

    costs = [r["cost_per_gram"] for r in routes]
    min_cost, max_cost = min(costs), max(costs)

    for r in routes:
        r["score"] = score_route(r, min_cost, max_cost)

        if (
            r["supply_chain_risk"] == "HIGH" and
            r["regulatory_risk"] == "HIGH"
        ) or r["score"] < 35:
            r["status"] = "REJECTED"
        else:
            r["status"] = "ACCEPTED"

    routes.sort(key=lambda x: -x["score"])

    for r in routes:
        r["decision_reason"] = generate_explanation(r, routes)

    return routes


# -----------------------------
# EXPLANATION
# -----------------------------

def generate_explanation(route, routes):
    if route["status"] == "REJECTED":
        return "Rejected due to high risk or poor overall score."

    best = routes[0]

    if route == best:
        return "Selected as best route due to strong balance of cost, risk, yield, and steps."

    return "Viable route but not optimal compared to alternatives."


# -----------------------------
# PIPELINE
# -----------------------------

def evaluate_routes(routes):
    routes = add_costs(routes)
    routes = add_risks(routes)
    routes = rank_routes(routes)
    return routes


# -----------------------------
# QUICK TEST
# -----------------------------

if __name__ == "__main__":
    routes = [
        {
            "route_id": "R1",
            "steps": ["A -> B", "B -> C"],
            "reagents": ["Pd catalyst", "THF"],
            "step_count": 2,
            "yield_estimate": 0.84,
            "literature": "USPTO",
            "cost_per_gram": None,
            "supply_chain_risk": None,
            "regulatory_risk": None,
            "risk_notes": [],
            "score": None,
            "status": None,
            "decision_reason": None
        }
    ]

    print(evaluate_routes(routes))