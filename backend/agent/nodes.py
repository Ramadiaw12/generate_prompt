# =============================================================================
# Fichier : backend/agent/nodes.py
# Rôle    : Nodes LangGraph — pipeline de génération + optimisation de prompts
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

import os
import json
import re

from dotenv import load_dotenv
load_dotenv("../.env")

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from agent.state import AgentState

# ── Modèle partagé ────────────────────────────────────────────────────────────
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)

# ─────────────────────────────────────────────────────────────────────────────
# HELPER : nettoie le JSON retourné par le LLM
# Supprime les caractères de contrôle qui cassent json.loads()
# ─────────────────────────────────────────────────────────────────────────────

def clean_json(text: str) -> str:
    """
    Nettoie le texte brut retourné par le LLM avant de le parser en JSON.
    - Supprime les balises markdown ```json ... ```
    - Supprime les caractères de contrôle invalides dans le JSON
    """
    text = re.sub(r"```json|```", "", text).strip()
    # Remplace les sauts de ligne DANS les valeurs JSON par \n littéral
    # pour éviter le "Invalid control character" de json.loads()
    text = re.sub(r'(?<!\\)\n', '\\n', text)
    text = re.sub(r'(?<!\\)\r', '\\r', text)
    text = re.sub(r'(?<!\\)\t', '\\t', text)
    return text


# =============================================================================
# NODE 1 : analyze_input
# Comprend l'intention, le domaine et la complexité de la demande
# =============================================================================

def analyze_input(state: AgentState) -> AgentState:
    """
    Analyse la saisie brute du user.
    Retourne : intent, domain, complexity.
    """
    system = SystemMessage(content="""
Tu es un expert en analyse de requêtes pour la génération de prompts.
Analyse la demande de l'utilisateur et retourne UNIQUEMENT un JSON valide sur UNE SEULE LIGNE avec :
- intent : ce que l'utilisateur veut accomplir (1 phrase courte)
- domain : le domaine principal parmi [code, redaction, analyse, image, data, education, business, autre]
- complexity : niveau de complexité parmi [simple, medium, complex]

Exemple : {"intent": "Créer un assistant pour déboguer du code Python", "domain": "code", "complexity": "medium"}
Ne mets RIEN avant ou après le JSON.
""")
    human = HumanMessage(content=f"Demande utilisateur : {state['user_input']}")

    try:
        response = llm.invoke([system, human])
        text = clean_json(response.content.strip())
        parsed = json.loads(text)
        return {
            **state,
            "intent": parsed.get("intent", ""),
            "domain": parsed.get("domain", "autre"),
            "complexity": parsed.get("complexity", "medium"),
        }
    except Exception as e:
        return {**state, "error": f"Erreur analyze_input: {str(e)}"}


# =============================================================================
# NODE 2 : structure_prompt
# Génère les 5 sections du prompt structuré
# =============================================================================

def structure_prompt(state: AgentState) -> AgentState:
    """
    Génère les 5 sections : role, context, task, output_format, constraints.
    """
    if state.get("error"):
        return state

    system = SystemMessage(content="""
Tu es un expert en prompt engineering.
Génère les 5 sections d'un prompt structuré de haute qualité.
Retourne UNIQUEMENT un JSON valide sur UNE SEULE LIGNE avec ces clés exactes :
- role : le rôle / persona que l'IA doit adopter
- context : le contexte et les informations de fond nécessaires
- task : la tâche précise à accomplir
- output_format : le format attendu de la réponse
- constraints : les contraintes et choses à éviter

Sois précis et actionnable. Ne mets RIEN avant ou après le JSON.
""")

    human = HumanMessage(content=f"""
Demande originale : {state['user_input']}
Intention : {state.get('intent', '')}
Domaine : {state.get('domain', '')}
Complexité : {state.get('complexity', '')}
Génère les 5 sections.
""")

    try:
        response = llm.invoke([system, human])
        text = clean_json(response.content.strip())
        parsed = json.loads(text)
        return {
            **state,
            "role": parsed.get("role", ""),
            "context": parsed.get("context", ""),
            "task": parsed.get("task", ""),
            "output_format": parsed.get("output_format", ""),
            "constraints": parsed.get("constraints", ""),
        }
    except Exception as e:
        return {**state, "error": f"Erreur structure_prompt: {str(e)}"}


# =============================================================================
# NODE 3 : refine_output
# Assemble et améliore le prompt final
# =============================================================================

def refine_output(state: AgentState) -> AgentState:
    """
    Assemble les sections en un prompt final cohérent et fluide.
    """
    if state.get("error"):
        return state

    system = SystemMessage(content="""
Tu es un expert en prompt engineering.
Assemble les 5 sections en un prompt final professionnel, fluide et prêt à l'emploi.
Règles :
- Garde toutes les informations importantes
- Rends le prompt naturel et cohérent
- Commence directement par le contenu du prompt
- Retourne UNIQUEMENT le texte du prompt final, sans JSON, sans balises.
""")

    human = HumanMessage(content=f"""
RÔLE : {state.get('role', '')}
CONTEXTE : {state.get('context', '')}
TÂCHE : {state.get('task', '')}
FORMAT : {state.get('output_format', '')}
CONTRAINTES : {state.get('constraints', '')}
Assemble en un prompt final fluide.
""")

    try:
        response = llm.invoke([system, human])
        full_prompt = response.content.strip()
        return {**state, "full_prompt": full_prompt}
    except Exception as e:
        return {**state, "error": f"Erreur refine_output: {str(e)}"}


# =============================================================================
# NODE 4 : optimize_prompt  ← NOUVEAU — Fonctionnalité PRO
# Analyse un prompt existant et génère une version améliorée + score
# =============================================================================

def optimize_prompt(state: AgentState) -> AgentState:
    """
    Analyse un prompt existant soumis par l'utilisateur et retourne :
    - score_before  : score de qualité du prompt original (0-100)
    - score_after   : score du prompt optimisé (0-100)
    - weaknesses    : liste des faiblesses détectées
    - improvements  : liste des améliorations apportées
    - optimized_prompt : le prompt amélioré, prêt à l'emploi

    C'est une fonctionnalité RÉSERVÉE AU PLAN PRO.
    Le prompt à optimiser est passé via state['prompt_to_optimize'].
    """
    if state.get("error"):
        return state

    # Le prompt à optimiser est dans un champ dédié
    prompt_to_optimize = state.get("prompt_to_optimize", "")
    if not prompt_to_optimize:
        return {**state, "error": "Erreur optimize_prompt: aucun prompt fourni à optimiser."}

    # ── Étape 1 : Analyse des faiblesses ─────────────────────────────────────
    system_analyze = SystemMessage(content="""
Tu es un expert senior en prompt engineering avec 10 ans d'expérience.
Analyse le prompt fourni et retourne UNIQUEMENT un JSON valide sur UNE SEULE LIGNE avec :
- score_before : score de qualité du prompt original de 0 à 100 (sois honnête et critique)
- weaknesses : tableau de 3 à 5 faiblesses spécifiques détectées (phrases courtes)
- missing_elements : tableau des éléments manquants parmi [role, context, task, output_format, constraints, examples]

Critères d'évaluation :
- Clarté et précision (0-25 pts)
- Structure et organisation (0-25 pts)  
- Spécificité du contexte (0-25 pts)
- Format de sortie défini (0-25 pts)

Ne mets RIEN avant ou après le JSON.
""")

    human_analyze = HumanMessage(content=f"Prompt à analyser : {prompt_to_optimize}")

    try:
        response_analyze = llm.invoke([system_analyze, human_analyze])
        text_analyze = clean_json(response_analyze.content.strip())
        analysis = json.loads(text_analyze)
        score_before = analysis.get("score_before", 50)
        weaknesses = analysis.get("weaknesses", [])
        missing_elements = analysis.get("missing_elements", [])
    except Exception as e:
        return {**state, "error": f"Erreur optimize_prompt (analyse): {str(e)}"}

    # ── Étape 2 : Génération du prompt optimisé ───────────────────────────────
    system_optimize = SystemMessage(content="""
Tu es un expert senior en prompt engineering.
Tu reçois un prompt original avec ses faiblesses identifiées.
Ta mission : réécrire ce prompt pour le rendre professionnel, précis et efficace.

Règles d'optimisation :
1. Ajoute un rôle clair si manquant ("Tu es un expert en...")
2. Enrichis le contexte avec les informations manquantes
3. Rends la tâche précise et actionnable (étapes si complexe)
4. Spécifie le format de sortie attendu
5. Ajoute des contraintes pertinentes
6. Garde la même intention que le prompt original

Retourne UNIQUEMENT le prompt optimisé, sans explication, sans JSON, sans balises.
""")

    human_optimize = HumanMessage(content=f"""
Prompt original : {prompt_to_optimize}

Faiblesses identifiées : {', '.join(weaknesses)}
Éléments manquants : {', '.join(missing_elements)}

Génère le prompt optimisé et professionnel.
""")

    try:
        response_optimize = llm.invoke([system_optimize, human_optimize])
        optimized_prompt = response_optimize.content.strip()
    except Exception as e:
        return {**state, "error": f"Erreur optimize_prompt (optimisation): {str(e)}"}

    # ── Étape 3 : Score du prompt optimisé ───────────────────────────────────
    system_score = SystemMessage(content="""
Tu es un expert en prompt engineering.
Évalue ce prompt optimisé et retourne UNIQUEMENT un JSON sur UNE SEULE LIGNE avec :
- score_after : score de qualité de 0 à 100
- improvements : tableau de 3 à 5 améliorations apportées (phrases courtes)

Ne mets RIEN avant ou après le JSON.
""")

    human_score = HumanMessage(content=f"Prompt optimisé à évaluer : {optimized_prompt}")

    try:
        response_score = llm.invoke([system_score, human_score])
        text_score = clean_json(response_score.content.strip())
        scoring = json.loads(text_score)
        score_after = scoring.get("score_after", 85)
        improvements = scoring.get("improvements", [])
    except Exception as e:
        # Si l'évaluation finale échoue, on met des valeurs par défaut
        score_after = min(score_before + 30, 95)
        improvements = ["Structure améliorée", "Contexte enrichi", "Format défini"]

    return {
        **state,
        "score_before": score_before,
        "score_after": score_after,
        "weaknesses": weaknesses,
        "improvements": improvements,
        "optimized_prompt": optimized_prompt,
    }