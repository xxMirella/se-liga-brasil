"""A persistent, truthful completion message for interactive and redirected executions."""


def build_completion_lines(result: dict) -> list[str]:
    artifacts = result.get("artifacts", [])
    accepted = sum(
        item.get(key, 0) for item in artifacts for key in ("new", "changed", "unchanged")
    )
    rejected = sum(item.get("rejected", 0) for item in artifacts)
    failures = len(result.get("failures", []))
    if result.get("status") == "completed":
        message = (
            "CONCLUÍDO — todos os dados válidos encontrados foram ingeridos ou já estavam na base."
        )
    else:
        message = (
            "FINALIZADO COM PENDÊNCIAS — consulte as rejeições e falhas "
            "antes de considerar a carga completa."
        )
    lines = [
        message,
        f"Arquivos processados: {len(artifacts)} | Falhas: {failures}",
        f"Registros aceitos: {accepted} | Rejeitados: {rejected}",
        f"Log de rejeições: {result.get('rejection_log', '')}",
    ]
    coverage = result.get("payroll_identity_coverage")
    if coverage is not None:
        lines.append(
            f"Vínculos de pessoa confirmados: {coverage.get('verified', 0)} | "
            f"Pagamentos com identidade pendente: {coverage.get('pending', 0)}"
        )
    return lines
