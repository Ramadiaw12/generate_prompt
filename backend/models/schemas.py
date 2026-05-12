# =============================================================================
# Fichier : backend/models/schemas.py
# Rôle    : Tables PostgreSQL — User + PromptHistory
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from db.database import Base


class User(Base):
    """
    Table 'users' — stocke les comptes utilisateurs.
    Supporte deux types de comptes :
    - auth_provider = "local"  → inscription email/mot de passe
    - auth_provider = "google" → connexion Google OAuth
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    email = Column(String(255), unique=True, nullable=False, index=True)

    hashed_password = Column(
        String(255),
        nullable=True,   # ✅ nullable pour les users Google (pas de mot de passe)
        default="",
    )

    name = Column(String(100), nullable=True, default="")

    picture = Column(
        String(500),
        nullable=True,
        default="",
        # Photo de profil Google
        # Vide pour les comptes classiques
    )

    auth_provider = Column(
        String(20),
        nullable=False,
        default="local",
        # "local"  = compte créé avec email/mot de passe
        # "google" = compte créé via Google OAuth
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relation avec PromptHistory
    prompts = relationship(
        "PromptHistory",
        back_populates="user",
        cascade="all, delete",
    )

    def __repr__(self):
        return f"<User id={self.id} email={self.email} provider={self.auth_provider}>"


class PromptHistory(Base):
    """
    Table 'prompt_history' — sauvegarde chaque prompt généré.
    Liée à la table users via user_id (ForeignKey).
    """
    __tablename__ = "prompt_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    user_input   = Column(Text, nullable=False)
    intent       = Column(Text, nullable=True, default="")
    domain       = Column(String(50), nullable=True, default="autre")
    complexity   = Column(String(20), nullable=True, default="medium")
    role         = Column(Text, nullable=True, default="")
    context      = Column(Text, nullable=True, default="")
    task         = Column(Text, nullable=True, default="")
    output_format = Column(Text, nullable=True, default="")
    constraints  = Column(Text, nullable=True, default="")
    full_prompt  = Column(Text, nullable=True, default="")

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="prompts")

    def __repr__(self):
        return f"<PromptHistory id={self.id} user_id={self.user_id} domain={self.domain}>"