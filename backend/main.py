# Fichier : backend/main.py

from dotenv import load_dotenv
load_dotenv()  # Charge les variables d'environnement depuis le fichier .env    

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.graph import build_graph
from auth.router import router as auth_router, get_current_user  # ✅ AJOUTÉ

# ─────────────────────────────────────────────────────────────────────────────
# LIFESPAN
# ─────────────────────────────────────────────────────────────────────────────

graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    graph = build_graph()
    print(" Agent graph compilé et prêt.")
    yield
    print(" Arrêt du serveur.")

# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Prompt Engineer API",
    description="Génère des prompts structurés à partir d'une demande utilisateur.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)  #  enregistre /auth/register, /auth/login, /auth/me

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "Prompt Engineer API is running 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy", "graph_ready": graph is not None}

@app.post("/generate-prompt", response_model=PromptResponse)
async def generate_prompt(
    request: PromptRequest,
    current_user: str = Depends(get_current_user)  # route protégée par JWT
):
    if not request.user_input.strip():
        raise HTTPException(status_code=422, detail="Le champ user_input ne peut pas être vide.")

    if graph is None:
        raise HTTPException(status_code=503, detail="Agent non initialisé.")

    initial_state = {
        "user_input": request.user_input.strip(),
        "intent": "", "domain": "", "complexity": "",
        "role": "", "context": "", "task": "",
        "output_format": "", "constraints": "",
        "full_prompt": "", "error": "",
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne de l'agent : {str(e)}")

    if final_state.get("error"):
        raise HTTPException(status_code=500, detail=final_state["error"])

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