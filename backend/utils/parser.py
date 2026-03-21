from typing import Any


def _safe_round(value: Any, precision: int = 2) -> float:
    try:
        return round(float(value), precision)
    except (TypeError, ValueError):
        return 0.0


def _top_gap_skills(gap_data: dict, category: str, limit: int = 8) -> list[dict]:
    skills: list[dict] = []
    for skill, details in gap_data.items():
        if skill.startswith("__") or not isinstance(details, dict):
            continue
        if details.get("category") != category:
            continue
        skills.append(
            {
                "name": skill,
                "gapScore": _safe_round(details.get("gap_score", 0)),
                "resumeScore": _safe_round(details.get("resume_score", 0)),
                "jdScore": _safe_round(details.get("jd_score", 0)),
                "level": details.get("level", "Unknown"),
                "action": details.get("action", "N/A"),
                "status": details.get("status", "unknown"),
            }
        )
    skills.sort(key=lambda item: item["gapScore"], reverse=True)
    return skills[:limit]


def _resume_skills(resume_skill_data: dict, category: str, limit: int = 12) -> list[dict]:
    skills: list[dict] = []
    for skill, details in resume_skill_data.items():
        if skill.startswith("__") or not isinstance(details, dict):
            continue
        if details.get("category") != category:
            continue
        skills.append(
            {
                "name": skill,
                "score": _safe_round(details.get("resulting_score", 0)),
                "confidence": _safe_round(details.get("confidence", 0)),
                "taxonomy": details.get("taxonomy_category", "General"),
            }
        )
    skills.sort(key=lambda item: item["score"], reverse=True)
    return skills[:limit]


def build_structured_response(
    filename: str,
    gap_data: dict,
    mapping_data: dict,
    roadmap_data: dict,
    resources_data: dict,
    resume_skill_data: dict,
) -> dict:
    top_roles = mapping_data.get("top_roles", [])[:3]
    best_fit = top_roles[0] if top_roles else {}
    jd_resources = resources_data.get("jd_requirement_resources", {})
    resource_items = jd_resources.get("items", [])[:8]

    critical_gaps = []
    for skill, details in gap_data.items():
        if skill.startswith("__") or not isinstance(details, dict):
            continue
        if details.get("action") == "top priority":
            critical_gaps.append(
                {
                    "name": skill,
                    "gapScore": _safe_round(details.get("gap_score", 0)),
                    "category": details.get("category", "unknown"),
                }
            )
    critical_gaps.sort(key=lambda item: item["gapScore"], reverse=True)
    jd_roadmap = roadmap_data.get("jd_requirement_roadmap", {})
    jd_graph = jd_roadmap.get("graph", roadmap_data.get("graph", {}))

    return {
        "fileName": filename,
        "overview": {
            "bestFitRole": best_fit.get("role", roadmap_data.get("candidate_best_fit_role", "N/A")),
            "bestFitScore": _safe_round(best_fit.get("score", 0)),
            "targetRole": roadmap_data.get("target_jd_role", "N/A"),
            "nextSteps": jd_resources.get("next_steps", roadmap_data.get("next_steps", [])),
        },
        "skills": {
            "hard": _top_gap_skills(gap_data, category="hard_skill"),
            "soft": _top_gap_skills(gap_data, category="soft_skill"),
            "resumeHard": _resume_skills(resume_skill_data, category="hard_skill"),
            "resumeSoft": _resume_skills(resume_skill_data, category="soft_skill"),
        },
        "insights": {
            "criticalGaps": critical_gaps[:8],
            "recommendedRoles": [
                {
                    "role": role.get("role", "Unknown"),
                    "score": _safe_round(role.get("score", 0)),
                    "reason": role.get("reason", ""),
                    "missingCoreSkills": role.get("missing_core_skills", []),
                }
                for role in top_roles
            ],
            "roadmap": [
                {
                    "skill": item.get("skill", "Unknown"),
                    "phase": item.get("phase", "Unassigned"),
                    "priority": _safe_round(item.get("priority", 0)),
                    "reason": item.get("reason", ""),
                    "resources": [resource.get("title", "") for resource in item.get("resources", [])],
                }
                for item in resource_items
            ],
            "roadmapGraph": {
                "nodes": [
                    {
                        "id": node.get("id", ""),
                        "label": node.get("data", {}).get("label", node.get("id", "")),
                        "status": node.get("data", {}).get("status", "unknown"),
                        "color": node.get("data", {}).get("color", "gray"),
                    }
                    for node in jd_graph.get("nodes", [])
                ],
                "edges": [
                    {
                        "source": edge.get("source", ""),
                        "target": edge.get("target", ""),
                        "weight": _safe_round(edge.get("weight", 1)),
                    }
                    for edge in jd_graph.get("edges", [])
                ],
                "meta": jd_graph.get("meta", {}),
                "title": jd_roadmap.get("title", roadmap_data.get("target_jd_role", "JD Roadmap Graph")),
            },
        },
        "rawReferences": {
            "roadmapTitle": jd_resources.get("title", "Roadmap"),
            "professionTrackCount": len(resources_data.get("profession_resources", [])),
        },
    }
