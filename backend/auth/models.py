# Fichier : backend/auth/models.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime


class User(SQLModel, table=True):
    """Utilisateur authentifié via OAuth."""
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    avatar_url: Optional[str] = None
    provider: str                          # "google" | "github"
    provider_id: str = Field(index=True)   # ID renvoyé par le provider

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relation vers l'historique
    prompts: List["PromptHistory"] = Relationship(back_populates="user")


class PromptHistory(SQLModel, table=True):
    """Historique des prompts générés par un utilisateur."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    raw_input: str           # Ce que l'utilisateur a saisi
    role: str                # Section générée : rôle
    context: str             # Section générée : contexte
    task: str                # Section générée : tâche
    output_format: str       # Section générée : format de sortie
    constraints: str         # Section générée : contraintes
    full_prompt: str         # Prompt final complet assemblé

    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="prompts")
