"""
Build a plain-text representation of a candidate for the human's future semantic step.

This module is deliberately NOT used by the rule-based scorer — it is the extension
seam described in §2 of the brief. The human can pass the blob to an encoder and
inject the resulting score via score.py's `semantic` parameter.
"""


def build_candidate_text(candidate: dict) -> str:
    """Return a single string summarising the candidate for embedding / LLM use.

    Concatenates: headline, summary, career descriptions, skill names, education.
    No scoring logic lives here.
    """
    parts = []

    profile = candidate.get("profile", {})
    if profile.get("headline"):
        parts.append(profile["headline"])
    if profile.get("summary"):
        parts.append(profile["summary"])

    for job in candidate.get("career_history", []):
        title = job.get("title", "")
        company = job.get("company", "")
        desc = job.get("description", "")
        if title or company:
            parts.append(f"{title} at {company}".strip(" at "))
        if desc:
            parts.append(desc)

    skill_names = [s["name"] for s in candidate.get("skills", []) if s.get("name")]
    if skill_names:
        parts.append("Skills: " + ", ".join(skill_names))

    for edu in candidate.get("education", []):
        deg = edu.get("degree", "")
        field = edu.get("field_of_study", "")
        inst = edu.get("institution", "")
        if deg or inst:
            parts.append(f"{deg} in {field} from {inst}".strip(" in from "))

    return "\n".join(parts)
