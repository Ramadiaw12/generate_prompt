# Fichier : backend/agent/graph.py
from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes import analyze_input, structure_prompt, refine_output


def has_error(state: AgentState) -> str:
    """Branchement conditionnel : stop si une erreur est survenue."""
    return "error" if state.get("error") else "continue"


def build_graph() -> StateGraph:
    """
    Construit et compile le graphe LangGraph.

    Flux :
        analyze_input → (si erreur → END) → structure_prompt → (si erreur → END) → refine_output → END
    """
    graph = StateGraph(AgentState)

    # ── Enregistrement des nodes ──────────────────────────────────────────────
    graph.add_node("analyze_input", analyze_input)
    graph.add_node("structure_prompt", structure_prompt)
    graph.add_node("refine_output", refine_output)

    # ── Point d'entrée ────────────────────────────────────────────────────────
    graph.set_entry_point("analyze_input")

    # ── Edges conditionnels ───────────────────────────────────────────────────
    graph.add_conditional_edges(
        "analyze_input",
        has_error,
        {"error": END, "continue": "structure_prompt"},
    )
    graph.add_conditional_edges(
        "structure_prompt",
        has_error,
        {"error": END, "continue": "refine_output"},
    )

    # ── Fin ───────────────────────────────────────────────────────────────────
    graph.add_edge("refine_output", END)

    return graph.compile()


# Instance compilée (importée dans le router)
prompt_graph = build_graph()
