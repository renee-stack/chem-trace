"""PubChem service utilities for molecular metadata lookup.

This module validates SMILES with RDKit and fetches compound metadata from
PubChem through pubchempy. The returned payload is a JSON-serializable
dictionary intended to be consumed as a data contract by downstream agents.
"""

from typing import Any, Dict, List

import pubchempy as pcp
from rdkit import Chem


def _extract_synonyms(cid: int, limit: int = 20) -> List[str]:
    """Fetch and normalize PubChem synonyms for a compound CID."""
    try:
        synonym_entries = pcp.get_synonyms(cid)
    except Exception:
        return []

    if not synonym_entries:
        return []

    raw_synonyms = synonym_entries[0].get("Synonym", [])
    return raw_synonyms[:limit]


def get_molecule_info(smiles: str) -> Dict[str, Any]:
    """Validate SMILES and fetch molecular metadata from PubChem.

    Args:
        smiles: Input SMILES string.

    Returns:
        JSON-serializable dictionary:
        - status: "success" or "error"
        - input_smiles: Original input value
        - molecule: Molecular metadata on success, otherwise None
        - errors: List of error messages
    """
    payload: Dict[str, Any] = {
        "status": "error",
        "input_smiles": smiles,
        "molecule": None,
        "errors": [],
    }

    if not isinstance(smiles, str) or not smiles.strip():
        payload["errors"].append("SMILES must be a non-empty string.")
        return payload

    normalized_smiles = smiles.strip()
    mol = Chem.MolFromSmiles(normalized_smiles)
    if mol is None:
        payload["errors"].append("Invalid SMILES string (RDKit validation failed).")
        return payload

    canonical_smiles = Chem.MolToSmiles(mol, canonical=True)

    try:
        compounds = pcp.get_compounds(normalized_smiles, namespace="smiles")
    except Exception as exc:
        payload["errors"].append(f"PubChem query failed: {exc}")
        return payload

    if not compounds:
        payload["errors"].append("No PubChem compound found for provided SMILES.")
        return payload

    compound = compounds[0]
    synonyms = _extract_synonyms(compound.cid)

    payload["status"] = "success"
    payload["molecule"] = {
        "cid": compound.cid,
        "smiles": normalized_smiles,
        "canonical_smiles": canonical_smiles,
        "iupac_name": compound.iupac_name,
        "molecular_weight": compound.molecular_weight,
        "synonyms": synonyms,
        "xlogp": compound.xlogp,
    }
    return payload
