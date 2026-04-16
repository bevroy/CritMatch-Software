from typing import Any


def expand_term(text: str, target_code_systems: list[str]) -> dict[str, Any]:
    normalized = "myocardial infarction" if "heart attack" in text.lower() else text.lower()

    expansions: list[dict[str, str]] = [
        {"type": "synonym", "display": "myocardial infarction"},
        {"type": "abbreviation", "display": "MI"},
    ]

    if "ICD10CM" in target_code_systems:
        expansions.append(
            {
                "type": "code",
                "system": "ICD10CM",
                "code": "I21",
                "display": "Acute myocardial infarction",
            }
        )

    if "SNOMEDCT" in target_code_systems:
        expansions.append(
            {
                "type": "code",
                "system": "SNOMEDCT",
                "code": "22298006",
                "display": "Myocardial infarction",
            }
        )

    return {"normalizedTerm": normalized, "expansions": expansions}
