#!/usr/bin/env python3
"""Codex hook: audit Python structure and inject required semantic review context."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from code_quality.system_design import review_project  # noqa: E402
from storage.files import hash_content, load_json, save_json  # noqa: E402

REVIEW_INSTRUCTIONS = (
    "System design obrigatório: revisar responsabilidade única, nomes do domínio, "
    "complexidade cognitiva, fronteiras entre módulos, consultas em lotes, memória limitada, "
    "idempotência e validação. O(n) para ler n registros é esperado; não confundir com carga "
    "cognitiva. Procurar N+1 e laços O(n²). Corrigir achados antes de concluir. "
    "O analisador é estrutural e não comprova semântica nem Big O. "
    "Aplicar a skill cognitive-code-review em "
    "/home/mirella/.codex/skills/cognitive-code-review/SKILL.md: "
    "alertar sobre carga cognitiva após alterações; buscar O(1) médio por consulta, "
    "declarando custo de construção do índice, varredura total e memória. "
    "Laços aninhados sobre grupos e seus elementos podem ser lineares no total."
)


def build_hook_output(payload: dict, findings: list[dict]) -> dict:
    event = payload.get("hook_event_name", "PostToolUse")
    report = json.dumps(findings, ensure_ascii=False)
    context = REVIEW_INSTRUCTIONS + "\nAchados estruturais: " + report
    if event == "Stop":
        if not findings:
            return {}
        return {"decision": "block", "reason": context}
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}


def main() -> None:
    payload = json.load(sys.stdin)
    findings = review_project(PROJECT_ROOT)
    state_path = PROJECT_ROOT / ".codex" / "review-state.json"
    fingerprint = hash_content({"findings": findings, "instructions": REVIEW_INSTRUCTIONS})
    previous = load_json(state_path, {})
    save_json(state_path, {"findings_hash": fingerprint, "findings": findings})
    output = build_hook_output(payload, findings)
    if (
        payload.get("hook_event_name") == "PostToolUse"
        and not findings
        and previous.get("findings_hash") == fingerprint
    ):
        output = {}
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
