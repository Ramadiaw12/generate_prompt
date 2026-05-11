# =============================================================================
# Fichier : backend/main.py
# Rôle    : Point d'entrée de l'API FastAPI
#           - Démarre le serveur
#           - Crée les tables PostgreSQL au démarrage
#           - Enregistre les routes auth + generate-prompt
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

# ── Chargement du .env EN PREMIER ─────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv("../.env")
# ⚠️ DOIT être avant tout import LangChain/OpenAI/SQLAlchemy
# Sans ça, les variables d'environnement ne sont pas disponibles

# ── Imports ───────────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent.graph import build_graph
# build_graph : compile le LangGraph une seule fois au démarrage

from auth.router import router as auth_router, get_current_user
# auth_router    : routes /auth/register, /auth/login, /auth/me
# get_current_user : dépendance pour protéger les routes avec JWT

from db.database import get_db, create_tables
# get_db       : session PostgreSQL par requête
# create_tables : crée les tables au démarrage si elles n'existent pas

from models.schemas import PromptHistory
# PromptHistory : table PostgreSQL pour sauvegarder les prompts générés

from models.schemas import User
# User : table PostgreSQL des utilisateurs

# ── Lifespan ──────────────────────────────────────────────────────────────────

graph = None
# Variable globale pour stocker le graph compilé
# On le compile une seule fois au démarrage (pas à chaque requête)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan FastAPI : code exécuté au démarrage et à l'arrêt du serveur.

    Au DÉMARRAGE (avant yield) :
    - Crée les tables PostgreSQL si elles n'existent pas
    - Compile le LangGraph agent

    À L'ARRÊT (après yield) :
    - Affiche un message de confirmation
    """
    global graph

    # Crée les tables PostgreSQL (users + prompt_history)
    # Si elles existent déjà → rien ne se passe, les données sont préservées
    create_tables()

    # Compile le LangGraph une seule fois
    # (compilation = construction du graphe de nodes, coûteuse en temps)
    graph = build_graph()
    print("✅ Agent graph compilé et prêt.")

    yield  # le serveur tourne ici

    print("🛑 Arrêt du serveur.")

# ── Application FastAPI ───────────────────────────────────────────────────────

app = FastAPI(
    title="Prompt Engineer API",
    description="Génère des prompts structurés à partir d'une demande utilisateur.",
    version="2.0.0",  # v2 : ajout PostgreSQL
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # En production : remplacez "*" par votre domaine exact
    # ex: ["https://mon-app.vercel.app"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Enregistrement des routes auth ────────────────────────────────────────────

app.include_router(auth_router)
# Ajoute les routes : POST /auth/register, POST /auth/login, GET /auth/me

# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class PromptRequest(BaseModel):
    """Données reçues pour générer un prompt."""
    user_input: str  # la demande brute de l'utilisateur

class PromptResponse(BaseModel):
    """Données renvoyées après génération du prompt."""
    # Résultats de l'analyse (Node 1)
    intent: str
    domain: str
    complexity: str
    # Sections structurées (Node 2)
    role: str
    context: str
    task: str
    output_format: str
    constraints: str
    # Prompt final assemblé (Node 3)
    full_prompt: str

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Route de sanity check — vérifie que le serveur tourne."""
    return {"status": "ok", "message": "Prompt Engineer API v2.0 🚀"}


@app.get("/health")
def health():
    """Vérifie l'état du serveur et du graph."""
    return {
        "status": "healthy",
        "graph_ready": graph is not None,
        "database": "postgresql",
    }


@app.post("/generate-prompt", response_model=PromptResponse)
async def generate_prompt(
    request: PromptRequest,
    current_user: User = Depends(get_current_user),
    # 🔒 Route protégée : FastAPI vérifie automatiquement le JWT
    # Si le token est absent/invalide → 401 Unauthorized automatique
    db: Session = Depends(get_db),
    # Session PostgreSQL injectée automatiquement
):
    """
    Génère un prompt structuré en 3 étapes via LangGraph.
    Route protégée par JWT.

    Étapes :
    1. Vérifie le token JWT (via Depends(get_current_user))
    2. Lance le pipeline agent (analyze → structure → refine)
    3. Sauvegarde le prompt généré dans PostgreSQL (prompt_history)
    4. Retourne les résultats au frontend
    """

    # Validation de l'input
    if not request.user_input.strip():
        raise HTTPException(
            status_code=422,
            detail="Le champ user_input ne peut pas être vide."
        )

    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="Agent non initialisé. Réessayez dans quelques secondes."
        )

    # État initial du graph LangGraph
    # Chaque clé correspond à un champ de AgentState dans state.py
    initial_state = {
        "user_input": request.user_input.strip(),
        "intent": "",
        "domain": "",
        "complexity": "",
        "role": "",
        "context": "",
        "task": "",
        "output_format": "",
        "constraints": "",
        "full_prompt": "",
        "error": "",
    }

    # Lance le pipeline agent (3 nodes : analyze → structure → refine)
    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne de l'agent : {str(e)}"
        )

    # Si un node a capturé une erreur métier
    if final_state.get("error"):
        raise HTTPException(
            status_code=500,
            detail=final_state["error"]
        )

    # ── Sauvegarde dans PostgreSQL ────────────────────────────────────────────
    # On sauvegarde chaque prompt généré dans l'historique de l'utilisateur
    prompt_record = PromptHistory(
        user_id=current_user.id,                        # lié au user connecté
        user_input=request.user_input.strip(),
        intent=final_state.get("intent", ""),
        domain=final_state.get("domain", ""),
        complexity=final_state.get("complexity", ""),
        role=final_state.get("role", ""),
        context=final_state.get("context", ""),
        task=final_state.get("task", ""),
        output_format=final_state.get("output_format", ""),
        constraints=final_state.get("constraints", ""),
        full_prompt=final_state.get("full_prompt", ""),
    )

    db.add(prompt_record)   # prépare l'insertion
    db.commit()             # sauvegarde définitivement dans PostgreSQL
    db.refresh(prompt_record)
    print(f"💾 Prompt #{prompt_record.id} sauvegardé pour {current_user.email}")

    # Retourne les résultats au frontend
    return PromptResponse(
        intent=final_state.get("intent", ""),
        domain=final_state.get("domain", ""),
        complexity=final_state.get("complexity", ""),
        role=final_state.get("role", ""),
        context=final_state.get("context", ""),
        task=final_state.get("task", ""),
        output_format=final_state.get("output_format", ""),
        constraints=final_state.get("constraints", ""),
        full_prompt=final_state.get("full_prompt", ""),
    )


@app.get("/my-prompts")
async def my_prompts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retourne l'historique des prompts générés par l'utilisateur connecté.
    Route protégée par JWT.

    Retourne les 20 derniers prompts, du plus récent au plus ancien.
    """
    prompts = (
        db.query(PromptHistory)
        .filter(PromptHistory.user_id == current_user.id)
        # Filtre : uniquement les prompts de l'utilisateur connecté
        .order_by(PromptHistory.created_at.desc())
        # Tri : du plus récent au plus ancien
        .limit(20)
        # Limite : 20 prompts maximum
        .all()
    )

    return {
        "total": len(prompts),
        "prompts": [
            {
                "id": p.id,
                "user_input": p.user_input,
                "domain": p.domain,
                "complexity": p.complexity,
                "full_prompt": p.full_prompt,
                "created_at": p.created_at.isoformat(),
            }
            for p in prompts
        ]
    }