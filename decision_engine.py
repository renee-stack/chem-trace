from copy import deepcopy


# -----------------------------
# CONFIG
# -----------------------------

DEFAULT_REAGENT_COST = 20.0
STEP_OVERHEAD_COST = 10.0
MIN_YIELD_FOR_COST = 0.20
REJECTION_SCORE_THRESHOLD = 35.0

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
    # chemistry agent common reagents
    "Salicylic acid": 10.0,
    "Acetic anhydride": 8.0,
    "Catalytic sulfuric acid": 3.0,
    "Water": 1.0,
    "Ethanol (recrystallization grade)": 6.0,
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
    "Salicylic acid": "LOW",
    "Acetic anhydride": "LOW",
    "Catalytic sulfuric acid": "MEDIUM",
    "Water": "LOW",
    "Ethanol (recrystallization grade)": "LOW",
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
    "Salicylic acid": "LOW",
    "Acetic anhydride": "MEDIUM",
    "Catalytic sulfuric acid": "MEDIUM",
    "Water": "LOW",
    "Ethanol (recrystallization grade)": "LOW",
}

RISK_SCORE_MAP = {"LOW": 100, "MEDIUM": 60, "HIGH": 20}
RISK_PRIORITY = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


# -----------------------------
# HELPERS
# -----------------------------

def worst_risk(current, new):
    return new if RISK_PRIORITY[new] > RISK_PRIORITY[current] else current


def safe_get_reagents(route):
    return route.get("reagents", [])


def safe_get_step_count(route):
    return route.get("step_count", 0)


def safe_get_yield(route):
    return route.get("yield_estimate", 0.0)


def flatten_step_reagents(steps):
    reagents = []
    for step in steps:
        for reagent in step.get("reagents", []):
            if reagent not in reagents:
                reagents.append(reagent)
    return reagents


def estimate_route_yield(steps):
    """
    Multiply step yields if present.
    If no step-level yields exist, return a sensible default.
    """
    yields = []
    for step in steps:
        if isinstance(step, dict) and "yield" in step and isinstance(step["yield"], (int, float)):
            yields.append(step["yield"])

    if not yields:
        return 0.72  # hackathon-safe default

    total = 1.0
    for y in yields:
        total *= y
    return round(total, 4)


def extract_literature(steps):
    refs = []
    for step in steps:
        if "citation" in step and step["citation"]:
            refs.append(step["citation"])
        for link in step.get("literature_links", []):
            refs.append(link)
    return "; ".join(refs) if refs else "No literature provided"


# -----------------------------
# ADAPTER
# -----------------------------

def adapt_chemistry_output(chem_output):
    """
    Convert Person C's chemistry agent output into Person B's route format.
    Returns a LIST of route dicts.
    """
    route_plan = chem_output.get("route_plan") or {}
    steps = route_plan.get("steps", [])
    reagents = route_plan.get("reagents") or flatten_step_reagents(steps)

    base_route = {
        "route_id": "R1",
        "steps": [
            step.get("description") or step.get("reaction_type") or f"Step {idx + 1}"
            for idx, step in enumerate(steps)
        ],
        "reagents": reagents,
        "step_count": len(steps),
        "yield_estimate": estimate_route_yield(steps),
        "literature": extract_literature(steps),
        "cost_per_gram": None,
        "supply_chain_risk": None,
        "regulatory_risk": None,
        "risk_notes": [],
        "score": None,
        "status": None,
        "decision_reason": None,
    }

    return [base_route]


# -----------------------------
# DEMO VARIANT GENERATOR
# -----------------------------

def expand_demo_variants(routes):
    """
    Since current chemistry agent often returns only one route scaffold,
    create realistic MVP alternatives so ranking is meaningful.
    """
    if not routes:
        return []

    base = deepcopy(routes[0])

    # Variant 1: short but expensive / riskier
    r1 = deepcopy(base)
    r1["route_id"] = "R1"
    r1["reagents"] = list(dict.fromkeys(base["reagents"] + ["Pd catalyst", "THF"]))
    r1["yield_estimate"] = min(0.90, base["yield_estimate"] + 0.08)
    r1["step_count"] = max(2, base["step_count"] - 1)
    r1["steps"] = base["steps"][: r1["step_count"]]

    # Variant 2: balanced medium-risk route
    r2 = deepcopy(base)
    r2["route_id"] = "R2"
    r2["reagents"] = list(dict.fromkeys(base["reagents"] + ["Nickel catalyst", "Boronic acid"]))
    r2["yield_estimate"] = min(0.82, base["yield_estimate"] + 0.03)
    r2["step_count"] = base["step_count"]

    # Variant 3: longer but cheaper / safer
    r3 = deepcopy(base)
    r3["route_id"] = "R3"
    r3["reagents"] = list(dict.fromkeys(base["reagents"] + ["Iron catalyst", "Ethanol", "NaOH"]))
    r3["yield_estimate"] = max(0.55, base["yield_estimate"] - 0.05)
    r3["step_count"] = base["step_count"] + 1
    r3["steps"] = base["steps"] + ["Final purification / workup optimisation"]

    return [r1, r2, r3]


# -----------------------------
# COST FUNCTION
# -----------------------------

def add_costs(routes):
    routes = deepcopy(routes)

    for route in routes:
        base_cost = sum(PRICE_MAP.get(r, DEFAULT_REAGENT_COST) for r in route["reagents"])
        step_cost = route["step_count"] * STEP_OVERHEAD_COST
        yield_factor = 1 / max(route["yield_estimate"], MIN_YIELD_FOR_COST)
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

        for reagent in route["reagents"]:
            s_risk = SUPPLY_RISK_MAP.get(reagent, "MEDIUM")
            r_risk = REGULATORY_RISK_MAP.get(reagent, "MEDIUM")

            supply = worst_risk(supply, s_risk)
            regulatory = worst_risk(regulatory, r_risk)

            if s_risk != "LOW":
                notes.append(f"{reagent} introduces supply-chain risk ({s_risk})")
            if r_risk != "LOW":
                notes.append(f"{reagent} introduces regulatory risk ({r_risk})")

        if not notes:
            notes.append("No major reagent-level risk flags detected.")

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
        cost_score = 100.0
    else:
        cost_score = 100.0 * (max_cost - cost) / (max_cost - min_cost)

    yield_score = max(0.0, min(100.0, route["yield_estimate"] * 100.0))
    step_score = max(0.0, 100.0 - (route["step_count"] - 1) * 15.0)

    risk_score = (
        RISK_SCORE_MAP[route["supply_chain_risk"]] +
        RISK_SCORE_MAP[route["regulatory_risk"]]
    ) / 2.0

    total = (
        0.35 * cost_score +
        0.25 * risk_score +
        0.20 * yield_score +
        0.20 * step_score
    )

    return round(total, 2)


# -----------------------------
# REJECTION
# -----------------------------

def should_reject(route):
    both_high = (
        route["supply_chain_risk"] == "HIGH" and
        route["regulatory_risk"] == "HIGH"
    )
    weak_score = route["score"] < REJECTION_SCORE_THRESHOLD
    long_and_weak_yield = (
        route["step_count"] >= 5 and route["yield_estimate"] < 0.50
    )
    return both_high or weak_score or long_and_weak_yield


# -----------------------------
# EXPLANATION
# -----------------------------

def generate_explanation(route, best_route):
    cost = route["cost_per_gram"]
    step_count = route["step_count"]
    yield_pct = round(route["yield_estimate"] * 100, 1)

    if route["status"] == "REJECTED":
        reasons = []
        if route["supply_chain_risk"] == "HIGH" and route["regulatory_risk"] == "HIGH":
            reasons.append("it combines high supply-chain and regulatory risk")
        if route["score"] < REJECTION_SCORE_THRESHOLD:
            reasons.append("its overall score is too low")
        if step_count >= 5 and route["yield_estimate"] < 0.50:
            reasons.append("it is too long for its expected yield")

        joined = "; ".join(reasons) if reasons else "it is not competitive overall"
        return (
            f"Rejected because {joined}. "
            f"It has estimated cost {cost}/g, {step_count} steps, and {yield_pct}% expected yield."
        )

    if route["route_id"] == best_route["route_id"]:
        strengths = []

        if route["cost_per_gram"] <= best_route["cost_per_gram"]:
            strengths.append("competitive cost")
        if route["supply_chain_risk"] != "HIGH" and route["regulatory_risk"] != "HIGH":
            strengths.append("manageable risk")
        if route["yield_estimate"] >= 0.70:
            strengths.append("solid expected yield")
        if route["step_count"] <= 3:
            strengths.append("concise route length")

        strengths_text = ", ".join(strengths) if strengths else "the best overall trade-off"
        return (
            f"Selected as best route because it offers {strengths_text}. "
            f"It achieves estimated cost {cost}/g with {step_count} steps and {yield_pct}% expected yield."
        )

    tradeoffs = []

    if route["cost_per_gram"] < best_route["cost_per_gram"]:
        tradeoffs.append("it is cheaper than the selected route")
    elif route["cost_per_gram"] > best_route["cost_per_gram"]:
        tradeoffs.append("it is more expensive than the selected route")

    if route["yield_estimate"] > best_route["yield_estimate"]:
        tradeoffs.append("it has higher expected yield")
    elif route["yield_estimate"] < best_route["yield_estimate"]:
        tradeoffs.append("it has lower expected yield")

    if route["step_count"] < best_route["step_count"]:
        tradeoffs.append("it uses fewer steps")
    elif route["step_count"] > best_route["step_count"]:
        tradeoffs.append("it uses more steps")

    if (
        route["supply_chain_risk"] == "LOW" and
        best_route["supply_chain_risk"] != "LOW"
    ) or (
        route["regulatory_risk"] == "LOW" and
        best_route["regulatory_risk"] != "LOW"
    ):
        tradeoffs.append("it is safer on key risk flags")

    tradeoff_text = "; ".join(tradeoffs) if tradeoffs else "it remains a viable fallback"
    return (
        f"Accepted but not selected because {tradeoff_text}. "
        f"It scores {route['score']} with estimated cost {cost}/g, {step_count} steps, and {yield_pct}% expected yield."
    )


# -----------------------------
# RANKING
# -----------------------------

def rank_routes(routes):
    routes = deepcopy(routes)

    if not routes:
        return routes

    costs = [r["cost_per_gram"] for r in routes]
    min_cost, max_cost = min(costs), max(costs)

    for route in routes:
        route["score"] = score_route(route, min_cost, max_cost)
        route["status"] = "REJECTED" if should_reject(route) else "ACCEPTED"

    routes.sort(key=lambda x: x["score"], reverse=True)

    best_accepted = next((r for r in routes if r["status"] == "ACCEPTED"), routes[0])

    for route in routes:
        route["decision_reason"] = generate_explanation(route, best_accepted)

    return routes


# -----------------------------
# PIPELINES
# -----------------------------

def evaluate_routes(routes):
    routes = add_costs(routes)
    routes = add_risks(routes)
    routes = rank_routes(routes)
    return routes


def evaluate_chemtrace_output(chem_output):
    """
    Main entry point when consuming Person C's chemistry agent output.
    """
    routes = adapt_chemistry_output(chem_output)
    routes = expand_demo_variants(routes)
    routes = evaluate_routes(routes)
    return routes


# -----------------------------
# QUICK TEST
# -----------------------------

if __name__ == "__main__":
    sample_chem_output = {
        "status": "success",
        "input_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "molecule_info": {},
        "route_plan": {
            "route_type": "hardcoded_demo",
            "target_name": "Aspirin",
            "reagents": [
                "Salicylic acid",
                "Acetic anhydride",
                "Catalytic sulfuric acid",
                "Water",
                "Ethanol (recrystallization grade)"
            ],
            "steps": [
                {
                    "step_number": 1,
                    "reaction_type": "Acetylation",
                    "description": "Acetylate salicylic acid using acetic anhydride.",
                    "reagents": [
                        "Salicylic acid",
                        "Acetic anhydride",
                        "Catalytic sulfuric acid"
                    ],
                    "literature_links": ["https://pubchem.ncbi.nlm.nih.gov/compound/Aspirin"]
                },
                {
                    "step_number": 2,
                    "reaction_type": "Workup and Recrystallization",
                    "description": "Quench, isolate crude product, and recrystallize for purification.",
                    "reagents": ["Water", "Ethanol (recrystallization grade)"],
                    "literature_links": ["https://en.wikipedia.org/wiki/Aspirin"]
                }
            ]
        },
        "errors": []
    }

    from pprint import pprint
    pprint(evaluate_chemtrace_output(sample_chem_output))