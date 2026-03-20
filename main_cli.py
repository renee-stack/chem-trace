"""Interactive CLI for the ChemTrace chemistry scouting agent."""

import json
import os
import sys

# Add project root for src imports when run from repository root.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

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

        print(f"Scouting {user_input}...")

        try:
            result = agent.scout_synthesis(user_input)
            if result.get("status") == "error":
                print("Error(s):")
                for err in result.get("errors", []):
                    print(f"- {err}")
            else:
                print("\nDATA RETRIEVED:")
                print(json.dumps(result, indent=2))
        except Exception as exc:
            print(f"Critical failure: {exc}")


if __name__ == "__main__":
    main()
