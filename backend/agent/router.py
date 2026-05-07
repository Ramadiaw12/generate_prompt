# Fichier : backend/agent/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List

from db.database import get_session
from auth.models import User, PromptHistory
from auth.jwt import get_current_user
from backend.models.schemas import PromptRequest, PromptResponse, PromptSection, HistoryItemOut
from agent.graph import prompt_graph

# Importation des bibliothèques nécessaires pour l'agent LangChain
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI 
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.messages import HumanMessage
import asyncio
from IPython.display import Markdown

router = APIRouter(prefix="/prompt", tags=["prompt"])


# ── Génération ────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=PromptResponse)
async def generate_prompt(
    body: PromptRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Lance le graphe LangGraph avec la saisie du user.
    Sauvegarde le résultat en base et le retourne.
    """
    if not body.user_input.strip():
        raise HTTPException(status_code=400, detail="La saisie ne peut pas être vide")

    # ── Exécution du graphe ───────────────────────────────────────────────────
    initial_state = {
        "user_input": body.user_input,
        "intent": None,
        "domain": None,
        "complexity": None,
        "role": None,
        "context": None,
        "task": None,
        "output_format": None,
        "constraints": None,
        "full_prompt": None,
        "error": None,
    }

    final_state = await prompt_graph.ainvoke(initial_state)

    if final_state.get("error"):
        raise HTTPException(status_code=500, detail=final_state["error"])

    # ── Sauvegarde en base ────────────────────────────────────────────────────
    history = PromptHistory(
        user_id=current_user.id,
        raw_input=body.user_input,
        role=final_state.get("role", ""),
        context=final_state.get("context", ""),
        task=final_state.get("task", ""),
        output_format=final_state.get("output_format", ""),
        constraints=final_state.get("constraints", ""),
        full_prompt=final_state.get("full_prompt", ""),
    )
    session.add(history)
    session.commit()
    session.refresh(history)

    # ── Réponse ───────────────────────────────────────────────────────────────
    return PromptResponse(
        sections=PromptSection(
            role=final_state.get("role", ""),
            context=final_state.get("context", ""),
            task=final_state.get("task", ""),
            output_format=final_state.get("output_format", ""),
            constraints=final_state.get("constraints", ""),
            full_prompt=final_state.get("full_prompt", ""),
        ),
        history_id=history.id,
    )


# ── Historique ────────────────────────────────────────────────────────────────

@router.get("/history", response_model=List[HistoryItemOut])
async def get_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Retourne l'historique des prompts générés par le user connecté."""
    items = session.exec(
        select(PromptHistory)
        .where(PromptHistory.user_id == current_user.id)
        .order_by(PromptHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return items


@router.delete("/history/{item_id}")
async def delete_history_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Supprime un item de l'historique (appartenant au user connecté)."""
    item = session.get(PromptHistory, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Item introuvable")
    session.delete(item)
    session.commit()
    return {"message": "Supprimé"}
