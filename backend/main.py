# =============================================================================
# Fichier : backend/main.py
# Rôle    : Point d'entrée FastAPI
#           - PostgreSQL
#           - Rate Limiting (slowapi)
#           - JWT Auth
#           - LangGraph Agent
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

# ── Chargement du .env EN PREMIER ─────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv("../.env")
# ⚠️ Doit être avant tout import LangChain/SQLAlchemy

# ── Imports ───────────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Rate limiting — protection contre les attaques brute force
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
# Limiter          : gère les limites de requêtes par IP
# get_remote_address : identifie l'IP de chaque visiteur
# RateLimitExceeded : exception levée quand la limite est dépassée

from agent.graph import build_graph
from auth.router import router as auth_router, get_current_user
from db.database import get_db, create_tables
from models.schemas import PromptHistory, User

# ── Rate Limiter ──────────────────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address,
    # Identifie les utilisateurs par leur adresse IP
    # Chaque IP a son propre compteur de requêtes
)
# Le limiter sera attaché à l'app FastAPI plus bas

# ── Lifespan ──────────────────────────────────────────────────────────────────

graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Exécuté au démarrage et à l'arrêt du serveur.
    Crée les tables PostgreSQL + compile le graph LangGraph.
    """
    global graph
    create_tables()        # crée users + prompt_history si elles n'existent pas
    graph = build_graph()  # compile le LangGraph une seule fois
    print("✅ Tables PostgreSQL créées / vérifiées.")
    print("✅ Agent graph compilé et prêt.")
    yield
    print("🛑 Arrêt du serveur.")

# ── Application FastAPI ───────────────────────────────────────────────────────

app = FastAPI(
    title="Prompt Engineer API",
    description="Génère des prompts structurés à partir d'une demande utilisateur.",
    version="2.0.0",
    lifespan=lifespan,
)

# Attache le rate limiter à l'app
app.state.limiter = limiter
# Gestionnaire d'erreur personnalisé quand la limite est dépassée
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Quand une IP dépasse sa limite → HTTP 429 Too Many Requests automatique

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://prompt-craft26.netlify.app/", "https://promptcraft.today"],

    # ✅ SÉCURISÉ : on accepte UNIQUEMENT le frontend local
    # En production : remplacez par votre vrai domaine
    # ex: ["https://mon-app.vercel.app"]
    allow_methods=["GET", "POST"],
    # On autorise uniquement GET et POST (pas DELETE, PUT non utilisés)
    allow_headers=["Authorization", "Content-Type"],
    # On autorise uniquement les headers nécessaires
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(auth_router)
# Ajoute /auth/register, /auth/login, /auth/me

# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class PromptRequest(BaseModel):
    """Données reçues pour générer un prompt."""
    user_input: str

class PromptResponse(BaseModel):
    """Données renvoyées après génération."""
    intent: str
    domain: str
    complexity: str
    role: str
    context: str
    task: str
    output_format: str
    constraints: str
    full_prompt: str

# ── Routes publiques ──────────────────────────────────────────────────────────

@app.get("/")
@limiter.limit("30/minute")
# Maximum 30 requêtes par minute par IP sur cette route
def root(request: Request):
    """Sanity check — vérifie que le serveur tourne."""
    return {"status": "ok", "message": "Prompt Engineer API v2.0 🚀"}


@app.get("/health")
@limiter.limit("30/minute")
def health(request: Request):
    """Vérifie l'état du serveur."""
    return {
        "status": "healthy",
        "graph_ready": graph is not None,
        "database": "postgresql",
    }

# ── Routes protégées ──────────────────────────────────────────────────────────

@app.post("/generate-prompt", response_model=PromptResponse)
@limiter.limit("10/minute")
# 🔒 Maximum 10 générations par minute par IP
# Protège contre le scraping et les abus de l'API Groq
async def generate_prompt(
    request: Request,                              # nécessaire pour slowapi
    body: PromptRequest,                           # données reçues
    current_user: User = Depends(get_current_user),# 🔒 JWT requis
    db: Session = Depends(get_db),                 # session PostgreSQL
):
    """
    Génère un prompt structuré en 3 étapes via LangGraph.
    🔒 Route protégée : JWT + Rate limit 10/minute par IP.

    Étapes :
    1. Vérifie le JWT
    2. Lance le pipeline agent
    3. Sauvegarde dans PostgreSQL
    4. Retourne les résultats
    """

    if not body.user_input.strip():
        raise HTTPException(
            status_code=422,
            detail="Le champ user_input ne peut pas être vide."
        )

    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="Agent non initialisé. Réessayez dans quelques secondes."
        )

    # État initial du pipeline LangGraph
    initial_state = {
        "user_input": body.user_input.strip(),
        "intent": "", "domain": "", "complexity": "",
        "role": "", "context": "", "task": "",
        "output_format": "", "constraints": "",
        "full_prompt": "", "error": "",
    }

    # Lance le pipeline agent (3 nodes)
    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne de l'agent : {str(e)}"
        )

    if final_state.get("error"):
        raise HTTPException(
            status_code=500,
            detail=final_state["error"]
        )

    # Sauvegarde dans PostgreSQL
    prompt_record = PromptHistory(
        user_id=current_user.id,
        user_input=body.user_input.strip(),
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
    db.add(prompt_record)
    db.commit()
    db.refresh(prompt_record)
    print(f"💾 Prompt #{prompt_record.id} sauvegardé pour {current_user.email}")

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
@limiter.limit("20/minute")
# Maximum 20 consultations d'historique par minute par IP
async def my_prompts(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retourne les 20 derniers prompts de l'utilisateur connecté.
    🔒 Route protégée : JWT requis.
    """
    prompts = (
        db.query(PromptHistory)
        .filter(PromptHistory.user_id == current_user.id)
        .order_by(PromptHistory.created_at.desc())
        .limit(20)
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