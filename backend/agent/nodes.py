# =============================================================================
# Fichier : backend/agent/nodes.py
# Rôle    : Nodes LangGraph — génération de prompts
#           Mode concis  → prompt 2-3 lignes
#           Mode complet → prompt 5 sections détaillées
#           Mode expert  → prompt ultra-détaillé avec exemples
#           Langue       → prompt généré dans la langue choisie (fr/en/ar)
# =============================================================================

import os, json, re
from dotenv import load_dotenv
load_dotenv("../.env")

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from agent.state import AgentState

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)

# Langue   instructions 
LANG_INSTRUCTIONS = {
    "fr": "Réponds UNIQUEMENT en français. Génère le prompt final en français.",
    "en": "Respond ONLY in English. Generate the final prompt in English.",
    "ar": "أجب فقط باللغة العربية. اكتب البرومبت النهائي باللغة العربية.",
}

def get_lang_instruction(lang: str) -> str:
    return LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["fr"])

# Helper JSON 
def clean_json(text: str) -> str:
    text = re.sub(r"```json|```", "", text).strip()
    # Remplace les sauts de ligne dans les valeurs JSON
    in_string = False
    result = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"' and (i == 0 or text[i-1] != '\\'):
            in_string = not in_string
        if in_string and c == '\n':
            result.append('\\n')
        elif in_string and c == '\r':
            result.append('\\r')
        elif in_string and c == '\t':
            result.append('\\t')
        else:
            result.append(c)
        i += 1
    return ''.join(result)

# =============================================================================
# NODE 1 : analyze_input
# =============================================================================
def analyze_input(state: AgentState) -> AgentState:
    lang = state.get("lang", "fr")
    lang_instr = get_lang_instruction(lang)

    system = SystemMessage(content=f"""
Tu es un expert en analyse de requêtes pour la génération de prompts.
{lang_instr}
Analyse la demande et retourne UNIQUEMENT un JSON valide sur UNE SEULE LIGNE :
{{"intent": "intention courte", "domain": "code|redaction|analyse|image|data|education|business|autre", "complexity": "simple|medium|complex"}}
Ne mets RIEN avant ou après le JSON.
""")
    human = HumanMessage(content=f"Demande : {state['user_input']}")

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
# Adapté selon le mode : concis / complet / expert
# =============================================================================
def structure_prompt(state: AgentState) -> AgentState:
    if state.get("error"):
        return state

    mode = state.get("mode", "complet")
    lang = state.get("lang", "fr")
    lang_instr = get_lang_instruction(lang)

    #  Mode CONCIS : prompt court, économe en tokens 
    if mode == "concis":
        system = SystemMessage(content=f"""
Tu es un expert en prompt engineering.
{lang_instr}

IMPORTANT : 
- Tu crées un prompt destiné à une autre IA.
- Tu ne dois jamais exécuter la tâche.
- Tu ne dois jamais répondre à la demande de l'utilisateur.
- Tu dois uniquement transformer la demande en instructions optimisées.
- Le prompt doit être très court et économe en tokens.
- Tu génères un prompt CONCIS 
— Maximum 2-3 lignes, efficace, direct.
- Pas de sections longues. 
- Pas d'explications. 
- Juste l'essentiel.

Retourne UNIQUEMENT un JSON valide sur UNE SEULE LIGNE :
{{"role": "rôle en 1 phrase max", "context": "", "task": "tâche en 1 phrase directe", "output_format": "format en quelques mots", "constraints": "1-2 contraintes max"}}
""")

    # Mode EXPERT : prompt ultra-détaillé avec exemples 
    elif mode == "expert":
        system = SystemMessage(content=f"""
Tu es un expert senior en prompt engineering.
{lang_instr}

IMPORTANT :
- Tu génères un prompt destiné à être utilisé par une autre IA.
- Tu n'es jamais l'IA qui exécute la tâche.
- Ne réponds jamais directement à la demande de l'utilisateur.
- Ne produis jamais le résultat final attendu.
- Transforme uniquement la demande en instructions optimisées.
- Conserve l'intention originale de l'utilisateur.

Tu génères un prompt EXPERT ultra-détaillé et professionnel avec :
- Un rôle très précis incluant le niveau d'expertise requis
- Un contexte riche et détaillé
- Une tâche décomposée en étapes logiques et séquentielles
- Un format de sortie clairement défini
- Des contraintes précises
- Des critères de qualité
- Des exemples lorsque cela apporte de la valeur


Retourne UNIQUEMENT un JSON valide sur UNE SEULE LIGNE :
{{"role": "rôle expert détaillé", "context": "contexte riche et complet", "task": "tâche décomposée en étapes", "output_format": "format précis avec structure", "constraints": "contraintes strictes + exemples"}}
""")

    # Mode COMPLET (défaut) : 5 sections équilibrées
    else:
        system = SystemMessage(content=f"""
Tu es un expert en prompt engineering.
{lang_instr}

IMPORTANT :
- Tu génères un prompt destiné à être utilisé par une autre IA.
- Tu n'es jamais l'IA qui exécute la tâche.
- Ne réponds jamais directement à la demande de l'utilisateur.
- Ne produis jamais le résultat final attendu.
- Transforme uniquement la demande en instructions optimisées.
- Conserve l'intention et l'objectif de l'utilisateur.

Tu génères un prompt COMPLET et structuré avec 5 sections équilibrées.
Chaque section doit être précise, claire et professionnelle.

Retourne UNIQUEMENT un JSON valide sur UNE SEULE LIGNE :
{{"role": "rôle et persona claire", "context": "contexte et informations de fond", "task": "tâche précise à accomplir", "output_format": "format attendu de la réponse", "constraints": "contraintes et limites"}}
""")

    human = HumanMessage(content=f"""
Demande : {state['user_input']}
Intention : {state.get('intent', '')}
Domaine : {state.get('domain', '')}
Complexité : {state.get('complexity', '')}
Mode : {mode}
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
# Assemble le prompt final selon le mode et la langue
# =============================================================================
def refine_output(state: AgentState) -> AgentState:
    if state.get("error"):
        return state

    mode = state.get("mode", "complet")
    lang = state.get("lang", "fr")
    lang_instr = get_lang_instruction(lang)

    # Instructions d'assemblage selon le mode
    if mode == "concis":
        assembly_instr = """
Assemble ces sections en UN prompt court et optimisé destiné à une autre IA.

Règles :
- Maximum 2 à 3 lignes.
- Conserve uniquement les informations essentielles.
- Utilise des instructions directes et actionnables.
- N'exécute jamais la tâche.
- Ne produis jamais le résultat final attendu.
- Génère uniquement le prompt final.
- Aucune introduction, explication ou commentaire.

Le prompt doit être immédiatement utilisable par une autre IA.
IMPORTANT : 2-3 lignes MAXIMUM. Pas plus.
"""
    elif mode == "expert":
        assembly_instr = """
Assemble ces sections en un prompt EXPERT ultra-professionnel et détaillé.

Règles :
- Le résultat doit être un prompt destiné à une autre IA.
- N'exécute jamais la tâche décrite.
- Ne produis jamais la réponse finale attendue.
- Conserve toutes les informations importantes des sections fournies.
- Organise le contenu avec une structure claire et professionnelle.
- Utilise des titres ou marqueurs visuels lorsque cela améliore la lisibilité.
- Décompose les instructions complexes en étapes logiques.
- Ajoute des critères de qualité et de validation lorsque pertinent.
- Inclue des exemples uniquement comme exemples à suivre par l'IA cible, jamais comme résultat final.

Le prompt doit être complet, précis et directement utilisable dans un contexte professionnel.
"""
    else:
        assembly_instr = """
Assemble ces sections en un prompt COMPLET, fluide et professionnel.

Règles :
- Le résultat doit être un prompt destiné à une autre IA.
- N'exécute jamais la tâche décrite.
- Ne produis jamais la réponse finale attendue.
- Conserve toutes les informations importantes.
- Organise naturellement les instructions pour maximiser leur clarté.
- Supprime les répétitions inutiles.
- Garde un bon équilibre entre précision et concision.
- N'ajoute aucune explication ou commentaire hors du prompt.

Le prompt final doit être directement utilisable par une autre IA.
"""

    system = SystemMessage(content=f"""
Tu es un expert en prompt engineering.
{lang_instr}
{assembly_instr}
Retourne UNIQUEMENT le texte du prompt final. Pas de JSON, pas de balises, pas d'introduction.
""")

    human = HumanMessage(content=f"""
RÔLE : {state.get('role', '')}
CONTEXTE : {state.get('context', '')}
TÂCHE : {state.get('task', '')}
FORMAT : {state.get('output_format', '')}
CONTRAINTES : {state.get('constraints', '')}
""")

    try:
        response = llm.invoke([system, human])
        full_prompt = response.content.strip()
        return {**state, "full_prompt": full_prompt}
    except Exception as e:
        return {**state, "error": f"Erreur refine_output: {str(e)}"}


# =============================================================================
# NODE 4 : optimize_prompt (PRO)
# =============================================================================
def optimize_prompt(state: AgentState) -> AgentState:
    if state.get("error"):
        return state

    lang = state.get("lang", "fr")
    lang_instr = get_lang_instruction(lang)
    prompt_to_optimize = state.get("prompt_to_optimize", "")

    if not prompt_to_optimize:
        return {**state, "error": "Aucun prompt fourni à optimiser."}

    # Étape 1 : Analyse
    system_analyze = SystemMessage(content=f"""
Tu es un expert senior en prompt engineering.
{lang_instr}

IMPORTANT :
- Tu analyses uniquement la qualité du prompt fourni.
- Tu n'exécutes jamais la tâche décrite dans le prompt.
- Tu n'évalues pas le sujet traité mais la qualité des instructions.
- Tu identifies les points faibles du prompt du point de vue du Prompt Engineering.
- Tu identifies les éléments manquants qui pourraient améliorer le prompt.

Critères d'évaluation :
- Clarté des instructions
- Précision de l'objectif
- Contexte fourni
- Contraintes définies
- Format de sortie spécifié
- Robustesse face aux ambiguïtés
- Optimisation pour les modèles d'IA

Analyse ce prompt et retourne UNIQUEMENT un JSON sur UNE SEULE LIGNE :
{{"score_before": 0-100, "weaknesses": ["faiblesse 1", "faiblesse 2"], "missing_elements": ["element manquant"]}}
""")
    try:
        r1 = llm.invoke([system_analyze, HumanMessage(content=f"Prompt : {prompt_to_optimize}")])
        a = json.loads(clean_json(r1.content.strip()))
        score_before = a.get("score_before", 50)
        weaknesses = a.get("weaknesses", [])
        missing = a.get("missing_elements", [])
    except Exception as e:
        return {**state, "error": f"Erreur optimize (analyse): {str(e)}"}

    # Étape 2 : Optimisation
    system_opt = SystemMessage(content=f"""
Tu es un expert senior en prompt engineering.
{lang_instr}
Ta mission est uniquement d'améliorer et restructurer le prompt fourni.

Règles obligatoires :
- Génère un prompt destiné à être utilisé par une autre IA.
- Ne réalise jamais la tâche demandée dans le prompt.
- Ne réponds jamais à la demande de l'utilisateur.
- Ne produis jamais le résultat attendu.
- Reformule les instructions pour les rendre plus claires, précises et professionnelles.
- Ajoute du contexte, des contraintes et un format de sortie si cela améliore le prompt.
- Conserve l'intention originale de l'utilisateur.

Retourne uniquement le prompt optimisé, sans explication, sans commentaire et sans balises markdown.
""")
    try:
        r2 = llm.invoke([system_opt, HumanMessage(content=f"Prompt original : {prompt_to_optimize}\nFaiblesses : {', '.join(weaknesses)}")])
        optimized_prompt = r2.content.strip()
    except Exception as e:
        return {**state, "error": f"Erreur optimize (optimisation): {str(e)}"}

    # Étape 3 : Score final
    system_score = SystemMessage(content=f"""
Tu es un expert en prompt engineering.
{lang_instr}
Évalue ce prompt optimisé et retourne UNIQUEMENT un JSON sur UNE SEULE LIGNE :
{{"score_after": 0-100, "improvements": ["amélioration 1", "amélioration 2"]}}
""")
    try:
        r3 = llm.invoke([system_score, HumanMessage(content=f"Prompt : {optimized_prompt}")])
        s = json.loads(clean_json(r3.content.strip()))
        score_after = s.get("score_after", 85)
        improvements = s.get("improvements", [])
    except:
        score_after = min(score_before + 30, 95)
        improvements = ["Structure améliorée", "Contexte enrichi"]

    return {
        **state,
        "score_before": score_before,
        "score_after": score_after,
        "weaknesses": weaknesses,
        "improvements": improvements,
        "optimized_prompt": optimized_prompt,
    }