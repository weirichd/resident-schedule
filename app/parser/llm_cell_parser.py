"""LLM-powered cell parser for rotation schedule cells.

Uses Anthropic API (claude-haiku-4-5) as primary backend, with ollama fallback
when no API key is set.
"""

import json
import logging
import os
from typing import Any

import httpx

from app.parser.cell_parser import ParsedCell, VacationInfo, parse_rotation_cell
from app.parser.rotation_map import ROTATION_ABBREVS, expand_rotation

logger = logging.getLogger(__name__)

# Default models
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Build rotation abbreviation context for the LLM prompt
_ABBREV_LINES = [f"  {k} = {v}" for k, v in ROTATION_ABBREVS.items()]
ROTATION_CONTEXT = "\n".join(_ABBREV_LINES)

SYSTEM_PROMPT = f"""\
You are an expert parser for surgical residency rotation schedules at \
The Ohio State University (OSU) Wexner Medical Center.

Your task is to parse rotation cell values from an Excel schedule \
and return structured JSON data.

## Domain context

These are surgical residency rotation schedules. Each cell contains \
a rotation abbreviation, sometimes with annotations.

### Known rotation abbreviations:
{ROTATION_CONTEXT}

### Rules:
1. "/" means a split rotation (two rotations sharing one time block, \
each gets half the time), UNLESS it is a known compound like \
"SONC/HPB", "Cardiac/CVICU", "Mel Sarc / Endo", "Vacation / Coverage".
2. "East" and "UH" are hospital locations. "East" at the start means \
location=East. "UH" at the end means location=UH.
   - "East Vascular", "East GS", "East Gen Surg" are established names \
where "East" is part of the rotation name AND the location is "East".
3. Vacation annotations look like: "[Vac: 8/16-8/17]", \
"Vac: 8/16-8/17 (A)", "Conf: 10/1-10/5 (P)"
   - (A) = approved, (P) = pending
   - Type is "vacation" for Vac and "conference" for Conf
4. "VACATION" as the full cell value means is_full_vacation=true
5. Ignore garbage: trailing brackets, asterisks, semicolons followed \
by notes, "*PENDING*", coverage notes like "Name to cover"
6. If the cell is empty or NaN, return an empty list.
7. Return the rotation abbreviation as-is (cleaned of annotations). \
Map it to a full_name using the abbreviation table above. If not \
in the table, use the abbreviation as both abbreviation and full_name.

## Output format

Return a JSON array. Each element corresponds to one input cell \
(by index). Each element is an object:
```json
{{
  "rotations": [
    {{
      "abbreviation": "SICU",
      "full_name": "Surgical Intensive Care Unit",
      "location": null
    }}
  ],
  "vacations": [
    {{
      "start": "8/16",
      "end": "8/17",
      "type": "vacation",
      "approved": "A"
    }}
  ],
  "is_full_vacation": false
}}
```

For split rotations (e.g., "ACS/Float"), return two entries in \
the "rotations" array.

IMPORTANT: Return ONLY the JSON array, no markdown fences, no \
explanation. The array must have exactly one element per input cell, \
in order."""


def _build_user_prompt(cells: list[tuple[int, str]]) -> str:
    """Build the user prompt with numbered cells to parse."""
    lines = ["Parse these rotation cells:\n"]
    for idx, (cell_id, cell_value) in enumerate(cells):
        lines.append(f"{idx + 1}. [{cell_id}] \"{cell_value}\"")
    lines.append(
        f"\nReturn a JSON array with exactly {len(cells)} elements, "
        "one per cell above, in order."
    )
    return "\n".join(lines)


def _call_anthropic(
    user_prompt: str,
    model: str = DEFAULT_ANTHROPIC_MODEL,
) -> str:
    """Call Anthropic API and return the response text."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def _call_ollama(
    user_prompt: str,
    model: str = DEFAULT_OLLAMA_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> str:
    """Call ollama REST API and return the response text."""
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["message"]["content"]


def _parse_llm_response(
    raw: str, num_cells: int
) -> list[dict[str, Any]] | None:
    """Parse the LLM JSON response.

    Returns a list of parsed cell dicts, or None if parsing fails.
    """
    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove opening fence
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON: %s", text[:200])
        return None

    if isinstance(parsed, dict):
        # Some models wrap the array in a dict like {"result": [...]}
        # Try to find a list value inside
        list_values = [v for v in parsed.values() if isinstance(v, list)]
        if len(list_values) == 1:
            parsed = list_values[0]
        elif "rotations" in parsed:
            # Model returned a single cell result dict instead of an array
            # Wrap it as a one-element array
            parsed = [parsed]
        else:
            logger.warning(
                "LLM response is a dict with no single list value: %s",
                list(parsed.keys()),
            )
            return None

    if not isinstance(parsed, list):
        logger.warning("LLM response is not a list: %s", type(parsed))
        return None

    if len(parsed) != num_cells:
        logger.warning(
            "LLM returned %d results for %d cells",
            len(parsed),
            num_cells,
        )
        # Still usable if we got at least some
        if len(parsed) < num_cells:
            # Pad with None
            parsed.extend([None] * (num_cells - len(parsed)))
        else:
            parsed = parsed[:num_cells]

    return parsed


def _convert_llm_result(result: dict[str, Any] | None) -> list[ParsedCell]:
    """Convert a single LLM result dict to a list of ParsedCell objects."""
    if result is None:
        return []

    rotations_data = result.get("rotations", [])
    vacations_data = result.get("vacations", [])
    is_full_vacation = result.get("is_full_vacation", False)

    # Build vacation list
    vacations: list[VacationInfo] = []
    for vac in vacations_data:
        vac_type = vac.get("type", "vacation")
        if vac_type not in ("vacation", "conference"):
            vac_type = "vacation"
        vacations.append(
            VacationInfo(
                vac_start=vac.get("start", ""),
                vac_end=vac.get("end", ""),
                vac_type=vac_type,
                approved_status=vac.get("approved"),
            )
        )

    if is_full_vacation and not rotations_data:
        return [
            ParsedCell(
                rotation="VACATION",
                rotation_full="Vacation",
                vacations=vacations,
                is_full_vacation=True,
            )
        ]

    cells: list[ParsedCell] = []
    for i, rot in enumerate(rotations_data):
        abbrev = rot.get("abbreviation", "")
        full_name = rot.get("full_name", "")

        if not abbrev:
            continue

        # Use our own expansion if LLM full_name seems wrong or missing
        if not full_name or full_name == abbrev:
            full_name = expand_rotation(abbrev)

        location = rot.get("location")
        if location and location.lower() not in ("east", "uh"):
            location = None

        # Attach vacations to first rotation only
        cell_vacs = vacations if i == 0 else []

        cells.append(
            ParsedCell(
                rotation=abbrev,
                rotation_full=full_name,
                location=location,
                vacations=cell_vacs,
                is_full_vacation=is_full_vacation,
            )
        )

    return cells


def parse_rotation_cells_llm_batch(
    cells: list[tuple[int, str]],
    model: str | None = None,
    use_ollama: bool = False,
    ollama_model: str | None = None,
) -> dict[int, list[ParsedCell]]:
    """Parse a batch of rotation cells using the LLM.

    Args:
        cells: List of (cell_id, cell_value) tuples.
        model: Anthropic model name override.
        use_ollama: If True, use ollama instead of Anthropic.
        ollama_model: Ollama model name override.

    Returns:
        Dict mapping cell_id to list[ParsedCell].
        Falls back to rules-based parser for cells where LLM fails.
    """
    if not cells:
        return {}

    # Filter out empty/NaN cells
    valid_cells = [
        (cid, val) for cid, val in cells if val and str(val).strip()
    ]
    if not valid_cells:
        return {}

    user_prompt = _build_user_prompt(valid_cells)

    try:
        if use_ollama:
            raw_response = _call_ollama(
                user_prompt,
                model=ollama_model or DEFAULT_OLLAMA_MODEL,
            )
        else:
            raw_response = _call_anthropic(
                user_prompt,
                model=model or DEFAULT_ANTHROPIC_MODEL,
            )
    except Exception as e:
        logger.error("LLM call failed: %s. Falling back to rules-based.", e)
        return _fallback_all(valid_cells)

    parsed_results = _parse_llm_response(raw_response, len(valid_cells))
    if parsed_results is None:
        logger.warning("Could not parse LLM response. Falling back.")
        return _fallback_all(valid_cells)

    # Convert each result
    results: dict[int, list[ParsedCell]] = {}
    for i, (cell_id, cell_value) in enumerate(valid_cells):
        result = parsed_results[i]
        try:
            parsed_cells = _convert_llm_result(result)
            if parsed_cells:
                results[cell_id] = parsed_cells
            else:
                # LLM returned empty — try rules-based fallback
                fallback = parse_rotation_cell(cell_value)
                if fallback:
                    results[cell_id] = fallback
        except Exception as e:
            logger.warning(
                "Failed to convert LLM result for cell %d: %s. "
                "Falling back to rules-based.",
                cell_id,
                e,
            )
            fallback = parse_rotation_cell(cell_value)
            if fallback:
                results[cell_id] = fallback

    return results


def _fallback_all(
    cells: list[tuple[int, str]],
) -> dict[int, list[ParsedCell]]:
    """Fall back to rules-based parser for all cells."""
    results: dict[int, list[ParsedCell]] = {}
    for cell_id, cell_value in cells:
        parsed = parse_rotation_cell(cell_value)
        if parsed:
            results[cell_id] = parsed
    return results


def parse_rotation_cell_llm(
    cell_value: str,
    block_start: str = "",
    block_end: str = "",
    model: str | None = None,
    use_ollama: bool = False,
    ollama_model: str | None = None,
) -> list[ParsedCell]:
    """Parse a single rotation cell using the LLM.

    This is the single-cell interface matching parse_rotation_cell().
    For efficiency, prefer parse_rotation_cells_llm_batch().

    Returns list[ParsedCell] (same interface as cell_parser.parse_rotation_cell).
    """
    if not cell_value or not str(cell_value).strip():
        return []

    result = parse_rotation_cells_llm_batch(
        [(0, str(cell_value))],
        model=model,
        use_ollama=use_ollama,
        ollama_model=ollama_model,
    )
    return result.get(0, [])


def get_backend_info() -> dict[str, str]:
    """Return info about which LLM backend will be used."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return {
            "backend": "anthropic",
            "model": DEFAULT_ANTHROPIC_MODEL,
        }
    return {
        "backend": "ollama",
        "model": DEFAULT_OLLAMA_MODEL,
        "url": DEFAULT_OLLAMA_URL,
    }
