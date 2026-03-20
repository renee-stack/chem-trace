import os
import sys

# Ensure the project root is in the path.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.chemistry_agent import ChemistryAgent
from src.utils.pubchem_service import get_molecule_info


def test_aspirin_flow():
    print("Testing Aspirin (hardcoded demo path)...")
    aspirin_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    agent = ChemistryAgent()
    result = agent.scout_synthesis(aspirin_smiles)

    assert result["status"] == "success"
    assert result["molecule_info"]["status"] == "success"
    assert result["molecule_info"]["molecule"]["iupac_name"] is not None
    assert result["route_plan"]["route_type"] == "hardcoded_demo"
    assert len(result["route_plan"]["steps"]) > 0
    assert len(result["route_plan"]["reagents"]) > 0
    print("Aspirin flow passed.")


def test_invalid_smiles():
    print("Testing invalid SMILES handling...")
    invalid_smiles = "NOT_A_MOLECULE"
    info = get_molecule_info(invalid_smiles)

    assert info["status"] == "error"
    assert len(info["errors"]) > 0
    print("Error handling passed.")


def test_pubchem_connection():
    print("Testing live PubChem fetch (caffeine)...")
    caffeine_smiles = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
    info = get_molecule_info(caffeine_smiles)

    assert info["status"] == "success"
    assert info["molecule"]["cid"] == 2519

    synonyms = [s.lower() for s in info["molecule"]["synonyms"]]
    assert "caffeine" in synonyms
    print("PubChem connection passed.")


if __name__ == "__main__":
    try:
        test_aspirin_flow()
        test_invalid_smiles()
        test_pubchem_connection()
        print("\nALL SYSTEMS GO. Person C is ready for integration.")
    except AssertionError:
        print("\nTEST FAILED. Check your logic.")
        raise
