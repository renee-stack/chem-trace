"""PubChem service utilities for molecular metadata lookup.

This module validates SMILES with RDKit and fetches compound metadata from
PubChem through pubchempy. The returned payload is a JSON-serializable
dictionary intended to be consumed as a data contract by downstream agents.
"""

from typing import Any, Dict, List, Optional

import pubchempy as pcp
from rdkit import Chem
from rdkit.Chem import Descriptors, inchi

from src.utils.rdkit_smiles import mol_from_smiles_lenient


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


def _try_get_compounds(
    identifier: str,
    namespace: str,
    searchtype: Optional[str] = None,
) -> List[Any]:
    """Call pubchempy.get_compounds; return [] on failure (never raise)."""
    try:
        kwargs: Dict[str, Any] = {"namespace": namespace}
        if searchtype is not None:
            kwargs["searchtype"] = searchtype
        return pcp.get_compounds(identifier, **kwargs)
    except Exception:
        return []


def _resolve_compounds_from_pubchem(mol: Any, normalized_smiles: str, canonical_smiles: str) -> List[Any]:
    """Try multiple PubChem strategies; identity alone can HTTP 400 on some SMILES."""
    # 1) Default SMILES lookup (most reliable for PubChem PUG REST).
    for smi in (canonical_smiles, normalized_smiles):
        found = _try_get_compounds(smi, "smiles")
        if found:
            return found

    # 2) Identity search (more forgiving for equivalent forms; may 400 on edge cases).
    for smi in (canonical_smiles, normalized_smiles):
        found = _try_get_compounds(smi, "smiles", searchtype="identity")
        if found:
            return found

    # 3) InChIKey — structure-based, avoids fragile SMILES URL/identity quirks.
    try:
        inchi_key = inchi.MolToInchiKey(mol)
        if inchi_key:
            found = _try_get_compounds(inchi_key, "inchikey")
            if found:
                return found
    except Exception:
        pass

    return []


def get_molecule_info(smiles: str) -> Dict[str, Any]:
    """Validate SMILES and fetch molecular metadata from PubChem.

    Args:
        smiles: Input SMILES string.

    Returns:
        JSON-serializable dictionary:
        - status: "success", "success_inferred", or "error"
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
    mol, parse_err = mol_from_smiles_lenient(normalized_smiles)
    if mol is None:
        payload["errors"].append(parse_err or "Invalid SMILES string (RDKit validation failed).")
        return payload

    canonical_smiles = Chem.MolToSmiles(mol, canonical=True)

    compounds = _resolve_compounds_from_pubchem(mol, normalized_smiles, canonical_smiles)

    if not compounds:
        payload["status"] = "success_inferred"
        payload["molecule"] = {
            "cid": "NOVEL_COMPOUND",
            "smiles": normalized_smiles,
            "canonical_smiles": canonical_smiles,
            "iupac_name": None,
            "molecular_weight": round(float(Descriptors.MolWt(mol)), 4),
            "synonyms": [],
            "xlogp": round(float(Descriptors.MolLogP(mol)), 4),
        }
        payload["errors"].append(
            "No PubChem match found; returned inferred RDKit descriptors."
        )
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
