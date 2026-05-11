# =============================================================================
# Fichier : Dockerfile
# Rôle    : Conteneur Docker pour le backend FastAPI
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

FROM python:3.12-slim

LABEL maintainer="DIAWANE Ramatoulaye"

# Variables d'environnement système
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Répertoire de travail
WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python directement avec pip
# (plus simple que uv dans Docker)
COPY pyproject.toml uv.lock ./

# Installe uv puis les dépendances dans le système Python (pas dans un venv)
RUN pip install uv && \
    uv export --no-dev --format requirements-txt > requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY backend/ ./

# Port exposé
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ✅ Commande corrigée — utilise python -m uvicorn (pas uv run)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]