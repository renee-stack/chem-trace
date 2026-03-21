"""2D molecule visualization utilities for UI rendering."""

import os
from typing import Tuple

from rdkit import Chem
from rdkit.Chem import Draw, rdDepictor


def generate_molecule_image(smiles: str, output_path: str = "static/molecules/temp.png") -> Tuple[bool, str]:
    """Convert a SMILES string into a 2D PNG image.

    Args:
        smiles: Input SMILES string.
        output_path: Target PNG path.

    Returns:
        (True, output_path) on success, or (False, error_message) on failure.
    """
    try:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False, "Invalid SMILES string"

        rdDepictor.Compute2DCoords(mol)

        # Crisp, high-contrast output suitable for dashboards.
        img = Draw.MolToImage(
            mol,
            size=(300, 300),
            kekulize=True,
            fitImage=True,
        )
        img.save(output_path)
        return True, output_path
    except Exception as exc:
        return False, str(exc)


if __name__ == "__main__":
    ok, result = generate_molecule_image("CC(=O)OC1=CC=CC=C1C(=O)O", "test_aspirin.png")
    if ok:
        print(f"Success! Image saved to {result}")
    else:
        print(f"Error: {result}")
