"""Attack-category taxonomy normalization.

Maps folder-name / LLM-output spellings of the 13 attack categories onto the
canonical title-case labels used by the validator and the analysis tooling.
"""

from __future__ import annotations

# folder-name / LLM-output spelling -> canonical validator label
_CATEGORY_MAP = {
    "information gathering": "Information Gathering",
    "information_gathering": "Information Gathering",
    "privilege escalation": "Privilege Escalation",
    "privilege_escalation": "Privilege Escalation",
    "persistence control": "Persistence Control",
    "persistence_control": "Persistence Control",
    "data exfiltration": "Data Exfiltration",
    "data_exfiltration": "Data Exfiltration",
    "disruption interference": "Disruption & Interference",
    "disruption_interference": "Disruption & Interference",
    "disruption & interference": "Disruption & Interference",
    "supply chain attack": "Supply Chain Attack",
    "supply_chain_attack": "Supply Chain Attack",
    "configuration weakening": "Configuration Weakening",
    "configuration_weakening": "Configuration Weakening",
    "data integrity risks": "Data Integrity Risks",
    "data_integrity_risks": "Data Integrity Risks",
    "code quality degradation": "Code Quality Degradation",
    "code_quality_degradation": "Code Quality Degradation",
    "advertising injection": "Advertising Injection",
    "advertising_injection": "Advertising Injection",
    "brand hijacking": "Brand Hijacking",
    "brand_hijacking": "Brand Hijacking",
    "false attribution": "False Attribution",
    "false_attribution": "False Attribution",
    "over-engineering": "Over-engineering",
    "over engineering": "Over-engineering",
    "over_engineering": "Over-engineering",
}


def normalize_attack_category(raw: str | None) -> str:
    """Normalize an attack-category string to a validator-accepted label."""
    if not raw or raw.upper() == "NONE":
        return "NONE"
    return _CATEGORY_MAP.get(raw.lower(), raw.title())
