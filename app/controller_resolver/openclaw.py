import json
import os
import shlex
import subprocess
from dataclasses import replace

from app.controller_resolver.types import ControllerResolutionResult, EvidenceItem, FetchedPage
from app.core.config import Settings


class NullControllerTextInterpreter:
    def interpret(
        self, domain: str, pages: list[FetchedPage], existing: ControllerResolutionResult
    ) -> ControllerResolutionResult:
        return existing


class OpenClawControllerTextInterpreter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def interpret(
        self, domain: str, pages: list[FetchedPage], existing: ControllerResolutionResult
    ) -> ControllerResolutionResult:
        if not self.settings.openclaw_enabled:
            return existing

        missing_fields = [
            field
            for field, value in {
                "controller_name": existing.controller_name,
                "controller_country": existing.controller_country,
                "dpo_contact": existing.dpo_contact,
                "privacy_request_url": existing.privacy_request_url,
            }.items()
            if not value
        ]
        if not missing_fields:
            return existing

        payload = {
            "domain": domain,
            "missing_fields": missing_fields,
            "pages": [
                {"url": page.url, "title": page.title, "text": page.text[: self.settings.openclaw_max_input_chars]}
                for page in pages[: self.settings.controller_resolver_max_pages]
            ],
        }
        prompt = (
            "Extract only values that are explicitly supported by the provided page text. "
            "Return JSON with keys controller_name, controller_country, dpo_contact, "
            "privacy_request_url, and evidence. Evidence items must include field, value, "
            "source_url, and an exact short excerpt from the input text. Use empty strings "
            "when the evidence is insufficient."
        )
        schema = {
            "type": "object",
            "properties": {
                "controller_name": {"type": "string"},
                "controller_country": {"type": "string"},
                "dpo_contact": {"type": "string"},
                "privacy_request_url": {"type": "string"},
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "value": {"type": "string"},
                            "source_url": {"type": "string"},
                            "excerpt": {"type": "string"},
                        },
                        "required": ["field", "value", "source_url", "excerpt"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "controller_name",
                "controller_country",
                "dpo_contact",
                "privacy_request_url",
                "evidence",
            ],
            "additionalProperties": False,
        }

        try:
            command_env = os.environ.copy()
            if self.settings.openclaw_token:
                command_env["OPENCLAW_TOKEN"] = self.settings.openclaw_token
            if self.settings.openclaw_base_url:
                command_env["OPENCLAW_BASE_URL"] = self.settings.openclaw_base_url
            completed = subprocess.run(
                [
                    *shlex.split(self.settings.openclaw_invoke_command),
                    "--tool",
                    "llm-task",
                    "--action",
                    "json",
                    "--args-json",
                    json.dumps(
                        {
                            "prompt": prompt,
                            "input": payload,
                            "schema": schema,
                            "baseUrl": self.settings.openclaw_base_url,
                            "model": self.settings.openclaw_model,
                            "maxTokens": 800,
                            "temperature": 0,
                        }
                    ),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.settings.openclaw_timeout_seconds,
                env=command_env,
            )
        except (OSError, subprocess.SubprocessError):
            return existing

        interpreted = _parse_openclaw_json(completed.stdout)
        if not interpreted:
            return existing

        return _merge_interpreted(existing, interpreted, pages)


def _parse_openclaw_json(output: str) -> dict[str, object] | None:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        start = output.find("{")
        end = output.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            parsed = json.loads(output[start : end + 1])
        except json.JSONDecodeError:
            return None

    if isinstance(parsed, dict) and isinstance(parsed.get("details"), dict):
        details = parsed["details"]
        if isinstance(details.get("json"), dict):
            return details["json"]
        if isinstance(details, dict):
            return details
    return parsed if isinstance(parsed, dict) else None


def _merge_interpreted(
    existing: ControllerResolutionResult,
    interpreted: dict[str, object],
    pages: list[FetchedPage],
) -> ControllerResolutionResult:
    fields = {
        "controller_name": existing.controller_name,
        "controller_country": existing.controller_country,
        "dpo_contact": existing.dpo_contact,
        "privacy_request_url": existing.privacy_request_url,
    }
    evidence = list(existing.evidence)
    allowed_urls = {page.url for page in pages}
    all_text = "\n".join(page.text for page in pages)

    for item in interpreted.get("evidence", []):
        if not isinstance(item, dict):
            continue
        field = str(item.get("field", ""))
        value = str(item.get("value", ""))
        source_url = str(item.get("source_url", ""))
        excerpt = str(item.get("excerpt", ""))
        if field not in fields or fields[field] or not value:
            continue
        if source_url not in allowed_urls:
            continue
        if excerpt and excerpt.lower() not in all_text.lower():
            continue
        fields[field] = value
        evidence.append(EvidenceItem(field, value, source_url, excerpt))

    confidence = existing.confidence
    if len(evidence) > len(existing.evidence):
        confidence = min(0.85, confidence + 0.08 * (len(evidence) - len(existing.evidence)))

    return replace(
        existing,
        controller_name=fields["controller_name"],
        controller_country=fields["controller_country"],
        controller_address=existing.controller_address,
        dpo_contact=fields["dpo_contact"],
        privacy_request_url=fields["privacy_request_url"],
        confidence=round(confidence, 2),
        evidence=evidence,
    )
