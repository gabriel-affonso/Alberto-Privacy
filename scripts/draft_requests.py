"""Generate access-request drafts once per company, or review existing requests.

The CLI's ``generate`` action is conservative by default: it creates drafts only for
Gmail-discovered companies classified CONFIRMED, marked DSAR-eligible, not awaiting
controller review, and compatible with the standard GDPR Article 15 template.
Use ``--all-companies`` only for deliberate legacy/manual batch generation.

The ``review`` action is conservative too: without an explicit ``--id`` it shows
only current DRAFTs inside that same confirmed scope. Use ``--all-requests`` for an
explicit audit of legacy/quarantined/other requests.
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import models  # noqa: F401
from app.controller_resolver.verified_contacts import verified_contact_for_domain
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.gmail_discovery.classification import CONFIRMED
from app.gmail_discovery.constants import GMAIL_DISCOVERY_SOURCE
from app.gdpr_request_generator.service import generate_request, should_include_advertising_modules
from app.models.account import Account
from app.models.company import Company
from app.models.gdpr_request import GdprRequest


def generate_missing(db, settings, confirmed_only=False):
    if not settings.privacy_user_full_name or not settings.privacy_user_preferred_email:
        raise ValueError("Configure PRIVACY_USER_FULL_NAME e PRIVACY_USER_PREFERRED_EMAIL.")

    created = preserved = skipped = 0
    for company in db.scalars(select(Company).order_by(Company.id)).all():
        account = None
        if confirmed_only:
            reason = _confirmed_draft_skip_reason(company)
            if reason:
                print(f"{company.name}: ignorado ({reason}).")
                skipped += 1
                continue
            account = db.scalars(
                select(Account)
                .where(
                    Account.company_id == company.id,
                    Account.discovery_source == GMAIL_DISCOVERY_SOURCE,
                )
                .order_by(Account.id)
            ).first()
            if account is None:
                print(f"{company.name}: ignorado (sem evidencia Gmail vinculada).")
                skipped += 1
                continue

        existing = db.scalar(
            select(GdprRequest.id)
            .where(
                GdprRequest.company_id == company.id,
                GdprRequest.request_type == "article_15_access",
                GdprRequest.status.in_(["DRAFT", "APPROVED", "SENT"]),
            )
            .limit(1)
        )
        if existing is not None:
            print(f"{company.name}: pedido existente #{existing}; preservado.")
            preserved += 1
            continue

        request = generate_request(
            db,
            company,
            settings,
            "article_15_access",
            account.id if account else None,
            should_include_advertising_modules(company) if confirmed_only else False,
        )
        print(f"{company.name}: rascunho #{request.id} criado.")
        created += 1

    print(
        f"Resumo: created={created} preserved={preserved} skipped={skipped} "
        f"scope={'confirmed' if confirmed_only else 'all'}."
    )
    return created, preserved, skipped


def _confirmed_draft_skip_reason(company):
    if company.discovery_source != GMAIL_DISCOVERY_SOURCE:
        return "nao foi confirmado por Gmail"
    if company.discovery_classification != CONFIRMED or not company.discovery_dsar_eligible:
        return "descoberta nao CONFIRMED/DSAR-eligible"
    if company.discovery_requires_controller_review:
        return "controller ainda exige revisao"
    if company.domain:
        record = verified_contact_for_domain(company.domain)
        if record is not None and record.get("standard_gdpr_article_15_template", True) is False:
            framework = record.get("legal_framework") or "framework juridico especial"
            return f"nao usa template GDPR Article 15; {framework}"
    return None


def review(db, request_id=None, confirmed_only=True):
    query = select(GdprRequest).order_by(GdprRequest.id)
    if request_id is not None:
        query = query.where(GdprRequest.id == request_id)
        confirmed_only = False
    elif confirmed_only:
        query = query.where(GdprRequest.status == "DRAFT")

    requests = db.scalars(query).all()
    if confirmed_only:
        requests = [request for request in requests if _confirmed_draft_skip_reason(request.company) is None]

    if not requests:
        raise ValueError("Nenhum pedido encontrado no escopo solicitado.")

    for request in requests:
        company = request.company
        resolution = request.controller_resolution
        method = resolution.request_method if resolution else company.request_method
        contact = (
            (resolution.dpo_contact if resolution else None)
            or company.dpo_contact
            or company.privacy_email
        )
        portal = (
            (resolution.privacy_request_url if resolution else None)
            or company.privacy_request_url
        )
        print(f"\n{'=' * 60}\nPedido #{request.id} | {company.name} | {request.status}")
        print(f"Canal registrado: {method or 'unknown'}")
        print(f"Contato registrado (revisar): {contact or 'NAO ENCONTRADO'}")
        print(f"Formulario/portal: {portal or 'NAO ENCONTRADO'}")
        if method in {"form", "portal"}:
            print("Este canal exige formulario/portal; envio por email indisponivel.")
        elif method != "email":
            print("Envio por email indisponivel: canal ainda nao esta verificado como EMAIL.")
        elif not contact or "@" not in contact:
            print("Envio por email indisponivel: falta destinatario verificado.")
        print(f"Assunto: {request.subject}\n\n{request.body_text}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["generate", "review", "approve", "send"])
    parser.add_argument("--id", type=int, help="ID do pedido revisado.")
    parser.add_argument(
        "--all-companies",
        action="store_true",
        help="No generate, opta explicitamente pelo lote legado de todas as empresas.",
    )
    parser.add_argument(
        "--all-requests",
        action="store_true",
        help="No review, inclui pedidos fora do escopo confirmado e outros estados.",
    )
    args = parser.parse_args()
    if args.action == "generate" and args.id is not None:
        parser.error("generate opera em lote; omita --id")
    if args.action != "generate" and args.all_companies:
        parser.error("--all-companies so pode ser usado com generate")
    if args.action != "review" and args.all_requests:
        parser.error("--all-requests so pode ser usado com review")
    if args.action in {"approve", "send"} and args.id is None:
        parser.error("Informe --id para autorizar ou enviar um pedido especifico")
    try:
        with SessionLocal() as db:
            if args.action == "generate":
                generate_missing(db, get_settings(), confirmed_only=not args.all_companies)
                print("\nRascunhos prontos. Nenhum pedido aprovado ou enviado.")
            elif args.action == "review":
                review(db, args.id, confirmed_only=not args.all_requests)
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

        resolution = request.controller_resolution
        method = resolution.request_method if resolution else request.company.request_method
        contact = (
            (resolution.dpo_contact if resolution else None)
            or request.company.dpo_contact
            or request.company.privacy_email
        )
        if method != "email" or not contact or "@" not in contact:
            raise ValueError(
                "Pedido sem canal EMAIL verificado. Revise o controller/contato antes do envio."
            )

        token_path = Path(settings.gmail_oauth_send_token_file)
        if not token_path.is_file():
            raise ValueError("Falta autorizar o Gmail para envio (gmail_send_token.json). Nada enviado.")
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path))
        except (ValueError, KeyError) as error:
            raise ValueError("Token de envio Gmail invalido. Nada enviado.") from error
        if not credentials.has_scopes([GMAIL_SEND_SCOPE]) or not (
            credentials.valid or credentials.refresh_token
        ):
            raise ValueError("Renove a autorizacao Gmail com permissao de envio. Nada enviado.")

    endpoint = "approve" if action == "approve" else "send-email"
    call = Request(
        f"http://127.0.0.1:8000/requests/{request_id}/{endpoint}",
        method="POST",
        data=b"",
        headers={"Authorization": "Bearer " + settings.privacy_api_token},
    )
    try:
        with urlopen(call, timeout=120) as response:
            result = json.load(response)
    except HTTPError as error:
        raise ValueError(f"HTTP {error.code}: {error.read().decode(errors='replace')}") from error
    except (URLError, TimeoutError) as error:
        raise ValueError(
            "Sem confirmacao da API. Antes de repetir envio, confira o pedido e a pasta Enviados no Gmail."
        ) from error
    print(f"Pedido #{request_id}: {result['status']}")


if __name__ == "__main__":
    main()
