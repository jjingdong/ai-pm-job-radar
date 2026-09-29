"""The rule Jev has to beat: title regexes, the way most job alerts work.

Deliberately a fair baseline, not a straw man: include PM titles, exclude the known
lookalikes (product marketing, product design, program management, and so on).
"""
import re

PM = re.compile(r"\bproduct manager\b|\bproduct management\b|\bproduct lead\b|\bproduct owner\b"
                r"|\bhead of product\b|\bgroup pm\b|\bgpm\b|\bpm\b", re.I)
ADJACENT = re.compile(r"\bproduct (marketing|design|designer|operations|ops|analyst|analytics|counsel|"
                      r"sales|support|specialist)\b|\bprogram manager\b|\bproject manager\b"
                      r"|\bfinance\b|\baccount (executive|manager)\b", re.I)
AI = re.compile(r"\bai\b|\bml\b|\bllm\b|machine learning|\bmodel(s)?\b|\bagent(s|ic)?\b|\bgenai\b"
                r"|\binference\b|\bresearch\b|\bevals?\b", re.I)


def role(title):
    if ADJACENT.search(title):
        return "adjacent"
    return "pm" if PM.search(title) else "not_pm"


def ai_focus(title):
    return "ai_product" if AI.search(title) else "not_ai"


def classify(posting):
    return {"role": role(posting["title"]), "ai_focus": ai_focus(posting["title"])}
