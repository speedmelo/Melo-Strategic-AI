from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
)

router = APIRouter()

# Swagger Authorize vai usar essa rota
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(status_code=401, detail="Token inválido")

    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    return user


@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()

    if existing:
        raise HTTPException(status_code=400, detail="Usuário já existe")

    new_user = User(
        email=user.email,
        password=hash_password(user.password),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Usuário criado com sucesso",
        "user_id": new_user.id,
        "email": new_user.email,
    }


@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user or not db_user.password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    access_token = create_access_token({"sub": str(db_user.id)})

    return {
        "message": "Login OK",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "email": db_user.email,
            "is_pro": db_user.is_pro,
        },
    }


@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # No Swagger, o campo "username" vai receber o email
    db_user = db.query(User).filter(User.email == form_data.username).first()

    if not db_user or not db_user.password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if not verify_password(form_data.password, db_user.password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    access_token = create_access_token({"sub": str(db_user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_pro": current_user.is_pro,
    }