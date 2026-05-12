# =============================================================================
# Fichier : backend/auth/router.py
# Rôle    : Authentification JWT + Google OAuth
#           - Inscription classique (register)
#           - Connexion classique   (login)
#           - Connexion Google      (google/login + google/callback)
#           - Profil                (me)
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv("../.env")

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from authlib.integrations.starlette_client import OAuth
# OAuth : bibliothèque qui gère le protocole OAuth2 avec Google
# Elle s'occupe de tout : redirection, échange de token, récupération du profil

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.config import Config

from db.database import get_db
from models.schemas import User

# ── Configuration JWT ─────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "changez-moi-en-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 jours

# ── Configuration Google OAuth ────────────────────────────────────────────────

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://localhost:3000")
# FRONTEND_URL : après le login Google, on redirige l'user vers le frontend

# Configuration Authlib pour Google
config = Config(environ={
    "GOOGLE_CLIENT_ID":     GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
})

oauth = OAuth(config)
oauth.register(
    name="google",
    # URLs officielles de Google pour OAuth2
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        # openid  : authentification
        # email   : récupérer l'email de l'user
        # profile : récupérer le nom et la photo
    },
)

# ── Initialisation ────────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
# Argon2 = algorithme de hashage recommandé pour les mots de passe

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
# auto_error=False : ne pas lever d'erreur si pas de token
# (certaines routes acceptent les deux : token JWT ou Google)

# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    """Données reçues lors de l'inscription classique."""
    email: str
    password: str
    name: Optional[str] = ""

class Token(BaseModel):
    """Token JWT renvoyé après connexion."""
    access_token: str
    token_type: str

class UserOut(BaseModel):
    """Données utilisateur publiques (sans mot de passe)."""
    id: int
    email: str
    name: Optional[str]
    created_at: datetime
    auth_provider: Optional[str]  # "local" ou "google"

    class Config:
        from_attributes = True

# ── Fonctions utilitaires ─────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash un mot de passe avec Argon2. Irréversible."""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Vérifie qu'un mot de passe correspond à son hash."""
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    """
    Crée un token JWT signé valide 7 jours.
    Contient l'email de l'user dans le champ 'sub'.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_or_create_google_user(db: Session, email: str, name: str, picture: str) -> User:
    """
    Récupère un user existant par email ou en crée un nouveau.
    Utilisé après l'authentification Google.

    Si l'user existe déjà (inscription classique) → on le connecte
    Si l'user n'existe pas → on crée un compte automatiquement
    Pas de mot de passe pour les users Google (auth_provider = "google")
    """
    user = db.query(User).filter(User.email == email).first()

    if user:
        # L'user existe → on met à jour son provider si nécessaire
        if user.auth_provider != "google":
            user.auth_provider = "google"
            db.commit()
        return user

    # Crée un nouveau user Google (sans mot de passe)
    new_user = User(
        email=email,
        name=name or email.split("@")[0],
        hashed_password="",          # pas de mot de passe pour Google
        auth_provider="google",      # indique que c'est un compte Google
        picture=picture or "",       # photo de profil Google
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# ── Dépendance : user connecté ────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dépendance FastAPI : vérifie le JWT et retourne l'user depuis PostgreSQL.
    Utilisée dans toutes les routes protégées avec Depends(get_current_user).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré. Veuillez vous reconnecter.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user

# ── ROUTES CLASSIQUES ─────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register(body: UserRegister, db: Session = Depends(get_db)):
    """
    Crée un compte avec email + mot de passe.
    Le mot de passe est hashé avec Argon2 avant stockage.
    """
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")

    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="Le mot de passe doit faire au moins 6 caractères.")

    new_user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name or "",
        auth_provider="local",   # compte classique
        picture="",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Compte créé avec succès !", "email": new_user.email, "id": new_user.id}


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Connexion classique email + mot de passe.
    Retourne un JWT valide 7 jours.
    """
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """
    Retourne les infos du user connecté.
    Route protégée : JWT requis.
    """
    return current_user

# ── ROUTES GOOGLE OAUTH ───────────────────────────────────────────────────────

@router.get("/google/login")
async def google_login(request: Request):
    """
    Étape 1 du flow Google OAuth.
    Redirige l'user vers la page de connexion Google.

    Flow complet :
    1. User clique "Continuer avec Google" → appelle cette route
    2. Cette route redirige vers accounts.google.com
    3. L'user choisit son compte Google
    4. Google redirige vers /auth/google/callback avec un code
    5. On échange le code contre un token Google
    6. On récupère l'email + nom de l'user
    7. On crée/connecte le compte dans PostgreSQL
    8. On génère notre JWT et on redirige vers le frontend
    """
    redirect_uri = request.url_for("google_callback")
    # request.url_for génère automatiquement l'URL de callback
    # Ex: https://promptcraft.today/auth/google/callback

    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """
    Étape 2 du flow Google OAuth — callback.
    Google appelle cette route avec un code d'autorisation.

    On échange ce code contre les infos de l'user.
    """
    try:
        # Échange le code Google contre un token d'accès
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        raise HTTPException(status_code=400, detail="Erreur lors de l'authentification Google.")

    # Récupère les infos du user depuis Google
    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(status_code=400, detail="Impossible de récupérer les informations Google.")

    email   = user_info.get("email")
    name    = user_info.get("name", "")
    picture = user_info.get("picture", "")

    if not email:
        raise HTTPException(status_code=400, detail="Email Google non disponible.")

    # Crée ou récupère le user dans PostgreSQL
    user = get_or_create_google_user(db, email, name, picture)

    # Génère notre JWT
    jwt_token = create_access_token(data={"sub": user.email})

    # Redirige vers le frontend avec le token dans l'URL
    # Le frontend va lire ce token et le stocker dans localStorage
    frontend_url = f"{FRONTEND_URL}?token={jwt_token}&email={email}&name={name}"
    return RedirectResponse(url=frontend_url)