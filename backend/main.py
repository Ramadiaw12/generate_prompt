# =============================================================================
# Fichier : backend/main.py
# Rôle    : Point d'entrée FastAPI
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

from dotenv import load_dotenv
load_dotenv("../.env")

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
# SessionMiddleware : OBLIGATOIRE pour Google OAuth
# Authlib stocke l'état OAuth dans la session pour éviter les attaques CSRF

from pydantic import BaseModel
from sqlalchemy.orm import Session

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from agent.graph import build_graph
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
    description="Génère des prompts structurés via un pipeline LangGraph.",
    version="2.1.0",
    lifespan=lifespan,
)

# ⚠️ SessionMiddleware DOIT être avant CORSMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "changez-moi"),
    # Utilisé pour chiffrer la session OAuth — même clé que JWT
)

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
    # allow_credentials=True : nécessaire pour les cookies de session OAuth
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Routes auth
app.include_router(auth_router)

# ── Schémas ───────────────────────────────────────────────────────────────────

class PromptRequest(BaseModel):
    user_input: str

class PromptResponse(BaseModel):
    intent: str
    domain: str
    complexity: str
    role: str
    context: str
    task: str
    output_format: str
    constraints: str
    full_prompt: str

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
@limiter.limit("30/minute")
def root(request: Request):
    return {"status": "ok", "message": "PromptCraft API v2.1 🚀"}

@app.get("/health")
@limiter.limit("30/minute")
def health(request: Request):
    return {"status": "healthy", "graph_ready": graph is not None, "database": "postgresql"}

@app.post("/generate-prompt", response_model=PromptResponse)
@limiter.limit("10/minute")
async def generate_prompt(
    request: Request,
    body: PromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Génère un prompt structuré en 3 étapes.
    🔒 Route protégée : JWT requis.
    ⏱️ Rate limit : 10 requêtes/minute par IP.
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


@app.get("/my-prompts")
@limiter.limit("20/minute")
async def my_prompts(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retourne les 20 derniers prompts de l'user connecté.
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