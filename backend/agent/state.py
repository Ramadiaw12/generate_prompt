# Fichier : backend/agent/state.py
from typing import TypedDict, Optional


class AgentState(TypedDict):
    """
    État partagé entre tous les nodes du graphe LangGraph.
    Chaque node lit et enrichit cet état.
    """
    # Input
    user_input: str                    # Saisie brute de l'utilisateur

    # Résultats intermédiaires
    intent: Optional[str]              # Intention détectée (node: analyze)
    domain: Optional[str]              # Domaine détecté : code, rédaction, analyse...
    complexity: Optional[str]          # simple | medium | complex

    # Sections du prompt structuré (node: structure)
    role: Optional[str]
    context: Optional[str]
    task: Optional[str]
    output_format: Optional[str]
    constraints: Optional[str]

    # Prompt final assemblé (node: refine)
    full_prompt: Optional[str]

    # Erreur éventuelle
    error: Optional[str]
