"""Rotation abbreviation mappings and common/uncommon classification."""

# Abbreviation -> Full name mapping
ROTATION_ABBREVS: dict[str, str] = {
    "ACS": "Acute Care Surgery",
    "CRS": "Colorectal Surgery",
    "HPB": "Hepatopancreatobiliary Surgery",
    "SICU": "Surgical Intensive Care Unit",
    "CTICU": "Cardiothoracic Intensive Care Unit",
    "SONC": "Surgical Oncology",
    "ZE": "Zollinger Elective",
    "Mel Sarc": "Melanoma / Sarcoma",
    "MelSarc": "Melanoma / Sarcoma",
    "ACS/MelSarc": "ACS / Melanoma Sarcoma",
    "ACS/Mel Sarc": "ACS / Melanoma Sarcoma",
    "Mel Sarc / Endo": "Melanoma Sarcoma / Endoscopy",
    "Float": "Float",
    "FLOAT": "Float",
    "Burn": "Burn",
    "Thoracic": "Thoracic Surgery",
    "Cardiac": "Cardiac Surgery",
    "Transplant": "Transplant Surgery",
    "Vascular": "Vascular Surgery",
    "Vascular - UH": "Vascular Surgery - University Hospital",
    "Vascular - East": "Vascular Surgery - East",
    "Vascular Lab": "Vascular Lab",
    "East Vascular": "East Vascular",
    "East Gen Surg": "East General Surgery",
    "East GS": "East General Surgery",
    "East": "East",
    "Ped Surg": "Pediatric Surgery",
    "Pediatric": "Pediatric Surgery",
    "Peds Surg": "Pediatric Surgery",
    "Peds": "Pediatric Surgery",
    "Breast": "Breast Surgery",
    "Endoscopy": "Endoscopy",
    "Endo": "Endoscopy",
    "Elective": "Elective",
    "OUTPATIENT": "Outpatient",
    "Outpatient": "Outpatient",
    "Surg Onc": "Surgical Oncology",
    "MC East": "Mount Carmel East",
    "MIS": "Minimally Invasive Surgery",
    "Echo": "Echocardiography",
    "Rural": "Rural Surgery",
    "Jeopardy": "Jeopardy",
    "Hand": "Hand Surgery",
    "ENT": "ENT",
    "Foregut": "Foregut Surgery",
    "Plastics": "Plastic Surgery",
    "PLASTICS": "Plastic Surgery",
    "Hernia": "Hernia Surgery",
    "Crit Care": "Critical Care",
    "Global": "Global Surgery",
    "UROLOGY": "Urology",
    "Urology": "Urology",
    "ORTHO": "Orthopedics",
    "Ortho": "Orthopedics",
    "ORTHO-AWAY": "Orthopedics (Away)",
    "NSGY": "Neurosurgery",
    "IR": "Interventional Radiology",
    "PROCEDURE": "Procedure",
    "Procedure": "Procedure",
    "CVICU": "Cardiovascular ICU",
    "CT Surgery": "CT Surgery",
    "CT Anesthesia": "CT Anesthesia",
    "CT - ICU": "CT ICU",
    "CT-ICU": "CT ICU",
    "Endoscopy CRC": "Endoscopy",
    "General": "General Surgery",
    "General Surgery": "General Surgery",
    "SONC - HPB": "Surgical Oncology / HPB",
    "SONC-HPB": "Surgical Oncology / HPB",
    "SONC/HPB": "Surgical Oncology / HPB",
    "SONC-Breast": "Surgical Oncology - Breast",
    "SONC-Mel/Sarc": "Surgical Oncology - Melanoma/Sarcoma",
    "VASCULAR": "Vascular Surgery",
    "Cardiac/CVICU": "Cardiac Surgery / Cardiovascular ICU",
    "VACATION": "Vacation",
    "Vacation / Coverage": "Vacation / Coverage",
}

# Compound rotation names that should NOT be split on "/"
COMPOUND_ROTATIONS: set[str] = {
    "SONC/HPB",
    "SONC-HPB",
    "SONC - HPB",
    "SONC-Breast",
    "SONC-Mel/Sarc",
    "Mel Sarc / Endo",
    "Mel Sarc/Endo",
    "Vacation / Coverage",
    "Vascular - UH",
    "Vascular - East",
    "East Gen Surg",
    "Ped Surg",
    "Surg Onc",
    "Mel Sarc",
    "Crit Care",
    "Peds Surg",
    "MC East",
    "East GS",
    "Cardiac/CVICU",
    "CT - ICU",
    "CT-ICU",
}

# Common rotations (sort first in picker UI)
COMMON_ROTATIONS: set[str] = {
    "Acute Care Surgery",
    "Surgical Intensive Care Unit",
    "Zollinger Elective",
    "Colorectal Surgery",
    "Hepatopancreatobiliary Surgery",
    "Thoracic Surgery",
    "Transplant Surgery",
    "Vascular Surgery",
    "Vascular Surgery - University Hospital",
    "Float",
    "Burn",
    "Pediatric Surgery",
    "Breast Surgery",
    "Endoscopy",
    "Surgical Oncology",
    "Melanoma / Sarcoma",
    "Cardiac Surgery",
    "Cardiothoracic Intensive Care Unit",
    "East General Surgery",
    "East Vascular",
}

# Known visiting institutions
KNOWN_INSTITUTIONS: set[str] = {
    "Doctors",
    "Doctors Hospital",
    "Mount Carmel",
    "Mt. Carmel",
    "Riverside",
    "Kettering",
    "Parkview",
}


def expand_rotation(abbrev: str) -> str:
    """Expand a rotation abbreviation to its full name.

    Returns the abbreviation itself if no mapping exists.
    Tries case-insensitive match as fallback.
    """
    cleaned = abbrev.strip()
    if cleaned in ROTATION_ABBREVS:
        return ROTATION_ABBREVS[cleaned]

    # Case-insensitive fallback
    cleaned_lower = cleaned.lower()
    for key, value in ROTATION_ABBREVS.items():
        if key.lower() == cleaned_lower:
            return value

    return cleaned


def is_common_rotation(full_name: str) -> bool:
    """Check if a rotation full name is considered common."""
    return full_name in COMMON_ROTATIONS
