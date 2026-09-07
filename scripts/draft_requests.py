"""Generate access-request drafts once per company, or review existing requests."""

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app import models  # noqa: F401
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.gdpr_request_generator.service import generate_request
from app.models.company import Company
from app.models.gdpr_request import GdprRequest


def generate_missing(db, settings):
    if not settings.privacy_user_full_name or not settings.privacy_user_preferred_email:
        raise ValueError("Configure PRIVACY_USER_FULL_NAME e PRIVACY_USER_PREFERRED_EMAIL.")
    for company in db.scalars(select(Company).order_by(Company.id)).all():
        existing = db.scalar(select(GdprRequest.id).where(
            GdprRequest.company_id == company.id,
            GdprRequest.request_type == "article_15_access",
        ).limit(1))
        if existing is not None:
            print(f"{company.name}: pedido existente #{existing}; preservado.")
            continue
        request = generate_request(db, company, settings, "article_15_access", None, True)
        print(f"{company.name}: rascunho #{request.id} criado.")


def review(db, request_id=None):
    query = select(GdprRequest).order_by(GdprRequest.id)
    if request_id is not None:
        query = query.where(GdprRequest.id == request_id)
    requests = db.scalars(query).all()
    if not requests:
        raise ValueError("Nenhum pedido encontrado.")
    for request in requests:
        company = request.company
        resolution = request.controller_resolution
        method = resolution.request_method if resolution else company.request_method
        contact = (resolution.dpo_contact if resolution else None) or company.dpo_contact or company.privacy_email
        portal = (resolution.privacy_request_url if resolution else None) or company.privacy_request_url
        print(f"\n{'=' * 60}\nPedido #{request.id} | {company.name} | {request.status}")
        print(f"Canal registrado: {method or 'unknown'}")
        print(f"Contato registrado (revisar): {contact or 'NAO ENCONTRADO'}")
        print(f"Formulario/portal: {portal or 'NAO ENCONTRADO'}")
        if method not in {'email', 'unknown', None}:
            print("Este canal exige formulario/portal; envio por email indisponivel.")
        elif not contact or '@' not in contact:
            print("Envio por email indisponivel: falta destinatario.")
        print(f"Assunto: {request.subject}\n\n{request.body_text}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["generate", "review", "approve", "send"])
    parser.add_argument("--id", type=int, help="ID do pedido revisado.")
    args = parser.parse_args()
    if args.action == "generate" and args.id is not None:
        parser.error("generate opera sobre todas as empresas; omita --id")
    if args.action in {"approve", "send"} and args.id is None:
        parser.error("Informe --id para autorizar ou enviar um pedido especifico")
    try:
        with SessionLocal() as db:
            if args.action == "generate":
                generate_missing(db, get_settings())
                print("\nRascunhos prontos. Nenhum pedido aprovado ou enviado.")
            elif args.action == "review":
                review(db, args.id)
            else:
                perform_action(db, get_settings(), args.action, args.id)
    except ValueError as error:
        raise SystemExit(str(error)) from error


def perform_action(db, settings, action, request_id):
    request = db.get(GdprRequest, request_id)
    if request is None:
        raise ValueError("Pedido nao encontrado.")
    expected = "DRAFT" if action == "approve" else "APPROVED"
    if request.status != expected:
        raise ValueError(f"Estado atual: {request.status}. Esta acao exige {expected}.")
    if action == "send":
        # Do not trigger interactive OAuth inside the API process on the NUC.
        from google.oauth2.credentials import Credentials
        from app.gmail_delivery import GMAIL_SEND_SCOPE

        token_path = Path(settings.gmail_oauth_send_token_file)
        if not token_path.is_file():
            raise ValueError("Falta autorizar o Gmail para envio (gmail_send_token.json). Nada enviado.")
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path))
        except (ValueError, KeyError) as error:
            raise ValueError("Token de envio Gmail invalido. Nada enviado.") from error
        if not credentials.has_scopes([GMAIL_SEND_SCOPE]) or not (credentials.valid or credentials.refresh_token):
            raise ValueError("Renove a autorizacao Gmail com permissao de envio. Nada enviado.")
        resolution = request.controller_resolution
        method = resolution.request_method if resolution else request.company.request_method
        contact = (resolution.dpo_contact if resolution else None) or request.company.dpo_contact or request.company.privacy_email
        if method not in {"email", "unknown", None} or not contact or '@' not in contact:
            raise ValueError("Pedido sem canal de email disponivel. Revise o contato/formulario.")
    endpoint = "approve" if action == "approve" else "send-email"
    call = Request(
        f"http://127.0.0.1:8000/requests/{request_id}/{endpoint}",
        method="POST", data=b"",
        headers={"Authorization": "Bearer " + settings.privacy_api_token},
    )
    try:
        with urlopen(call, timeout=120) as response:
            result = json.load(response)
    except HTTPError as error:
        raise ValueError(f"HTTP {error.code}: {error.read().decode(errors='replace')}") from error
    except (URLError, TimeoutError) as error:
        raise ValueError("Sem confirmacao da API. Antes de repetir envio, confira o pedido e a pasta Enviados no Gmail.") from error
    print(f"Pedido #{request_id}: {result['status']}")


if __name__ == "__main__":
    main()
