import io
from typing import List

import fitz
import spacy
import stripe
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.db.database import Base, engine, get_db, SessionLocal
from app.models.user import User
from app.models.audit_log import AuditLog
from app.routes import auth
from app.routes.auth import get_current_user

# cria tabelas
Base.metadata.create_all(bind=engine)

stripe.api_key = settings.STRIPE_SECRET_KEY

app = FastAPI(title=settings.APP_NAME)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])

limiter = Limiter(key_func=get_remote_address)
logger.add("logs/melo_system.log", rotation="10 days")

nlp = spacy.load("pt_core_news_sm")

FREE_AUDIT_LIMIT = 1


@app.get("/")
def root():
    return {"message": "Melo Strategic AI rodando 🚀"}


class RiskOutput(BaseModel):
    clausula: str
    nivel: str
    insight: str
    sugestao: str


class CheckoutResponse(BaseModel):
    url: str


MAPA_INTELIGENCIA = {
    "multa": (
        "CRÍTICO",
        "Risco de liquidez severo.",
        "Negociar teto de 10% do valor total.",
    ),
    "foro": (
        "ALTO",
        "Insegurança jurídica territorial.",
        "Cláusula de Arbitragem Internacional.",
    ),
    "prazo": (
        "MÉDIO",
        "Gargalo operacional.",
        "Adicionar multa diária por atraso.",
    ),
    "exclusividade": (
        "CRÍTICO",
        "Bloqueio de escalabilidade.",
        "Remover ou limitar a 12 meses.",
    ),
}


# Função dedicada e síncrona para extração de texto do arquivo
def extract_text_from_file(content: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        texto = ""
        with fitz.open(stream=io.BytesIO(content), filetype="pdf") as doc:
            for page in doc:
                texto += page.get_text()
        return texto
    return content.decode("utf-8", errors="ignore")


# Função dedicada e síncrona para a inferência da IA com spaCy
def process_nlp_and_find_risks(texto: str) -> List[RiskOutput]:
    doc_nlp = nlp(texto)
    findings = []

    for sent in doc_nlp.sents:
        s_lower = sent.text.lower()
        for key, (nivel, insight, sug) in MAPA_INTELIGENCIA.items():
            if key in s_lower:
                findings.append(
                    RiskOutput(
                        clausula=sent.text.strip()[:400],
                        nivel=nivel,
                        insight=insight,
                        sugestao=sug,
                    )
                )
    return findings


@app.post("/billing/checkout", response_model=CheckoutResponse)
async def create_checkout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "brl",
                        "product_data": {
                            "name": "Melo AI - Plano Global Enterprise"
                        },
                        "unit_amount": 29900,
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{settings.FRONTEND_URL}/success",
            cancel_url=f"{settings.FRONTEND_URL}/cancel",
            customer_email=current_user.email,
        )
        return {"url": session.url}
    except Exception as e:
        logger.error(f"Erro Stripe: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro no processamento de pagamento",
        )


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Stripe signature ausente")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Assinatura inválida")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")

        if customer_email:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.email == customer_email).first()
                if user:
                    user.is_pro = True
                    db.commit()
                    logger.info(f"Usuário {customer_email} ativado como PRO")
                else:
                    logger.warning(f"Usuário não encontrado para o email {customer_email}")
            finally:
                db.close()

    return JSONResponse({"status": "success"})


@app.post("/dev/activate-pro")
def activate_pro(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = current_user
    user.is_pro = True
    db.commit()

    return {
        "message": "Usuário ativado como PRO (modo dev)",
        "email": user.email
    }


@app.post("/ai/audit", response_model=List[RiskOutput])
@limiter.limit("3/minute")
async def perform_audit(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = current_user

        # Trial grátis limitado
        if not user.is_pro:
            audit_count = db.query(AuditLog).filter(AuditLog.user_id == user.id).count()

            if audit_count >= FREE_AUDIT_LIMIT:
                raise HTTPException(
                    status_code=403,
                    detail="Limite gratuito atingido. Assine o plano PRO para continuar."
                )

        content = await file.read()

        texto = await run_in_threadpool(extract_text_from_file, content, file.filename)

        if not texto.strip():
            raise HTTPException(
                status_code=400,
                detail="Não foi possível extrair texto do arquivo enviado."
            )

        findings = await run_in_threadpool(process_nlp_and_find_risks, texto)

        new_log = AuditLog(
            user_id=user.id,
            filename=file.filename,
            risks_found=len(findings),
        )
        db.add(new_log)
        db.commit()

        logger.info(f"Auditoria concluída para {user.email}: {len(findings)} riscos.")
        return findings

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Erro no processamento da IA: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno no processamento do documento."
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)