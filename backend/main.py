# =============================================================================
# Fichier : backend/main.py
# Rôle    : Point d'entrée FastAPI
#           - Génération de prompts (Free + Pro)
#           - Optimisation de prompts (Pro uniquement)
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

from dotenv import load_dotenv
load_dotenv("../.env")

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from agent.graph import build_graph
from agent.nodes import optimize_prompt
# On appelle optimize_prompt directement — pas via le graph génération
# car c'est un pipeline séparé

from auth.router import router as auth_router, get_current_user
from db.database import get_db, create_tables
from models.schemas import PromptHistory, User

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Lifespan ──────────────────────────────────────────────────────────────────
graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    create_tables()
    graph = build_graph()
    print("✅ Tables PostgreSQL créées / vérifiées.")
    print("✅ Agent graph compilé et prêt.")
    yield
    print("🛑 Arrêt du serveur.")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PromptCraft API",
    description="Génère et optimise des prompts via un pipeline LangGraph.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "changez-moi"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://prompt-craft26.netlify.app",
        "https://promptcraft.today",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router)

# ── Schémas ───────────────────────────────────────────────────────────────────

class PromptRequest(BaseModel):
    """Données pour générer un prompt."""
    user_input: str

class PromptResponse(BaseModel):
    """Résultat de la génération."""
    intent: str
    domain: str
    complexity: str
    role: str
    context: str
    task: str
    output_format: str
    constraints: str
    full_prompt: str

class OptimizeRequest(BaseModel):
    """
    Données pour optimiser un prompt existant.
    Fonctionnalité PRO uniquement.
    """
    prompt_to_optimize: str  # le prompt existant soumis par l'utilisateur

class OptimizeResponse(BaseModel):
    """
    Résultat de l'optimisation.
    Contient le prompt amélioré + scores + analyse.
    """
    score_before:      int          # score qualité avant (0-100)
    score_after:       int          # score qualité après (0-100)
    weaknesses:        List[str]    # faiblesses détectées
    improvements:      List[str]    # améliorations apportées
    optimized_prompt:  str          # prompt amélioré prêt à l'emploi

# ── Routes publiques ──────────────────────────────────────────────────────────

@app.get("/")
@limiter.limit("30/minute")
def root(request: Request):
    return {"status": "ok", "message": "PromptCraft API v3.0 🚀", "version": "3.0.0"}

@app.get("/health")
@limiter.limit("30/minute")
def health(request: Request):
    return {"status": "healthy", "graph_ready": graph is not None, "database": "postgresql"}

# ── Route : Génération de prompt (Free + Pro) ─────────────────────────────────

@app.post("/generate-prompt", response_model=PromptResponse)
@limiter.limit("10/minute")
async def generate_prompt(
    request: Request,
    body: PromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Génère un prompt structuré en 3 étapes via LangGraph.
    Disponible pour tous les utilisateurs (Free + Pro).
    🔒 JWT requis · ⏱️ 10 req/min par IP
    """
    if not body.user_input.strip():
        raise HTTPException(status_code=422, detail="Le champ user_input ne peut pas être vide.")
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent non initialisé.")

    initial_state = {
        "user_input": body.user_input.strip(),
        "intent": "", "domain": "", "complexity": "",
        "role": "", "context": "", "task": "",
        "output_format": "", "constraints": "",
        "full_prompt": "", "error": "",
        # Champs optimisation (vides pour ce pipeline)
        "prompt_to_optimize": None,
        "score_before": None, "score_after": None,
        "weaknesses": None, "improvements": None,
        "optimized_prompt": None,
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur agent : {str(e)}")

    if final_state.get("error"):
        raise HTTPException(status_code=500, detail=final_state["error"])

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

# ── Route : Optimisation de prompt (PRO uniquement) ───────────────────────────

@app.post("/optimize-prompt", response_model=OptimizeResponse)
@limiter.limit("5/minute")
async def optimize_prompt_route(
    request: Request,
    body: OptimizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyse un prompt existant et génère une version améliorée.

    🔒 FONCTIONNALITÉ PRO UNIQUEMENT
    ⏱️ Rate limit : 5 optimisations/minute par IP

    Retourne :
    - Score avant/après (0-100)
    - Faiblesses détectées
    - Améliorations apportées
    - Prompt optimisé prêt à l'emploi

    Note : La vérification du plan Pro sera activée après
    l'intégration de Lemon Squeezy (prochaine étape).
    Pour l'instant, route accessible à tous les users connectés.
    """
    if not body.prompt_to_optimize.strip():
        raise HTTPException(
            status_code=422,
            detail="Le champ prompt_to_optimize ne peut pas être vide."
        )

    if len(body.prompt_to_optimize) < 10:
        raise HTTPException(
            status_code=422,
            detail="Le prompt est trop court pour être analysé (minimum 10 caractères)."
        )

    # Construit l'état initial pour le node optimize_prompt
    initial_state = {
        "user_input": "",
        "intent": "", "domain": "", "complexity": "",
        "role": "", "context": "", "task": "",
        "output_format": "", "constraints": "",
        "full_prompt": "", "error": "",
        # Champ clé : le prompt à optimiser
        "prompt_to_optimize": body.prompt_to_optimize.strip(),
        "score_before": None, "score_after": None,
        "weaknesses": None, "improvements": None,
        "optimized_prompt": None,
    }

    # Appel direct au node optimize_prompt (pas via le graph génération)
    try:
        result_state = optimize_prompt(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur optimisation : {str(e)}")

    if result_state.get("error"):
        raise HTTPException(status_code=500, detail=result_state["error"])

    print(f"🔧 Prompt optimisé pour {current_user.email} — score {result_state.get('score_before')} → {result_state.get('score_after')}")

    return OptimizeResponse(
        score_before=result_state.get("score_before", 50),
        score_after=result_state.get("score_after", 85),
        weaknesses=result_state.get("weaknesses", []),
        improvements=result_state.get("improvements", []),
        optimized_prompt=result_state.get("optimized_prompt", ""),
    )

# ── Route : Historique des prompts ───────────────────────────────────────────

@app.get("/my-prompts")
@limiter.limit("20/minute")
async def my_prompts(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retourne les 20 derniers prompts générés par l'utilisateur connecté.
    🔒 JWT requis.
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

# ── Route : Infos plan utilisateur ───────────────────────────────────────────

@app.get("/my-plan")
@limiter.limit("30/minute")
async def my_plan(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Retourne le plan actuel de l'utilisateur.
    Sera enrichi après intégration Lemon Squeezy.
    """
    return {
        "email": current_user.email,
        "plan": getattr(current_user, 'plan', 'free'),
        "features": {
            "generate_prompt": True,       # Free + Pro
            "optimize_prompt": True,       # Pro uniquement (à activer)
            "export": False,               # Pro uniquement (à venir)
            "templates": False,            # Pro uniquement (à venir)
            "batch": False,                # Expert uniquement (à venir)
        }
    }