import re

MATH_PATTERNS = [
    r"\b(solve|calculate|compute|evaluate|simplify|derive|prove|integrate|differentiate)\b",
    r"\b(equation|formula|integral|derivative|matrix|determinant|limit|sum|product)\b",
    r"\b(algebra|calculus|geometry|trigonometry|probability|statistics|logarithm)\b",
    r"\b(step[\s-]?by[\s-]?step|show\s+work|find\s+x|find\s+y)\b",
    r"[0-9]+\s*[\+\-\*/^=]\s*[0-9]",
    r"\$[^$]+\$",  # inline latex-ish
    r"\b(sin|cos|tan|log|ln|sqrt|exp)\s*[\(\[]",
    r"\^[\{]?[0-9]",
    r"∫|∑|√|π|≤|≥|≠|±",
]


def is_math_question(question: str) -> bool:
    q = question.lower()
    for pattern in MATH_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE):
            return True
    return False


def extract_math_terms(question: str) -> list[str]:
    """Terms useful for keyword retrieval alongside vector search."""
    terms: set[str] = set()
    for word in re.findall(r"[a-zA-Z]{3,}", question):
        if word.lower() not in {"the", "and", "for", "what", "how", "this", "that", "from", "with"}:
            terms.add(word)
    for num in re.findall(r"\b\d+(?:\.\d+)?\b", question):
        terms.add(num)
    return list(terms)[:8]
