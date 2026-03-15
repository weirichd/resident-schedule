"""Parse individual rotation cells for vacations, splits, locations, and visiting info."""

import re
from dataclasses import dataclass, field

import pandas as pd

from app.parser.rotation_map import (
    COMPOUND_ROTATIONS,
    canonicalize_rotation,
    expand_rotation,
)

# Vacation patterns
# Matches: "Vac: 12/8-12/14", "[Vac: 10/27-11/2]", "Vac: 8/11-8/17 (A)"
VAC_PATTERN = re.compile(
    r"\[?\s*Vac(?:ation)?[:/]\s*(\d{1,2}/\d{1,2})\s*-\s*(\d{1,2}/\d{1,2})\s*\]?"
    r"(?:\s*\(([AP])\))?",
    re.IGNORECASE,
)

# Conference pattern
CONF_PATTERN = re.compile(
    r"\[?\s*Conf[:/]\s*(\d{1,2}/\d{1,2})\s*-\s*(\d{1,2}/\d{1,2})\s*\]?"
    r"(?:\s*\(([AP])\))?",
    re.IGNORECASE,
)

# Combined Vac/Conf pattern
VAC_CONF_PATTERN = re.compile(
    r"Vac/Conf[:/]\s*(\d{1,2}/\d{1,2})\s*-\s*(\d{1,2}/\d{1,2})\s*\(([AP])\)",
    re.IGNORECASE,
)

# Coverage pattern: "A. Powell to cover", "Name to cover"
COVERAGE_PATTERN = re.compile(r"([A-Z][.\w]+(?:\s\w+)?)\s+to\s+cover", re.IGNORECASE)

# Approval pattern standalone: (A), (P), *PENDING*
APPROVAL_PATTERN = re.compile(r"\(([AP])\)")

# Date-range specifics within rotation cells: "SICU 10.20-11.9"
DATE_SPEC_PATTERN = re.compile(r"(\d{1,2})[./](\d{1,2})\s*-+\s*(\d{1,2})[./](\d{1,2})")

# Visiting resident patterns
# "Name - Institution", "Name (Institution)", "Name, DO - Institution"
VISITING_DASH = re.compile(
    r"^(.+?)\s*[-–]\s*(Doctors\s*Hospital|Doctors|Mount\s*Carmel|"
    r"Mt\.?\s*Carmel|Riverside|Kettering|Parkview|EM/IM)$",
    re.IGNORECASE,
)
VISITING_PAREN = re.compile(
    r"^(.+?)\s*\(\s*(Doctors|Mount\s*Carmel|Mt\.?\s*Carmel|"
    r"Riverside|Kettering|Parkview)\s*\)$",
    re.IGNORECASE,
)

# Section header visiting context
VISITING_SECTION_PATTERN = re.compile(
    r"(DOCTORS|MOUNT\s*CARMEL|MT\.?\s*CARMEL|RIVERSIDE|KETTERING|PARKVIEW)",
    re.IGNORECASE,
)

# Known specialty tracks appended/prepended to resident names
# e.g., "Jeffrey Song - Urology", "Vascular - Drayson Campbell"
SPECIALTY_TRACKS: set[str] = {
    "Anesthesia",
    "CT",
    "EM/IM",
    "Family Medicine",
    "NSGY",
    "OMFS",
    "Ortho",
    "Plastics",
    "Podiatry",
    "Prelim",
    "Urology",
    "Vascular",
}


@dataclass
class VacationInfo:
    vac_start: str  # "M/D" format
    vac_end: str  # "M/D" format
    vac_type: str = "vacation"  # "vacation" or "conference"


@dataclass
class ParsedCell:
    """Result of parsing a single rotation cell."""

    rotation: str  # cleaned rotation abbreviation
    rotation_full: str  # expanded full name
    location: str | None = None  # "East" or None
    vacations: list[VacationInfo] = field(default_factory=list)
    is_full_vacation: bool = False  # True if cell is just "VACATION"


@dataclass
class VisitingInfo:
    """Parsed visiting resident info."""

    name: str
    institution: str
    is_visiting: bool = True


def parse_visiting_name(raw_name: str) -> VisitingInfo | None:
    """Parse a visiting resident name.

    Returns VisitingInfo if the name indicates a visiting resident, None otherwise.
    """
    name = raw_name.strip()

    # "Name, DO - Institution" or "Name - Institution"
    m = VISITING_DASH.match(name)
    if m:
        return VisitingInfo(
            name=m.group(1).strip().rstrip(",").strip(),
            institution=_normalize_institution(m.group(2)),
        )

    # "Name (Institution)"
    m = VISITING_PAREN.match(name)
    if m:
        return VisitingInfo(
            name=m.group(1).strip(),
            institution=_normalize_institution(m.group(2)),
        )

    # "Doctors Rotator- Name" (old format)
    if "Rotator" in name:
        parts = re.split(r"Rotator\s*[-–]\s*", name, maxsplit=1)
        if len(parts) == 2:
            institution = parts[0].strip()
            resident_name = parts[1].strip()
            return VisitingInfo(
                name=resident_name,
                institution=_normalize_institution(institution),
            )

    return None


def clean_resident_name(raw_name: str) -> str:
    """Strip specialty track prefixes/suffixes from resident names.

    e.g., "Jeffrey Song - Urology" → "Jeffrey Song",
          "Vascular - Drayson Campbell" → "Drayson Campbell".
    Only strips known specialty tracks, not visiting institution names.
    """
    name = raw_name.strip()

    # "Name - Track" pattern (most common)
    if " - " in name:
        parts = name.rsplit(" - ", maxsplit=1)
        suffix = parts[1].strip()
        if suffix in SPECIALTY_TRACKS:
            return parts[0].strip()

    # "Track - Name" pattern (rare: "Vascular - Drayson Campbell")
    if " - " in name:
        parts = name.split(" - ", maxsplit=1)
        prefix = parts[0].strip()
        if prefix in SPECIALTY_TRACKS:
            return parts[1].strip()

    # "Name -Track" or "Name- Track" with irregular spacing
    m = re.match(r"^(.+?)\s*[-–]\s*(.+)$", name)
    if m:
        left, right = m.group(1).strip(), m.group(2).strip()
        if right in SPECIALTY_TRACKS:
            return left
        if left in SPECIALTY_TRACKS:
            return right

    return name


def _normalize_institution(raw: str) -> str:
    """Normalize institution name."""
    raw = raw.strip()
    lower = raw.lower()
    if "doctor" in lower:
        return "Doctors Hospital"
    if "carmel" in lower:
        return "Mount Carmel"
    if "riverside" in lower:
        return "Riverside"
    if "kettering" in lower:
        return "Kettering"
    if "parkview" in lower:
        return "Parkview"
    return raw


def _extract_vacations(text: str) -> list[VacationInfo]:
    """Extract all vacation/conference annotations from a cell text."""
    vacations = []

    # Vac/Conf combined
    for m in VAC_CONF_PATTERN.finditer(text):
        vacations.append(
            VacationInfo(
                vac_start=m.group(1),
                vac_end=m.group(2),
                vac_type="vacation",
            )
        )

    # Standalone vacations (avoid re-matching combined ones)
    for m in VAC_PATTERN.finditer(text):
        vac = VacationInfo(
            vac_start=m.group(1),
            vac_end=m.group(2),
            vac_type="vacation",
        )
        # Avoid duplicates from Vac/Conf
        if not any(
            v.vac_start == vac.vac_start and v.vac_end == vac.vac_end for v in vacations
        ):
            vacations.append(vac)

    # Conferences
    for m in CONF_PATTERN.finditer(text):
        conf = VacationInfo(
            vac_start=m.group(1),
            vac_end=m.group(2),
            vac_type="conference",
        )
        if not any(
            v.vac_start == conf.vac_start and v.vac_end == conf.vac_end
            for v in vacations
        ):
            vacations.append(conf)

    return vacations


def _strip_annotations(text: str) -> str:
    """Remove vacation/conference annotations and bracketed content from cell text."""
    # Remove Vac/Conf patterns
    result = VAC_CONF_PATTERN.sub("", text)
    result = VAC_PATTERN.sub("", result)
    result = CONF_PATTERN.sub("", result)

    # Remove approval markers
    result = APPROVAL_PATTERN.sub("", result)

    # Remove bracketed content that's not rotation info
    result = re.sub(r"\[.*?\]", "", result)

    # Remove orphaned annotations before stray ] (vac/conf consumed the opening [)
    result = re.sub(r"\s[^[\]]+\]", "", result)

    # Remove {Vac: ...} typo (treat like [Vac:])
    result = re.sub(r"\{Vac:.*?\}", "", result, flags=re.IGNORECASE)

    # Remove coverage text
    result = COVERAGE_PATTERN.sub("", result)

    # Remove *PENDING* markers
    result = re.sub(r"\*PENDING\*", "", result)

    # Remove "**text**" and "**text" spanning to end of string
    result = re.sub(r"\*\*[^*]+\*\*", "", result)
    result = re.sub(r"\*\*.*$", "", result)

    # Remove semicolons and everything after (coverage/note text)
    result = re.sub(r"\s*;.*$", "", result)

    # Remove parenthetical notes: dates, annotations like (-clinical), (wknd request), ()
    result = re.sub(r"\([^)]*\)", "", result)

    # Remove remaining stray brackets and braces
    result = re.sub(r"[\[\]{}]", "", result)

    # Remove question marks (never part of valid rotation names)
    result = result.replace("?", "")

    # Remove stray asterisks (e.g., "Elective*"); meaningful ** patterns already handled above
    result = result.replace("*", "")

    # Clean up
    result = re.sub(r"\s+", " ", result).strip()
    result = result.strip(" /;,-&")
    return result


def _parse_location(rotation: str) -> tuple[str, str | None]:
    """Parse "East" or "UH" location from rotation name.

    Returns (cleaned_rotation, location).
    """
    rot = rotation.strip()

    # "East - ACS", "East - General" with dash separator (check BEFORE "East X")
    if rot.startswith("East - "):
        remainder = rot[7:].strip()
        return remainder, "East"

    # "East Vascular", "East GS" — established names, keep "East" as part of name
    if rot.startswith("East "):
        remainder = rot[5:].strip()
        if remainder in ("Vascular", "GS", "Gen Surg"):
            return rot, "East"
        # Other "East X" — decompose to rotation=X, location=East
        return remainder, "East"

    # "Vascular - UH" → rotation="Vascular", location="UH" (check BEFORE " UH")
    if rot.endswith(" - UH"):
        return rot[:-5].strip(), "UH"
    # "Vascular UH" → rotation="Vascular", location="UH"
    if rot.endswith(" UH"):
        return rot[:-3].strip(), "UH"

    return rot, None


def parse_rotation_cell(
    cell_value, block_start: str = "", block_end: str = ""
) -> list[ParsedCell]:
    """Parse a single rotation cell value.

    Returns a list of ParsedCell (usually 1, but can be 2 for "/" split rotations).
    """
    if pd.isna(cell_value):
        return []

    text = str(cell_value).strip()
    if not text:
        return []

    # Full vacation cell
    if text.upper() == "VACATION":
        return [
            ParsedCell(
                rotation="VACATION",
                rotation_full="Vacation",
                is_full_vacation=True,
            )
        ]

    # Extract vacations before stripping
    vacations = _extract_vacations(text)

    # Strip annotations to get clean rotation name
    clean = _strip_annotations(text)
    if not clean:
        # Cell was only annotations (e.g., just vacation info)
        # This might be a vacation-only cell
        if vacations:
            return [
                ParsedCell(
                    rotation="VACATION",
                    rotation_full="Vacation",
                    vacations=vacations,
                    is_full_vacation=True,
                )
            ]
        return []

    # Handle date-specific sub-rotations like "SICU 10.20-11.9 / Cardiac 11.10-12.7"
    # or "Thoracic 8.25--9.21/SICU"
    # For now, just strip the date specs and treat as compound
    clean = DATE_SPEC_PATTERN.sub("", clean).strip()
    clean = re.sub(r"\s+", " ", clean).strip(" /&")

    # Strip month suffixes: "SICU -Aug", "SICU - Feb" → "SICU"
    clean = re.sub(
        r"\s*-\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    clean = clean.strip()

    # Parse location
    rotation, location = _parse_location(clean)

    # Canonicalize before compound check
    rotation = canonicalize_rotation(rotation)

    # Check if this is a compound rotation that shouldn't be split
    if _is_compound(rotation):
        full = expand_rotation(rotation)
        return [
            ParsedCell(
                rotation=rotation,
                rotation_full=full,
                location=location,
                vacations=vacations,
            )
        ]

    # Try to split on "/" for split rotations
    # e.g., "ACS/Float", "Breast/Elective", "SICU/Rural/SICU"
    if "/" in rotation and not _is_compound(rotation):
        parts = [p.strip() for p in rotation.split("/") if p.strip()]
        if len(parts) >= 2:
            results = []
            for i, part in enumerate(parts):
                part_rot, part_loc = _parse_location(part)
                part_rot = canonicalize_rotation(part_rot)
                full = expand_rotation(part_rot)
                # Distribute vacations to first part only
                part_vacs = vacations if i == 0 else []
                results.append(
                    ParsedCell(
                        rotation=part_rot,
                        rotation_full=full,
                        location=part_loc or location,
                        vacations=part_vacs,
                    )
                )
            return results

    # Single rotation
    full = expand_rotation(rotation)
    return [
        ParsedCell(
            rotation=rotation,
            rotation_full=full,
            location=location,
            vacations=vacations,
        )
    ]


def _is_compound(rotation: str) -> bool:
    """Check if a rotation name is a known compound (should not be split on /)."""
    if rotation in COMPOUND_ROTATIONS:
        return True
    # Also check without spaces around /
    normalized = rotation.replace(" / ", "/").replace("/ ", "/").replace(" /", "/")
    return normalized in COMPOUND_ROTATIONS or rotation in COMPOUND_ROTATIONS


def parse_vacation_annotation_row(
    row: pd.Series, rotation_start_col: int
) -> dict[int, list[VacationInfo]]:
    """Parse a vacation annotation row.

    Returns dict mapping column index to list of VacationInfo.
    """
    result: dict[int, list[VacationInfo]] = {}
    for col_idx in range(rotation_start_col, len(row)):
        val = row.get(col_idx)
        if pd.notna(val):
            text = str(val).strip()
            if text:
                vacations = _extract_vacations(text)
                if vacations:
                    result[col_idx] = vacations
    return result
