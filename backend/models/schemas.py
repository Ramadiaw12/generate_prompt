# =============================================================================
# Fichier : backend/models/schemas.py
# Rôle    : Définition des tables PostgreSQL (User + PromptHistory)
# Auteur  : DIAWANE Ramatoulaye
#
# Chaque classe Python ici = une table dans PostgreSQL
# Chaque attribut de classe = une colonne dans la table
# =============================================================================

# ── Imports ───────────────────────────────────────────────────────────────────

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
# Column     : définit une colonne dans une table
# Integer    : type entier        → ex: id, user_id
# String     : texte court        → ex: email, nom (longueur limitée)
# Text       : texte long         → ex: prompt complet (pas de limite)
# DateTime   : date + heure       → ex: created_at
# ForeignKey : lien entre tables  → ex: user_id dans PromptHistory

from sqlalchemy.orm import relationship
# relationship : définit le lien Python entre deux tables
# ex: user.prompts → donne tous les prompts d'un user

from datetime import datetime, timezone
# datetime : pour horodater automatiquement (created_at)
# timezone : pour stocker en UTC (bonne pratique internationale)

from db.database import Base
# Base : la classe mère dont héritent toutes nos tables
# Importée depuis database.py


# =============================================================================
# TABLE 1 : users
# Stocke les comptes utilisateurs de la plateforme
# =============================================================================

class User(Base):
    """
    Table 'users' dans PostgreSQL.
    
    Colonnes :
    ┌─────────────────┬──────────────┬─────────────────────────────┐
    │ Colonne         │ Type         │ Description                 │
    ├─────────────────┼──────────────┼─────────────────────────────┤
    │ id              │ INTEGER      │ Clé primaire auto-increment  │
    │ email           │ VARCHAR(255) │ Email unique de l'utilisateur│
    │ hashed_password │ VARCHAR(255) │ Mot de passe hashé (Argon2) │
    │ name            │ VARCHAR(100) │ Prénom / nom d'affichage    │
    │ created_at      │ TIMESTAMP    │ Date de création du compte  │
    └─────────────────┴──────────────┴─────────────────────────────┘
    """

    # Nom de la table dans PostgreSQL
    __tablename__ = "users"

    # ── Colonnes ─────────────────────────────────────────────────────────────

    id = Column(
        Integer,
        primary_key=True,   # clé primaire : identifiant unique de chaque ligne
        index=True,         # index : accélère les recherches par id
        autoincrement=True, # s'incrémente automatiquement : 1, 2, 3, 4...
    )

    email = Column(
        String(255),        # texte de 255 caractères max
        unique=True,        # deux users ne peuvent pas avoir le même email
        nullable=False,     # obligatoire : on ne peut pas créer un user sans email
        index=True,         # index : accélère les recherches par email (login)
    )

    hashed_password = Column(
        String(255),
        nullable=False,     # obligatoire : pas de compte sans mot de passe
        # On ne stocke JAMAIS le mot de passe en clair
        # On stocke le hash Argon2 généré par auth/router.py
    )

    name = Column(
        String(100),
        nullable=True,      # optionnel : un user peut s'inscrire sans donner son nom
        default="",         # valeur par défaut : chaîne vide
    )

    created_at = Column(
        DateTime,
        # default : valeur automatique à l'insertion
        # datetime.now(timezone.utc) = heure actuelle en UTC
        # On utilise UTC pour éviter les problèmes de fuseau horaire
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relation avec PromptHistory ───────────────────────────────────────────

    prompts = relationship(
        "PromptHistory",        # nom de la classe liée
        back_populates="user",  # attribut correspondant dans PromptHistory
        cascade="all, delete",  # si on supprime un user → ses prompts sont supprimés
        lazy="select",          # les prompts sont chargés uniquement quand on y accède
    )
    # Utilisation :
    #   user = db.query(User).first()
    #   user.prompts → liste de tous ses PromptHistory

    def __repr__(self):
        # Représentation lisible pour le debug
        return f"<User id={self.id} email={self.email}>"


# =============================================================================
# TABLE 2 : prompt_history
# Stocke chaque prompt généré par chaque utilisateur
# =============================================================================

class PromptHistory(Base):
    """
    Table 'prompt_history' dans PostgreSQL.
    
    Colonnes :
    ┌──────────────┬──────────────┬──────────────────────────────────────┐
    │ Colonne      │ Type         │ Description                          │
    ├──────────────┼──────────────┼──────────────────────────────────────┤
    │ id           │ INTEGER      │ Clé primaire auto-increment           │
    │ user_id      │ INTEGER      │ Référence vers users.id (FK)          │
    │ user_input   │ TEXT         │ Ce que l'utilisateur a saisi          │
    │ intent       │ TEXT         │ Intention détectée par l'agent        │
    │ domain       │ VARCHAR(50)  │ Domaine détecté (code, redaction...)  │
    │ complexity   │ VARCHAR(20)  │ Complexité (simple, medium, complex)  │
    │ role         │ TEXT         │ Section Rôle générée                  │
    │ context      │ TEXT         │ Section Contexte générée              │
    │ task         │ TEXT         │ Section Tâche générée                 │
    │ output_format│ TEXT         │ Section Format de sortie générée      │
    │ constraints  │ TEXT         │ Section Contraintes générée           │
    │ full_prompt  │ TEXT         │ Prompt final assemblé                 │
    │ created_at   │ TIMESTAMP    │ Date de génération                    │
    └──────────────┴──────────────┴──────────────────────────────────────┘
    """

    __tablename__ = "prompt_history"

    # ── Colonnes ─────────────────────────────────────────────────────────────

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),  # clé étrangère : lie ce prompt à un user
        nullable=False,          # obligatoire : un prompt appartient toujours à un user
        index=True,              # index : accélère "donne-moi tous les prompts du user X"
    )
    # ForeignKey("users.id") signifie :
    # "la valeur de user_id doit exister dans la colonne id de la table users"
    # PostgreSQL refuse d'insérer un prompt avec un user_id inexistant → sécurité

    user_input = Column(
        Text,           # Text = pas de limite de longueur (contrairement à String)
        nullable=False, # obligatoire : on a toujours un input utilisateur
    )

    # ── Résultats de l'analyse (Node 1 : analyze_input) ──────────────────────

    intent = Column(Text, nullable=True, default="")
    # Ce que l'utilisateur veut accomplir
    # ex: "Créer un assistant pour déboguer du code Python"

    domain = Column(String(50), nullable=True, default="autre")
    # Domaine détecté parmi : code, redaction, analyse, image, data, education, business, autre

    complexity = Column(String(20), nullable=True, default="medium")
    # Niveau de complexité : simple, medium, complex

    # ── Sections structurées (Node 2 : structure_prompt) ─────────────────────

    role = Column(Text, nullable=True, default="")
    # Le rôle / persona que l'IA doit adopter

    context = Column(Text, nullable=True, default="")
    # Le contexte et les informations de fond

    task = Column(Text, nullable=True, default="")
    # La tâche précise à accomplir

    output_format = Column(Text, nullable=True, default="")
    # Le format attendu de la réponse

    constraints = Column(Text, nullable=True, default="")
    # Les contraintes et limites

    # ── Prompt final (Node 3 : refine_output) ────────────────────────────────

    full_prompt = Column(
        Text,
        nullable=True,
        default="",
        # Le prompt complet, assemblé et raffiné, prêt à l'emploi
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        # Horodatage automatique en UTC à chaque génération
    )

    # ── Relation avec User ────────────────────────────────────────────────────

    user = relationship(
        "User",                     # nom de la classe liée
        back_populates="prompts",   # attribut correspondant dans User
    )
    # Utilisation :
    #   prompt = db.query(PromptHistory).first()
    #   prompt.user → l'objet User propriétaire de ce prompt

    def __repr__(self):
        return f"<PromptHistory id={self.id} user_id={self.user_id} domain={self.domain}>"