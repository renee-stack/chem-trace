"""Lenient RDKit SMILES parsing for database-style / edge-case strings."""

from typing import Any, Optional, Tuple

from rdkit import Chem

# SanitizeFlags location varies slightly across RDKit builds.
try:
    _SAN_ALL = Chem.SanitizeFlags.SANITIZE_ALL
    _SAN_KEK = Chem.SanitizeFlags.SANITIZE_KEKULIZE
except AttributeError:  # pragma: no cover
    from rdkit.Chem import rdmolops

    _SAN_ALL = rdmolops.SanitizeFlags.SANITIZE_ALL
    _SAN_KEK = rdmolops.SanitizeFlags.SANITIZE_KEKULIZE


def mol_from_smiles_lenient(smiles: str) -> Tuple[Optional[Any], Optional[str]]:
    """Parse SMILES with RDKit.

    Uses default sanitization first. If that fails (e.g. kekulization errors on
    some aromatic representations), parses with ``sanitize=False`` and
    sanitizes with kekulization skipped — a common fix for ChEMBL/DrugBank-style
    SMILES that are still valid for search and InChI.

    Returns:
        (mol, None) on success, or (None, error_message) on failure.
    """
    if not isinstance(smiles, str) or not smiles.strip():
        return None, "SMILES must be a non-empty string."

    s = smiles.strip()
    mol = Chem.MolFromSmiles(s)
    if mol is not None:
        return mol, None

    mol = Chem.MolFromSmiles(s, sanitize=False)
    if mol is None:
        return None, "Invalid SMILES string (RDKit cannot build a molecular graph)."

    try:
        Chem.SanitizeMol(mol, sanitizeOps=_SAN_ALL ^ _SAN_KEK)
        return mol, None
    except Exception as exc:
        return None, (
            "SMILES parsed but failed RDKit sanitization (tried without kekulization). "
            f"Detail: {exc}"
        )
