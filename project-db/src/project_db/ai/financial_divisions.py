"""Controlled division vocabulary (CSI MasterFormat, residential subset).

The single fixed axis the financial redesign reconciles on: every revenue and
cost amount maps to exactly ONE division, so "Plumbing" (client quote),
"plomberie" (sub invoice), and a Home-Depot PEX run all collapse to `22`.

Deterministic + fail-safe (never crash): classification prefers an explicit
MasterFormat code/hint carried by the source sheet, then bilingual (EN/FR --
this is Quebec) keyword matching, then `99 Unclassified`. No LLM. See
docs/FINANCIAL_REDESIGN.md §2.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _strip_accents(s: str) -> str:
    """Fold diacritics so accented Quebec-French descriptions match the
    unaccented aliases below ('béton' -> 'beton', 'fenêtre' -> 'fenetre').
    No-op for already-ASCII text, so English matching is unchanged."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Division:
    code: str  # canonical division code, e.g. "09" or "10-12"
    name: str
    aliases: tuple[str, ...]  # lowercase EN/FR keywords; matched as whole words


# Order matters: more specific trades BEFORE broad ones (first match wins), so
# "plumbing fixture" -> 22 not 10-12. General-requirements terms are specific
# enough (overhead/contingency/supervision) not to over-match.
DIVISIONS: tuple[Division, ...] = (
    Division(
        "01",
        "General Requirements",
        (
            "general requirements",
            "overhead",
            "profit",
            "o&p",
            "ohp",
            "contingency",
            "contingence",
            "supervision",
            "site supervision",
            "delivery",
            "livraison",
            "mobilization",
            "permit",
            "permis",
            "frais generaux",
            "administration",
            "general conditions",
        ),
    ),
    Division(
        "02",
        "Demolition",
        (
            "demolition",
            "demo",
            "teardown",
            "removal",
            "remove",
            "enlevement",
            "stripping",
            "gutting",
        ),
    ),
    Division(
        "03",
        "Concrete",
        (
            "concrete",
            "beton",
            "foundation",
            "fondation",
            "slab",
            "dalle",
            "footing",
            "semelle",
        ),
    ),
    Division(
        "05",
        "Structural",
        (
            "structural",
            "structure",
            "steel",
            "acier",
            "beam",
            "poutre",
            "load-bearing",
            "load bearing",
            "lintel",
            "linteau",
            "column",
            "colonne",
            "joist",
            "solive",
        ),
    ),
    Division(
        "22",
        "Plumbing",
        (
            "plumbing",
            "plomberie",
            "plumber",
            "plombier",
            "rough-in plumbing",
            "pex",
            "drain",
            "sink",
            "evier",
            "toilet",
            "toilette",
            "shower",
            "douche",
            "faucet",
            "robinet",
            "water heater",
            "chauffe-eau",
            "sanitary",
            "sanitaire",
        ),
    ),
    Division(
        "23",
        "HVAC / Mechanical",
        (
            "hvac",
            "mechanical",
            "mecanique",
            "heating",
            "chauffage",
            "ventilation",
            "air conditioning",
            "climatisation",
            "thermopump",
            "thermopompe",
            "heat pump",
            "ductwork",
            "conduit",
            "furnace",
            "fournaise",
            "hrv",
            "vrc",
            "semi-split",
            "mini-split",
        ),
    ),
    Division(
        "26",
        "Electrical",
        (
            "electrical",
            "electrique",
            "electricite",
            "electrician",
            "electricien",
            "wiring",
            "cablage",
            "lighting",
            "eclairage",
            "outlet",
            "prise",
            "panel",
            "panneau",
            "breaker",
            "disjoncteur",
        ),
    ),
    Division(
        "08",
        "Openings (Doors/Windows)",
        (
            "opening",
            "door",
            "doors",
            "porte",
            "portes",
            "window",
            "windows",
            "fenetre",
            "fenetres",
            "glazing",
            "vitrage",
            "skylight",
            "puits de lumiere",
        ),
    ),
    Division(
        "07",
        "Roofing / Insulation / Moisture",
        (
            "roof",
            "roofing",
            "toiture",
            "insulation",
            "isolation",
            "waterproofing",
            "impermeabilisation",
            "membrane",
            "thermal",
            "vapor barrier",
            "pare-vapeur",
            "soffit",
            "fascia",
        ),
    ),
    Division(
        "06",
        "Carpentry / Millwork",
        (
            "carpentry",
            "charpenterie",
            "menuiserie",
            "millwork",
            "framing",
            "ossature",
            "wood",
            "bois",
            "trim",
            "moulding",
            "moulure",
            "baseboard",
            "plinthe",
        ),
    ),
    Division(
        "09",
        "Finishes",
        (
            "finishes",
            "finitions",
            "drywall",
            "gypse",
            "gypsum",
            "plaster",
            "platre",
            "flooring",
            "plancher",
            "floor",
            "tile",
            "tuile",
            "carrelage",
            "paint",
            "painting",
            "peinture",
            "grout",
            "coulis",
            "ceiling",
            "plafond",
            "membrane/ waterproofing",
        ),
    ),
    Division(
        "10-12",
        "Fixtures / Hardware / Casework",
        (
            "fixture",
            "fixtures",
            "hardware",
            "quincaillerie",
            "cabinetry",
            "cabinet",
            "armoire",
            "casework",
            "countertop",
            "comptoir",
            "vanity",
            "vanite",
            "specialty",
            "specialties",
            "furnishing",
            "appliance",
            "electromenager",
            "accessory",
            "accessoire",
        ),
    ),
    Division(
        "31-32",
        "Site / Landscape / Earthwork",
        (
            "landscape",
            "landscaping",
            "paysager",
            "excavation",
            "earthwork",
            "terrassement",
            "grading",
            "paving",
            "pavage",
            "asphalt",
            "asphalte",
            "sidewalk",
            "trottoir",
            "drainage",
            "site work",
        ),
    ),
)

UNCLASSIFIED = Division("99", "Unclassified", ())

# code -> Division, including range members so a hint of "10"/"11"/"12" -> 10-12.
_CODE_LOOKUP: dict[str, Division] = {}
for _d in DIVISIONS:
    _CODE_LOOKUP[_d.code] = _d
    if "-" in _d.code:
        lo, hi = _d.code.split("-")
        for _n in range(int(lo), int(hi) + 1):
            _CODE_LOOKUP[f"{_n:02d}"] = _d
_CODE_LOOKUP[UNCLASSIFIED.code] = UNCLASSIFIED

# All divisions including the catch-all, for validation/lookup.
ALL_DIVISION_CODES: frozenset[str] = frozenset([d.code for d in DIVISIONS] + [UNCLASSIFIED.code])

# Precompiled whole-word alias matchers, in DIVISIONS order.  A trailing "s" is
# optional so a singular alias also matches its plural ('tuile' -> 'tuiles',
# 'door' -> 'doors') -- the alias list was inconsistent about listing plurals,
# which silently dropped French plurals like 'tuiles'/'fenetres' to div 99.
_ALIAS_PATTERNS: list[tuple[Division, re.Pattern[str]]] = []
for _d in DIVISIONS:
    if _d.aliases:
        _pat = re.compile(
            r"\b(" + "|".join(re.escape(a) for a in _d.aliases) + r")s?\b", re.IGNORECASE
        )
        _ALIAS_PATTERNS.append((_d, _pat))


def _code_from_hint(hint: str) -> str | None:
    """Pull a CSI division code out of a MasterFormat hint like 'Division 22',
    '22 00 00', '230000', or '09 - Finishes'."""
    if not hint:
        return None
    # First two digits of a digit run: "Division 22" / "22 00 00" / "230000"
    # -> "22"/"23"; tolerates the concatenated 6-digit MasterFormat form.
    m = re.search(r"\b(\d{2})\d*\b", hint)
    if not m:
        return None
    return m.group(1)


def division_by_code(code: str | None) -> Division:
    """Resolve a (possibly range-member) code to its Division, else Unclassified."""
    if not code:
        return UNCLASSIFIED
    return _CODE_LOOKUP.get(code.strip(), UNCLASSIFIED)


def classify_division(text: str | None, *, masterformat_hint: str | None = None) -> Division:
    """Map a line description (and optional sheet MasterFormat hint) to exactly
    one Division. Hint wins (explicit code, then its keywords); else the
    description's keywords; else `99 Unclassified`. Never raises."""
    if masterformat_hint:
        code = _code_from_hint(masterformat_hint)
        if code and code in _CODE_LOOKUP:
            return _CODE_LOOKUP[code]
        hinted = _keyword_match(masterformat_hint)
        if hinted is not None:
            return hinted
    matched = _keyword_match(text or "")
    return matched if matched is not None else UNCLASSIFIED


def _keyword_match(text: str) -> Division | None:
    if not text:
        return None
    folded = _strip_accents(text)
    for division, pattern in _ALIAS_PATTERNS:
        if pattern.search(folded):
            return division
    return None
