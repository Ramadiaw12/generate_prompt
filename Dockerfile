# =============================================================================
# Fichier : Dockerfile
# Rôle    : Conteneur Docker pour le backend FastAPI
# Auteur  : DIAWANE Ramatoulaye
#
# Un Dockerfile = la recette pour construire une "image" Docker
# Une image = une boîte autonome qui contient tout ce qu'il faut pour
# faire tourner l'app (Python, dépendances, code source)
# =============================================================================

# ── Image de base ─────────────────────────────────────────────────────────────
FROM python:3.12-slim
# On part d'une image Python 3.12 officielle ultra-légère (slim)
# "slim" = sans les outils inutiles → image plus petite et plus sécurisée
# Alternative : python:3.12 (complète mais ~900MB vs ~130MB pour slim)

# ── Métadonnées ───────────────────────────────────────────────────────────────
LABEL maintainer="DIAWANE Ramatoulaye"
LABEL version="2.0.0"
LABEL description="Prompt Engineer API — FastAPI + LangGraph + PostgreSQL"

# ── Variables d'environnement système ────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1
# Empêche Python de créer des fichiers .pyc dans le conteneur
# Économise de l'espace disque

ENV PYTHONUNBUFFERED=1
# Force Python à afficher les logs immédiatement (pas de buffering)
# Essentiel pour voir les logs en temps réel dans Docker

ENV PYTHONPATH=/app
# Indique à Python où chercher les modules
# Permet d'importer "from agent.graph import ..." depuis n'importe où

# ── Répertoire de travail ─────────────────────────────────────────────────────
WORKDIR /app
# Tous les fichiers seront dans /app à l'intérieur du conteneur
# Équivalent de "cd /app" — toutes les commandes suivantes s'exécutent ici

# ── Installation des dépendances système ─────────────────────────────────────
RUN apt-get update && apt-get install -y \
    gcc \
    # compilateur C — nécessaire pour psycopg2 (driver PostgreSQL)
    libpq-dev \
    # headers PostgreSQL — nécessaires pour compiler psycopg2
    curl \
    # outil HTTP — utilisé pour le health check
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
    # Nettoie le cache apt → réduit la taille de l'image

# ── Installation de uv (gestionnaire de paquets) ─────────────────────────────
RUN pip install uv
# uv est notre gestionnaire de paquets Python
# On l'installe dans le conteneur pour reproduire l'environnement local

# ── Copie des fichiers de dépendances ─────────────────────────────────────────
COPY pyproject.toml uv.lock ./
# On copie UNIQUEMENT les fichiers de dépendances en premier
# Pourquoi ? Docker met en cache chaque étape (layer)
# Si on copie tout le code d'abord, le cache est invalidé à chaque changement de code
# En copiant pyproject.toml en premier, les dépendances ne sont réinstallées
# que si pyproject.toml change → builds beaucoup plus rapides

# ── Installation des dépendances Python ───────────────────────────────────────
RUN uv sync --frozen --no-dev
# --frozen : utilise exactement les versions de uv.lock (reproductibilité)
# --no-dev : n'installe pas les dépendances de développement (plus léger)

# ── Copie du code source ───────────────────────────────────────────────────────
COPY backend/ ./
# Copie tout le dossier backend/ dans /app du conteneur
# Cette étape est après l'installation des dépendances pour profiter du cache

# ── Port exposé ───────────────────────────────────────────────────────────────
EXPOSE 8000
# Indique que le conteneur écoute sur le port 8000
# C'est documentaire — docker-compose fait le vrai binding de ports

# ── Health check ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
# Docker vérifie toutes les 30s que l'API répond sur /health
# --interval   : vérifie toutes les 30 secondes
# --timeout    : attend max 10 secondes la réponse
# --start-period: attend 40s au démarrage avant de commencer les checks
# --retries    : 3 échecs consécutifs → conteneur marqué "unhealthy"

# ── Commande de démarrage ─────────────────────────────────────────────────────
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# Démarre le serveur FastAPI
# --host 0.0.0.0 : écoute sur toutes les interfaces réseau
#                  (nécessaire dans Docker, sinon inaccessible depuis l'extérieur)
# --port 8000    : port d'écoute
# Pas de --reload en production (reload = dev uniquement)