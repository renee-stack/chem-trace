"""Chemistry agent for synthesis scouting data contracts."""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from rdkit import Chem

from src.utils.pubchem_service import get_molecule_info
from src.utils.rdkit_smiles import mol_from_smiles_lenient

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


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
    3. Output ONLY a JSON array of steps (raw JSON). Do not use markdown, code fences, or any text before or after the array.

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

    @staticmethod
    def _coerce_parsed_to_steps(parsed: Any) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Normalize parsed JSON into a list of step dicts."""
        if isinstance(parsed, list):
            return parsed, None
        if isinstance(parsed, dict):
            if "steps" in parsed and isinstance(parsed["steps"], list):
                return parsed["steps"], None
            return None, "LLM JSON object does not contain a 'steps' array."
        return None, "LLM output must be a JSON array or an object with 'steps'."

    @classmethod
    def _parse_llm_route_json(cls, raw_text: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Parse model output: strip fences, then JSON array or object with steps."""
        text = (raw_text or "").strip()
        if not text:
            return None, "LLM returned empty response."

        fence = re.search(r"```(?:json)?\s*\n?(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()

        def try_load(s: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
            try:
                parsed = json.loads(s)
            except json.JSONDecodeError as exc:
                return None, str(exc)
            steps, err = cls._coerce_parsed_to_steps(parsed)
            if err:
                return None, err
            return steps, None

        steps, err = try_load(text)
        if steps is not None:
            return steps, None

        # Bracket-scan: first top-level JSON array
        start = text.find("[")
        if start != -1:
            depth = 0
            for i in range(start, len(text)):
                ch = text[i]
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        snippet = text[start : i + 1]
                        steps2, err2 = try_load(snippet)
                        if steps2 is not None:
                            return steps2, None
                        break

        # Brace-scan: object that may contain "steps"
        start_o = text.find("{")
        if start_o != -1:
            depth = 0
            for i in range(start_o, len(text)):
                ch = text[i]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        snippet = text[start_o : i + 1]
                        steps3, err3 = try_load(snippet)
                        if steps3 is not None:
                            return steps3, None
                        break

        preview = text[:240].replace("\n", " ")
        return None, f"Failed to parse LLM JSON ({err or 'no valid array/object'}). Preview: {preview!r}"

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
                # `claude-3-5-sonnet-latest` and similar aliases often 404 on the current API.
                # Override with ANTHROPIC_MODEL in .env (see Anthropic docs for IDs).
                preferred = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
                fallback_models = ["claude-sonnet-4-6", "claude-haiku-4-5", "claude-opus-4-6"]
                candidates: List[str] = []
                for m in [preferred, *fallback_models]:
                    if m and m not in candidates:
                        candidates.append(m)

                last_exc: Optional[Exception] = None
                completion = None
                for candidate in candidates:
                    try:
                        completion = client.messages.create(
                            model=candidate,
                            max_tokens=1400,
                            temperature=0.2,
                            system=(
                                "You output only valid JSON: a single JSON array of route steps, "
                                "or a JSON object with a 'steps' key. No markdown or code fences."
                            ),
                            messages=[{"role": "user", "content": prompt}],
                        )
                        model = candidate
                        break
                    except Exception as exc:  # pragma: no cover - network/API
                        err_s = str(exc).lower()
                        if "404" in str(exc) or "not_found" in err_s:
                            last_exc = exc
                            continue
                        raise

                if completion is None:
                    return {
                        "status": "error",
                        "provider": "anthropic",
                        "model": preferred,
                        "steps": [],
                        "errors": [
                            "Anthropic model not found (404). Set ANTHROPIC_MODEL to a valid ID "
                            f"(e.g. claude-sonnet-4-6). Last error: {last_exc}"
                        ],
                    }

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
                        {
                            "role": "system",
                            "content": (
                                "Return only JSON: either a JSON object with key 'steps' (array of steps) "
                                "or a raw JSON array. No markdown or code fences."
                            ),
                        },
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

        parsed_steps, parse_err = self._parse_llm_route_json(raw_text)
        if parse_err or parsed_steps is None:
            return {
                "status": "error",
                "provider": provider,
                "model": model,
                "steps": [],
                "errors": [parse_err or "Failed to parse LLM JSON output."],
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
        mol, parse_err = mol_from_smiles_lenient(input_smiles)
        if mol is None:
            response["errors"].append(
                parse_err or "Invalid SMILES string (RDKit validation failed)."
            )
            return response

        molecule_info = get_molecule_info(input_smiles)
        response["molecule_info"] = molecule_info
        if molecule_info["status"] not in {"success", "partial", "success_inferred"}:
            response["errors"].extend(molecule_info.get("errors", []))
            return response

        if input_smiles == self.ASPIRIN_SMILES:
            route_plan = self._aspirin_route()
        else:
            mol_blob = molecule_info.get("molecule") or {}
            synonyms = mol_blob.get("synonyms") or []
            first_syn = synonyms[0] if synonyms else None
            chem_data = {
                "name": mol_blob.get("iupac_name") or first_syn or "UNKNOWN_TARGET",
                "weight": mol_blob.get("molecular_weight"),
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
                route_plan["target_name"] = chem_data["name"]

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
