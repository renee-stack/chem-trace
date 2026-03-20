"""Chemistry agent for synthesis scouting data contracts."""

import json
import os
from typing import Any, Dict, List

from rdkit import Chem

from src.utils.pubchem_service import get_molecule_info


class ChemistryAgent:
    """Provides molecule scouting payloads for the orchestration pipeline.

    Person A (Orchestrator) should call this first.
    Person B (Decision Engine) can consume `synonyms` and route `reagents`
    for downstream cost/risk analysis.
    """

    ASPIRIN_SMILES = "CC(=O)OC1=CC=CC=C1C(=O)O"

    def get_retrosynthesis_prompt(self, smiles: str, chem_data: Dict[str, Any]) -> str:
        """Build a chemistry-focused prompt for LLM-based route generation."""
        return f"""
    You are an expert Medicinal Chemist.
    Target Molecule: {chem_data['name']}
    SMILES: {smiles}
    Molecular Weight: {chem_data['weight']}

    Task: Propose a viable 3-step synthetic route starting from commercially available precursors.

    Rules:
    1. Each step must include: Reaction Name, Reagents, Estimated Yield (0.0 to 1.0), and a plausible Literature Citation.
    2. Ensure all intermediates are chemically valid.
    3. Output ONLY a JSON array of steps.

    JSON Format:
    [
      {{
        "step": 1,
        "reaction": "Name",
        "reagents": ["Reagent 1", "Reagent 2"],
        "yield": 0.85,
        "citation": "Journal Name, Year"
      }}
    ]
    """

    def generate_route_with_llm(self, smiles: str, chem_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a route with Anthropic/OpenAI and return a data-contract JSON object."""
        prompt = self.get_retrosynthesis_prompt(smiles, chem_data)

        # Prefer Anthropic when API key exists, otherwise try OpenAI.
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        raw_text = ""
        provider = ""
        model = ""

        try:
            if anthropic_key:
                from anthropic import Anthropic  # type: ignore

                client = Anthropic(api_key=anthropic_key)
                model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
                completion = client.messages.create(
                    model=model,
                    max_tokens=1400,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                provider = "anthropic"
                raw_text = "".join(
                    block.text for block in completion.content if getattr(block, "type", "") == "text"
                ).strip()
            elif openai_key:
                from openai import OpenAI  # type: ignore

                client = OpenAI(api_key=openai_key)
                model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                completion = client.chat.completions.create(
                    model=model,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "Return only JSON."},
                        {"role": "user", "content": prompt},
                    ],
                )
                provider = "openai"
                raw_text = completion.choices[0].message.content or ""
            else:
                return {
                    "status": "error",
                    "provider": None,
                    "model": None,
                    "steps": [],
                    "errors": ["No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY."],
                }
        except Exception as exc:
            return {
                "status": "error",
                "provider": provider or None,
                "model": model or None,
                "steps": [],
                "errors": [f"LLM request failed: {exc}"],
            }

        parsed_steps: List[Dict[str, Any]]
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                if "steps" in parsed and isinstance(parsed["steps"], list):
                    parsed_steps = parsed["steps"]
                else:
                    return {
                        "status": "error",
                        "provider": provider,
                        "model": model,
                        "steps": [],
                        "errors": ["LLM JSON does not contain a valid 'steps' array."],
                    }
            elif isinstance(parsed, list):
                parsed_steps = parsed
            else:
                return {
                    "status": "error",
                    "provider": provider,
                    "model": model,
                    "steps": [],
                    "errors": ["LLM output JSON must be an array of steps or object with 'steps'."],
                }
        except Exception as exc:
            return {
                "status": "error",
                "provider": provider,
                "model": model,
                "steps": [],
                "errors": [f"Failed to parse LLM JSON output: {exc}"],
            }

        return {
            "status": "success",
            "provider": provider,
            "model": model,
            "steps": parsed_steps,
            "errors": [],
        }

    def scout_synthesis(self, smiles: str) -> Dict[str, Any]:
        """Return synthesis scouting JSON for a target SMILES.

        Args:
            smiles: Input SMILES string.

        Returns:
            JSON-serializable data contract containing:
            - request metadata
            - molecular profile from PubChem
            - synthesis route scaffold
        """
        response: Dict[str, Any] = {
            "status": "error",
            "input_smiles": smiles,
            "molecule_info": None,
            "route_plan": None,
            "errors": [],
        }

        if not isinstance(smiles, str) or not smiles.strip():
            response["errors"].append("SMILES must be a non-empty string.")
            return response

        input_smiles = smiles.strip()
        mol = Chem.MolFromSmiles(input_smiles)
        if mol is None:
            response["errors"].append("Invalid SMILES string (RDKit validation failed).")
            return response

        molecule_info = get_molecule_info(input_smiles)
        response["molecule_info"] = molecule_info
        if molecule_info["status"] != "success":
            response["errors"].extend(molecule_info.get("errors", []))
            return response

        if input_smiles == self.ASPIRIN_SMILES:
            route_plan = self._aspirin_route()
        else:
            chem_data = {
                "name": molecule_info["molecule"].get("iupac_name") or "UNKNOWN_TARGET",
                "weight": molecule_info["molecule"].get("molecular_weight"),
            }
            llm_route = self.generate_route_with_llm(input_smiles, chem_data)
            if llm_route["status"] == "success":
                steps = llm_route["steps"]
                reagents = sorted(
                    {
                        reagent
                        for step in steps
                        if isinstance(step, dict)
                        for reagent in step.get("reagents", [])
                        if isinstance(reagent, str)
                    }
                )
                route_plan = {
                    "route_type": "llm_generated",
                    "target_name": chem_data["name"],
                    "target_smiles": input_smiles,
                    "reagents": reagents,
                    "steps": steps,
                    "llm_metadata": {
                        "provider": llm_route["provider"],
                        "model": llm_route["model"],
                    },
                }
            else:
                response["errors"].extend(llm_route.get("errors", []))
                route_plan = self._template_route(input_smiles)
                route_plan["route_type"] = "template_fallback"

        response["status"] = "success"
        response["route_plan"] = route_plan
        return response

    def _aspirin_route(self) -> Dict[str, Any]:
        """Return a hardcoded two-step synthesis route for Aspirin."""
        steps: List[Dict[str, Any]] = [
            {
                "step_number": 1,
                "reaction_type": "Acetylation",
                "description": "Acetylate salicylic acid using acetic anhydride.",
                "reagents": [
                    "Salicylic acid",
                    "Acetic anhydride",
                    "Catalytic sulfuric acid",
                ],
                "conditions": {
                    "temperature_c": "50-70",
                    "time_h": "0.5-1.5",
                    "solvent": "None or glacial acetic acid",
                },
                "expected_intermediate_or_product": "Acetylsalicylic acid (Aspirin crude)",
                "literature_links": [
                    "https://pubchem.ncbi.nlm.nih.gov/compound/Aspirin",
                ],
            },
            {
                "step_number": 2,
                "reaction_type": "Workup and Recrystallization",
                "description": "Quench, isolate crude product, and recrystallize for purification.",
                "reagents": ["Water", "Ethanol (recrystallization grade)"],
                "conditions": {
                    "temperature_c": "0-25",
                    "time_h": "1-2",
                    "solvent": "Ethanol/Water",
                },
                "expected_intermediate_or_product": "Purified Aspirin",
                "literature_links": [
                    "https://en.wikipedia.org/wiki/Aspirin",
                ],
            },
        ]
        return {
            "route_type": "hardcoded_demo",
            "target_name": "Aspirin",
            "reagents": sorted({r for step in steps for r in step["reagents"]}),
            "steps": steps,
        }

    def _template_route(self, smiles: str) -> Dict[str, Any]:
        """Return a generic route template with placeholders."""
        return {
            "route_type": "template",
            "target_name": "UNKNOWN_TARGET",
            "target_smiles": smiles,
            "reagents": [
                "<reagent_1>",
                "<reagent_2>",
            ],
            "steps": [
                {
                    "step_number": 1,
                    "reaction_type": "<reaction_type>",
                    "description": "<step_description>",
                    "reagents": ["<reagent_1>", "<reagent_2>"],
                    "conditions": {
                        "temperature_c": "<temp_range>",
                        "time_h": "<duration>",
                        "solvent": "<solvent>",
                    },
                    "expected_intermediate_or_product": "<intermediate_or_product>",
                    "literature_links": [
                        "<doi_or_patent_or_url>",
                    ],
                },
                {
                    "step_number": 2,
                    "reaction_type": "<reaction_type>",
                    "description": "<step_description>",
                    "reagents": ["<reagent_3>", "<reagent_4>"],
                    "conditions": {
                        "temperature_c": "<temp_range>",
                        "time_h": "<duration>",
                        "solvent": "<solvent>",
                    },
                    "expected_intermediate_or_product": "<intermediate_or_product>",
                    "literature_links": [
                        "<doi_or_patent_or_url>",
                    ],
                },
            ],
        }
