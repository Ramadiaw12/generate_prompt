from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    # Génération
    user_input:    str
    intent:        str
    domain:        str
    complexity:    str
    role:          str
    context:       str
    task:          str
    output_format: str
    constraints:   str
    full_prompt:   str
    # Mode et langue
    mode:          Optional[str]   # concis | complet | expert
    lang:          Optional[str]   # fr | en | ar
    # Optimisation PRO
    prompt_to_optimize: Optional[str]
    score_before:       Optional[int]
    score_after:        Optional[int]
    weaknesses:         Optional[List[str]]
    improvements:       Optional[List[str]]
    optimized_prompt:   Optional[str]
    # Erreur
    error: str