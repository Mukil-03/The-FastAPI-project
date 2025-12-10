from __future__ import annotations

import re
from typing import Any, Dict, List

from app.engine.core import NodeResult, ToolRegistry


def _extract_functions_from_code(code: str) -> List[str]:
    pattern = r"def\\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    return re.findall(pattern, code)


def extract_functions(state: Dict[str, Any], tools: ToolRegistry) -> NodeResult:
    code = state.get("code", "")
    functions = _extract_functions_from_code(code)
    new_state = dict(state)
    new_state["functions"] = functions
    new_state["function_count"] = len(functions)
    return NodeResult(state=new_state, log=f"Found {len(functions)} functions")


def check_complexity(state: Dict[str, Any], tools: ToolRegistry) -> NodeResult:
    complexity_score = 0.0
    for fn in state.get("functions", []):
        complexity_score += min(1.0, max(0.1, len(fn) / 10))
    complexity_score = round(complexity_score / max(1, len(state.get("functions", []))), 2) if state.get("functions") else 0.1
    new_state = dict(state)
    new_state["complexity_score"] = complexity_score
    return NodeResult(state=new_state, log=f"Complexity score: {complexity_score}")


def detect_issues(state: Dict[str, Any], tools: ToolRegistry) -> NodeResult:
    detect = tools.get("detect_smells")
    issues = detect(state.get("code", ""))
    new_state = dict(state)
    new_state["issues"] = issues
    return NodeResult(state=new_state, log=f"Issues detected: {issues.get('issues', 0)}")


def suggest_improvements(state: Dict[str, Any], tools: ToolRegistry) -> NodeResult:
    suggestions: List[str] = []
    complexity = state.get("complexity_score", 0)
    if complexity > 0.7:
        suggestions.append("Reduce branching or split large functions.")
    if state.get("issues", {}).get("issues", 0) > 0:
        suggestions.append("Address flagged code smells.")
    if not suggestions:
        suggestions.append("Looks good, minor refactors only.")
    new_state = dict(state)
    new_state.setdefault("suggestions", []).extend(suggestions)
    return NodeResult(state=new_state, log=f"Added {len(suggestions)} suggestions")


def check_quality(state: Dict[str, Any], tools: ToolRegistry) -> NodeResult:
    threshold = state.get("quality_threshold", 0.7)
    max_loops = state.get("max_iterations", 3)
    iterations = state.get("iterations", 0) + 1

    issues_count = state.get("issues", {}).get("issues", 0)
    complexity = state.get("complexity_score", 0)
    score = max(0.0, 1.0 - (0.2 * issues_count) - (0.3 * complexity))
    new_state = dict(state)
    new_state["quality_score"] = round(score, 2)
    new_state["iterations"] = iterations

    log = f"Quality score {new_state['quality_score']} (iteration {iterations})"
    if new_state["quality_score"] >= threshold or iterations >= max_loops:
        return NodeResult(state=new_state, next_node=None, log=log + " -> stop")
    return NodeResult(state=new_state, next_node="suggest_improvements", log=log + " -> continue")


NODE_LIBRARY = {
    "extract_functions": extract_functions,
    "check_complexity": check_complexity,
    "detect_issues": detect_issues,
    "suggest_improvements": suggest_improvements,
    "check_quality": check_quality,
}

