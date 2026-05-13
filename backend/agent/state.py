# =============================================================================
# Fichier : backend/agent/state.py
# Rôle    : Définition de l'état partagé entre tous les nodes LangGraph
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

from typing import TypedDict, Optional, List


class AgentState(TypedDict):
    """
    État partagé entre tous les nodes du pipeline LangGraph.
    Chaque node lit et écrit dans cet état.

    ── Pipeline génération (nodes 1, 2, 3) ──────────────────────────────────
    user_input    → saisie brute de l'utilisateur
    intent        → intention détectée (node 1)
    domain        → domaine détecté   (node 1)
    complexity    → complexité         (node 1)
    role          → section rôle       (node 2)
    context       → section contexte   (node 2)
    task          → section tâche      (node 2)
    output_format → section format     (node 2)
    constraints   → section contraintes(node 2)
    full_prompt   → prompt final       (node 3)

    ── Pipeline optimisation (node 4) — Plan PRO ────────────────────────────
    prompt_to_optimize → prompt existant soumis par l'user
    score_before       → score qualité avant optimisation (0-100)
    score_after        → score qualité après optimisation (0-100)
    weaknesses         → liste des faiblesses détectées
    improvements       → liste des améliorations apportées
    optimized_prompt   → prompt amélioré prêt à l'emploi

    ── Erreurs ──────────────────────────────────────────────────────────────
    error → message d'erreur si un node échoue (pipeline court-circuité)
    """

    # ── Génération ─────────────────────────────────────────────────────────
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

    # ── Optimisation PRO ───────────────────────────────────────────────────
    prompt_to_optimize: Optional[str]
    score_before:       Optional[int]
    score_after:        Optional[int]
    weaknesses:         Optional[List[str]]
    improvements:       Optional[List[str]]
    optimized_prompt:   Optional[str]

    # ── Erreur ─────────────────────────────────────────────────────────────
    error: str