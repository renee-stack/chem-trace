"""Interactive CLI for the ChemTrace chemistry scouting agent."""

import json
import os
import sys

from decision_engine import evaluate_chemtrace_output

# Add project root for src imports when run from repository root.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

import pubchempy as pcp

from src.agents.chemistry_agent import ChemistryAgent


def main() -> None:
    """Run an interactive terminal loop for molecule scouting."""
    agent = ChemistryAgent()

    print("========================================")
    print("ChemTrace: Autonomous Chemistry Scout")
    print("========================================")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        user_input = input("\nEnter Molecule SMILES > ").strip()

        if user_input.lower() in ["exit", "quit"]:
            print("Shutting down scout...")
            break

        if not user_input:
            continue

        if not any(char in user_input for char in ["=", "(", ")", "#", "[", "]"]):
            print(f"Attempting to resolve name '{user_input}' to SMILES...")
            try:
                results = pcp.get_compounds(user_input, "name")
                if results and results[0].isomeric_smiles:
                    user_input = results[0].isomeric_smiles
                    print(f"Resolved to: {user_input}")
                else:
                    print("Could not resolve name to SMILES. Proceeding with raw input.")
            except Exception as exc:
                print(f"Name resolution failed: {exc}. Proceeding with raw input.")

        print(f"Scouting {user_input}...")

        try:
            result = agent.scout_synthesis(user_input)

            if result.get("status") == "error":
                print("Error(s):")
                for err in result.get("errors", []):
                    print(f"- {err}")
                continue

            print("\nDATA RETRIEVED:")
            print(json.dumps(result, indent=2))

            ranked_routes = evaluate_chemtrace_output(result)

            print("\n========================================")
            print("DECISION ENGINE OUTPUT")
            print("========================================")
            print(json.dumps(ranked_routes, indent=2))

            if ranked_routes:
                best_route = ranked_routes[0]
                print("\n========================================")
                print("BEST ROUTE SUMMARY")
                print("========================================")
                print(f"Route ID: {best_route['route_id']}")
                print(f"Score: {best_route['score']}")
                print(f"Status: {best_route['status']}")
                print(f"Estimated Cost per Gram: {best_route['cost_per_gram']}")
                print(f"Supply Chain Risk: {best_route['supply_chain_risk']}")
                print(f"Regulatory Risk: {best_route['regulatory_risk']}")
                print(f"Step Count: {best_route['step_count']}")
                print(f"Yield Estimate: {best_route['yield_estimate']}")
                print(f"Reason: {best_route['decision_reason']}")

        except Exception as exc:
            print(f"Critical failure: {exc}")


if __name__ == "__main__":
    main()