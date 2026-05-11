# =============================================================================
# Fichier : backend/auth/router.py
# Rôle    : Authentification JWT branchée sur PostgreSQL
#           - Inscription (register)
#           - Connexion   (login)
#           - Profil      (me)
# Auteur  : DIAWANE Ramatoulaye
# =============================================================================

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv("../.env")

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from models.schemas import User

# ── Configuration JWT ─────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "changez-moi-en-production")
# Clé secrète pour signer les tokens JWT
# En production : générez avec → openssl rand -hex 32

ALGORITHM = "HS256"
# Algorithme de signature : HMAC avec SHA-256

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
# Durée de validité du token : 7 jours

# ── Initialisation ────────────────────────────────────────────────────────────

router = APIRouter(
    prefix="/auth",   # toutes les routes commencent par /auth
    tags=["auth"],    # groupe dans la doc Swagger
)

pwd_context = CryptContext(
    schemes=["argon2"],   # algorithme de hashage des mots de passe
    deprecated="auto",
)
# Argon2 = standard recommandé pour hasher les mots de passe

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# Lit automatiquement le header : Authorization: Bearer <token>

# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    """Données reçues lors de l'inscription."""
    email: str
    password: str
    name: Optional[str] = ""

class Token(BaseModel):
    """Réponse renvoyée après une connexion réussie."""
    access_token: str
    token_type: str

class UserOut(BaseModel):
    """Données utilisateur renvoyées par /auth/me (sans le mot de passe !)"""
    id: int
    email: str
    name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
        # Permet à Pydantic de lire les attributs SQLAlchemy directement

# ── Fonctions utilitaires ─────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """
    Transforme un mot de passe en clair en hash Argon2.
    On ne stocke JAMAIS le mot de passe en clair dans la DB.
    "monpassword" → "$argon2id$v=19$m=65536..."
    Ce processus est irréversible.
    """
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """
    Vérifie qu'un mot de passe en clair correspond à son hash.
    Utilisé lors du login.
    """
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    """
    Crée un token JWT signé contenant l'email de l'utilisateur.
    Le token expire dans 7 jours.
    Signé avec SECRET_KEY → impossible à falsifier sans la clé.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ── Dépendance : récupérer le user connecté ───────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),  # lit le token dans le header
    db: Session = Depends(get_db),        # ouvre une session PostgreSQL
) -> User:
    """
    Dépendance FastAPI : décode le JWT et retourne l'objet User depuis PostgreSQL.

    Étapes :
    1. Lit le token depuis Authorization: Bearer <token>
    2. Décode et vérifie la signature avec SECRET_KEY
    3. Extrait l'email depuis le token
    4. Charge l'objet User depuis PostgreSQL
    5. Retourne le User si tout est OK, lève une 401 sinon
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré. Veuillez vous reconnecter.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Cherche le user dans PostgreSQL
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user

# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register(
    body: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Crée un nouveau compte utilisateur dans PostgreSQL.

    Étapes :
    1. Vérifie que l'email n'est pas déjà utilisé
    2. Vérifie que le mot de passe fait au moins 6 caractères
    3. Hashe le mot de passe avec Argon2
    4. Insère le nouvel utilisateur dans PostgreSQL
    5. Retourne un message de confirmation
    """

    # Vérifie si l'email existe déjà
    existing_user = db.query(User).filter(User.email == body.email).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Cet email est déjà utilisé. Essayez de vous connecter."
        )

    # Validation du mot de passe
    if len(body.password) < 6:
        raise HTTPException(
            status_code=422,
            detail="Le mot de passe doit contenir au moins 6 caractères."
        )

    # Hashage du mot de passe (on ne stocke JAMAIS le mot de passe en clair)
    hashed = hash_password(body.password)

    # Création de l'objet User SQLAlchemy
    new_user = User(
        email=body.email,
        hashed_password=hashed,
        name=body.name or "",
    )

    # Sauvegarde dans PostgreSQL
    db.add(new_user)       # prépare l'insertion
    db.commit()            # valide la transaction
    db.refresh(new_user)   # recharge depuis DB (récupère l'id auto-généré)

    return {
        "message": "Compte créé avec succès. Bienvenue !",
        "email": new_user.email,
        "id": new_user.id,
    }


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authentifie un utilisateur et retourne un token JWT.

    Étapes :
    1. Cherche l'utilisateur par email dans PostgreSQL
    2. Vérifie le mot de passe avec Argon2
    3. Génère un token JWT signé valide 7 jours
    4. Retourne le token

    Note : OAuth2 utilise "username" pour l'email (standard OAuth2)
    """

    # Cherche le user par email
    user = db.query(User).filter(User.email == form_data.username).first()

    # Vérifie email ET mot de passe ensemble
    # (ne pas révéler si l'email existe ou non → sécurité)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Génère le token JWT
    token = create_access_token(data={"sub": user.email})

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserOut)
async def me(
    current_user: User = Depends(get_current_user)
):
    """
    Retourne les informations du compte connecté.
    Route protégée : nécessite un token JWT valide.
    Le mot de passe haché n'est jamais renvoyé (UserOut l'exclut).
    """
    return current_user