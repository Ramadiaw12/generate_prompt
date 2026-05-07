# Fichier : backend/auth/router.py
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — mettez ces valeurs dans votre .env en production
# ─────────────────────────────────────────────────────────────────────────────
SECRET_KEY = "changez-moi-en-production-avec-openssl-rand-hex-32"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 jours

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: str
    password: str
    name: Optional[str] = ""

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency : décode le JWT et retourne l'email du user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return email
    except JWTError:
        raise credentials_exception

# ─────────────────────────────────────────────────────────────────────────────
# DB SIMULATION — remplacez par votre vraie DB (SQLAlchemy, Supabase…)
# ─────────────────────────────────────────────────────────────────────────────
# Dictionnaire en mémoire pour le développement.
# En production : utilisez database.py avec SQLAlchemy ou une autre DB.
_users_db: dict[str, dict] = {}

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register(body: UserRegister):
    """Crée un nouveau compte utilisateur."""
    if body.email in _users_db:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")

    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="Le mot de passe doit faire au moins 6 caractères.")

    _users_db[body.email] = {
        "email": body.email,
        "name": body.name,
        "hashed_password": hash_password(body.password),
        "created_at": datetime.utcnow().isoformat(),
    }
    return {"message": "Compte créé avec succès.", "email": body.email}


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authentifie un utilisateur et retourne un JWT."""
    user = _users_db.get(form_data.username)

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": user["email"]})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me(current_user: str = Depends(get_current_user)):
    """Retourne les infos du user connecté."""
    user = _users_db.get(current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return {"email": user["email"], "name": user["name"]}
