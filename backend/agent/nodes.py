# Fichier : backend/agent/nodes.py*
import os
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState

# Modèle partagé entre tous les nodes
# llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm = ChatOpenAI(
    model="grok-3",               
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
    temperature=0,
)

# ─────────────────────────────────────────────────────────────────────────────
# NODE 1 : analyze_input
# Comprend l'intention, le domaine et la complexité de la demande
# ─────────────────────────────────────────────────────────────────────────────

def analyze_input(state: AgentState) -> AgentState:
    """
    Analyse la saisie brute du user.
    Retourne : intent, domain, complexity.
    """
    system = SystemMessage(content="""
Tu es un expert en analyse de requêtes pour la génération de prompts.
Analyse la demande de l'utilisateur et retourne UNIQUEMENT un JSON valide avec :
- intent : ce que l'utilisateur veut accomplir (1 phrase courte)
- domain : le domaine principal parmi [code, redaction, analyse, image, data, education, business, autre]
- complexity : niveau de complexité parmi [simple, medium, complex]

Exemple de réponse :
{"intent": "Créer un assistant pour déboguer du code Python", "domain": "code", "complexity": "medium"}
""")
    human = HumanMessage(content=f"Demande utilisateur : {state['user_input']}")

    try:
        response = llm.invoke([system, human])
        text = response.content.strip()
        text = re.sub(r"```json|```", "", text).strip()
        parsed = json.loads(text)

        return {
            **state,
            "intent": parsed.get("intent", ""),
            "domain": parsed.get("domain", "autre"),
            "complexity": parsed.get("complexity", "medium"),
        }
    except Exception as e:
        return {**state, "error": f"Erreur analyze_input: {str(e)}"}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 2 : structure_prompt
# Génère les 5 sections du prompt structuré
# ─────────────────────────────────────────────────────────────────────────────

def structure_prompt(state: AgentState) -> AgentState:
    """
    Génère les 5 sections : role, context, task, output_format, constraints.
    S'appuie sur l'analyse du node précédent.
    """
    if state.get("error"):
        return state

    system = SystemMessage(content="""
Tu es un expert en prompt engineering. 
À partir de l'analyse fournie, génère les 5 sections d'un prompt structuré de haute qualité.
Retourne UNIQUEMENT un JSON valide avec ces clés exactes :
- role : le rôle / persona que l'IA doit adopter
- context : le contexte et les informations de fond nécessaires
- task : la tâche précise à accomplir, step-by-step si complexe
- output_format : le format attendu de la réponse (longueur, structure, style)
- constraints : les contraintes, limites et choses à éviter

Sois précis, actionnable et adapté au domaine détecté.
Ne mets aucun texte avant ou après le JSON.
""")

    human = HumanMessage(content=f"""
Demande originale : {state['user_input']}
Intention détectée : {state.get('intent', '')}
Domaine : {state.get('domain', '')}
Complexité : {state.get('complexity', '')}

Génère les 5 sections du prompt structuré.
""")

    try:
        response = llm.invoke([system, human])
        text = response.content.strip()
        text = re.sub(r"```json|```", "", text).strip()
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


# ─────────────────────────────────────────────────────────────────────────────
# NODE 3 : refine_output
# Assemble et améliore le prompt final
# ─────────────────────────────────────────────────────────────────────────────

def refine_output(state: AgentState) -> AgentState:
    """
    Assemble les sections en un prompt final cohérent et fluide.
    """
    if state.get("error"):
        return state

    system = SystemMessage(content="""
Tu es un expert en prompt engineering. 
Tu reçois les 5 sections d'un prompt structuré.
Ton travail : assembler ces sections en un prompt final professionnel, fluide et prêt à l'emploi.

Règles :
- Garde toutes les informations importantes des sections
- Rends le prompt naturel et cohérent (pas juste une concaténation)
- Commence directement par le contenu du prompt, pas par une introduction
- Le prompt doit être directement utilisable tel quel

Retourne UNIQUEMENT le texte du prompt final, sans JSON, sans balises.
""")

    human = HumanMessage(content=f"""
RÔLE : {state.get('role', '')}

CONTEXTE : {state.get('context', '')}

TÂCHE : {state.get('task', '')}

FORMAT DE SORTIE : {state.get('output_format', '')}

CONTRAINTES : {state.get('constraints', '')}

Assemble ces sections en un prompt final fluide et professionnel.
""")

    try:
        response = llm.invoke([system, human])
        full_prompt = response.content.strip()
        return {**state, "full_prompt": full_prompt}
    except Exception as e:
        return {**state, "error": f"Erreur refine_output: {str(e)}"}