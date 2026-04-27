SYNONYMS = {
    'mi': 'myocardial infarction',
    'heart attack': 'myocardial infarction',
    'hf': 'heart failure',
    'chf': 'heart failure',
    't2dm': 'type 2 diabetes',
    'diabetes mellitus type 2': 'type 2 diabetes',
    'breast ca': 'breast cancer',
    'cva': 'stroke',
    'aki': 'acute kidney injury',
    'ckd': 'chronic kidney disease',
    'mci': 'mild cognitive impairment',
}


def normalize_term(term: str) -> str:
    value = (term or '').strip().lower()
    return SYNONYMS.get(value, value)


def normalize_terms(terms: list[str]) -> set[str]:
    return {normalize_term(t) for t in terms if t}
