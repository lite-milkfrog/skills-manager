from __future__ import annotations

import re

_INTENT_ALIASES = {
    "网页设计": ("web", "design", "webpage", "website", "frontend", "ui"),
    "网页开发": ("web", "development", "webpage", "website", "frontend", "browser"),
    "写作研究": ("writing", "research", "content"),
    "投资研究": ("investment", "research", "finance", "stock"),
    "学习流程": ("learning", "study", "workflow", "education"),
}


def normalized_search_terms(query: str) -> list[str]:
    raw = query.casefold()
    terms = [term.casefold() for term in re.findall(r"[\w.-]+", query) if term.strip()]
    for phrase, aliases in _INTENT_ALIASES.items():
        if phrase in raw:
            terms.extend(aliases)
    return list(dict.fromkeys(terms))
