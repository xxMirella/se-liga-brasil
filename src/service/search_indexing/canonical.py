"""Canonicalize semantic page filters without merging distinct pages."""

from urllib.parse import parse_qsl, urlencode, urlsplit
from uuid import UUID


def path_with_parameters(path, parameters):
    query = urlencode([(key, str(value)) for key, value in parameters.items() if value])
    return path + ("?" + query if query else "")


def panorama_canonical(parameters):
    """Only the legislature is a distinct page; every other parameter is an interaction."""
    from service.majority_panorama.state import parse_state

    return path_with_parameters("/panorama", {"leg": parse_state(parameters).legislature_id})


def canonical_page(target, today):
    parsed = urlsplit(target)
    parameters = dict(parse_qsl(parsed.query, keep_blank_values=False))
    path = parsed.path.rstrip("/") or "/"
    if path == "/panorama":
        return panorama_canonical(parameters), False
    if path.startswith("/pessoas/"):
        identifier = str(UUID(path.rsplit("/", 1)[-1]))
        activity = parameters.get("tab") == "activity"
        filtered = bool(set(parameters) - {"tab", "scope"}) or parameters.get("scope") == "period"
        return "/pessoas/" + identifier + ("?tab=activity" if activity else ""), filtered
    if path == "/pessoas":
        filtered = bool(set(parameters) - {"limit"})
        canonical = (path_with_parameters(path, dict(sorted(parameters.items())))
                     if filtered else path)
        return canonical, filtered
    if path == "/como-funciona":
        sphere = parameters.get("esfera")
        return path_with_parameters(path, {
            "esfera": sphere if sphere != "municipal" else None,
        }), False
    if path == "/comparacao-de-classificacoes":
        return path_with_parameters(path, {
            "partido": parameters.get("partido", "").casefold(),
        }), False
    return ("/" if path == "/sobre" else path), False
