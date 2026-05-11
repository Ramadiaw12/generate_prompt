# =============================================================================
# Fichier : backend/db/database.py
# Rôle    : Connexion à PostgreSQL + session de base de données
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

# ── Imports ──────────────────────────────────────────────────────────────────

import os                          # pour lire les variables d'environnement
from dotenv import load_dotenv     # pour charger le fichier .env

from sqlalchemy import create_engine
# create_engine : crée le "moteur" qui fait le pont entre Python et PostgreSQL

from sqlalchemy.ext.declarative import declarative_base
# declarative_base : la classe mère dont vont hériter toutes nos tables

from sqlalchemy.orm import sessionmaker, Session
# sessionmaker : fabrique de sessions (une session = une conversation avec la DB)
# Session      : le type de la session (utilisé pour les annotations de type)

from typing import Generator
# Generator : type Python pour les fonctions qui utilisent "yield"

# ── Chargement des variables d'environnement ─────────────────────────────────

load_dotenv("../.env")
# On charge le fichier .env AVANT de lire DATABASE_URL
# Sans ça, os.getenv retournerait None

# ── URL de connexion à PostgreSQL ─────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")
# On lit DATABASE_URL depuis le .env
# Format attendu : postgresql://user:password@host:port/dbname
# Exemple local  : postgresql://postgres:monpassword@localhost:5432/promptcraft
# Exemple Railway: postgresql://postgres:xxx@containers-us-west-xxx.railway.app:5432/railway

if not DATABASE_URL:
    # Si la variable n'est pas définie, on arrête tout immédiatement
    # Mieux vaut crasher au démarrage que d'avoir une erreur bizarre plus tard
    raise ValueError(
        "❌ DATABASE_URL manquante dans le fichier .env\n"
        "Format : postgresql://user:password@host:port/dbname"
    )

# ── Création du moteur SQLAlchemy ─────────────────────────────────────────────

engine = create_engine(
    DATABASE_URL,
    # pool_pre_ping : vérifie que la connexion est vivante avant chaque requête
    # Évite les erreurs "connexion perdue" après une longue inactivité
    pool_pre_ping=True,

    # pool_size : nombre de connexions maintenues ouvertes en permanence
    # 5 connexions simultanées suffisent largement pour commencer
    pool_size=5,

    # max_overflow : connexions supplémentaires autorisées en cas de pic
    # Total max = pool_size + max_overflow = 5 + 10 = 15 connexions
    max_overflow=10,

    # echo : affiche toutes les requêtes SQL dans le terminal
    # True = utile pour déboguer | False = silencieux en production
    echo=False,
)

# ── Classe de base pour les modèles ──────────────────────────────────────────

Base = declarative_base()
# Toutes nos tables (User, PromptHistory...) vont hériter de cette classe
# C'est ce qui permet à SQLAlchemy de les "connaître" et de les créer

# ── Fabrique de sessions ──────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    bind=engine,        # on associe la session à notre moteur PostgreSQL
    autocommit=False,   # on gère nous-mêmes les commits (plus sûr)
    autoflush=False,    # on gère nous-mêmes les flush (plus de contrôle)
)
# SessionLocal est une "classe" qu'on instancie pour ouvrir une session
# Exemple : db = SessionLocal() → ouvre une connexion à PostgreSQL

# ── Fonction de création des tables ──────────────────────────────────────────

def create_tables():
    """
    Crée toutes les tables dans PostgreSQL si elles n'existent pas encore.
    
    Cette fonction est appelée une seule fois au démarrage du serveur
    dans le lifespan de FastAPI (main.py).
    
    Si une table existe déjà, SQLAlchemy la laisse intacte —
    vos données ne sont jamais effacées.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Tables PostgreSQL créées / vérifiées.")

# ── Dépendance FastAPI — session par requête ──────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    Dépendance FastAPI : fournit une session DB pour chaque requête HTTP.
    
    Fonctionnement :
    1. FastAPI appelle cette fonction avant chaque route qui en a besoin
    2. Une session est ouverte (db = SessionLocal())
    3. La session est passée à la route via Depends(get_db)
    4. Après la requête, la session est TOUJOURS fermée (finally)
       → même si une erreur survient, la connexion est libérée
    
    Utilisation dans une route :
        @app.get("/exemple")
        def ma_route(db: Session = Depends(get_db)):
            users = db.query(User).all()
            return users
    """
    db = SessionLocal()   # on ouvre une session (connexion à PostgreSQL)
    try:
        yield db          # on passe la session à la route FastAPI
    finally:
        db.close()        # on ferme TOUJOURS la session après usage
        # "finally" = s'exécute même si une exception est levée