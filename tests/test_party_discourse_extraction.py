import json
from types import SimpleNamespace

import httpx
import pytest

from gemini_api.cached_generator import CachedJsonGenerator
from gemini_api.client import (
    DailyQuotaExhaustedError,
    GeminiApiError,
    GeminiJsonClient,
    GeneratedJson,
)
from gemini_api.request_pacer import CallBudgetExhaustedError, RequestPacer
from gemini_api.response_cache import DiskResponseCache
from service.party_discourse_extraction.agreement import cohen_kappa
from service.party_discourse_extraction.blinding import blind_text
from service.party_discourse_extraction.consistency import label_consistency
from service.party_discourse_extraction.evidence_conversion import convert_record
from service.party_discourse_extraction.extraction_run import run_extraction
from service.party_discourse_extraction.labeling import sample_labeling_units, write_labeling_csv
from service.party_discourse_extraction.relevance import assess_relevance
from service.party_discourse_extraction.rubric_indicators import RubricIndicator
from service.party_discourse_extraction.segmentation import MAX_SEGMENT_CHARACTERS, segment_document
from service.party_discourse_extraction.validation import ExtractedItem, validate_response

PASSAGE = (
    "Defendemos a privatização de empresas estatais que não cumprem função estratégica. "
    "Também propomos reduzir a carga tributária sobre a produção e o emprego formal."
)
QUOTE = "Defendemos a privatização de empresas estatais"


def answer(**overrides) -> str:
    item = {
        "indicator": "E1",
        "direction": "+1",
        "strength": 3,
        "commitment_type": "generico",
        "quote": QUOTE,
    }
    return json.dumps({"items": [{**item, **overrides}]})


def test_validation_accepts_a_literal_quote_even_with_other_whitespace_and_quotes():
    passage = "Art. 1º  O texto\n afirma “liberdade” plena de mercado e concorrência aberta."
    text = answer(quote='O texto afirma "liberdade" plena de mercado')
    accepted, discarded = validate_response(text, passage, {"E1"})
    assert len(accepted) == 1 and not discarded


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"quote": "Defendemos a estatização de todas as empresas"}, "quote_not_in_passage"),
        ({"quote": "privatização"}, "quote_too_short"),
        ({"indicator": "X9"}, "indicator_unknown"),
        ({"direction": "2"}, "direction_invalid"),
        ({"strength": 7}, "strength_invalid"),
        ({"strength": True}, "strength_invalid"),
    ],
)
def test_validation_discards_unproven_or_invalid_items(overrides, reason):
    accepted, discarded = validate_response(answer(**overrides), PASSAGE, {"E1"})
    assert not accepted and [item.reason for item in discarded] == [reason]


def test_validation_discards_duplicates_and_malformed_json():
    twice = json.dumps({"items": json.loads(answer())["items"] * 2})
    accepted, discarded = validate_response(twice, PASSAGE, {"E1"})
    assert len(accepted) == 1 and discarded[0].reason == "duplicate_item"
    assert validate_response("not json", PASSAGE, {"E1"})[1][0].reason == "response_not_valid_json"


def test_not_applicable_direction_is_kept_as_none():
    accepted, _ = validate_response(answer(direction="nao_se_aplica"), PASSAGE, {"E1"})
    assert accepted[0].direction is None


def test_blinding_masks_party_names_links_and_leaders_but_not_common_words():
    text = (
        "O PT e o Partido dos Trabalhadores com Lula em https://pt.org.br/x. "
        "Um novo tempo, dizem os petistas."
    )
    blinded = blind_text(text, "PT")
    for forbidden in ("PT", "Trabalhadores", "Lula", "petistas", "pt.org.br"):
        assert forbidden not in blinded.text
    assert "novo tempo" in blinded.text and blinded.masked_counts["[PARTIDO]"] >= 3
    novo = blind_text("O NOVO defende um novo modelo; o Partido Novo cresce.", "NOVO").text
    assert "NOVO" not in novo and "Partido Novo" not in novo and "um novo modelo" in novo
    with pytest.raises(ValueError, match="BLINDING_PARTY_UNKNOWN"):
        blind_text("texto", "XYZ")


def test_segmentation_keeps_articles_apart_and_respects_the_size_limit():
    articles = "\n\n".join(f"Art. {n}º " + "Texto de exemplo longo. " * 12 for n in range(1, 4))
    assert len(segment_document(articles, "doc")) >= 1
    huge = "Frase completa de teste do documento. " * 400
    assert all(len(s.text) <= MAX_SEGMENT_CHARACTERS for s in segment_document(huge, "doc"))


def test_relevance_filter_needs_a_keyword_and_enough_words():
    assert assess_relevance(PASSAGE).indicator_hints[:2] == ("E1", "E3")
    assert not assess_relevance(
        "A convenção se reunirá em local definido pela executiva."
    ).is_relevant
    assert not assess_relevance("privatização").is_relevant


def item(indicator="E1", direction=1, quote="a mesma frase exata do documento"):
    return ExtractedItem(indicator, direction, 2, "generico", quote)


def test_consistency_marks_agreement_conflict_and_single_run():
    first = [
        item(),
        item("E3", 1, "outra frase distinta sobre tributos"),
        item("C2", 1, "frase só aqui"),
    ]
    second = [item(), item("E3", -1, "outra frase distinta sobre tributos")]
    labeled, report = label_consistency(first, second)
    assert [status for _, status in labeled] == ["agree", "direction_conflict", "single_run"]
    assert (report.agree, report.direction_conflict, report.only_first_run) == (1, 1, 1)


class CountingGenerator:
    model = "fake-model"

    def __init__(self, text):
        self.calls, self._text = 0, text

    def generate_json(self, system_instruction, user_text, response_schema):
        self.calls += 1
        return GeneratedJson(self._text, self.model, {"totalTokenCount": 1})


def test_cache_avoids_repeated_calls_but_keeps_runs_independent(tmp_path):
    inner, cache = CountingGenerator("{}"), DiskResponseCache(tmp_path)
    first = CachedJsonGenerator(inner, cache, "v1", "run-1")
    second = CachedJsonGenerator(inner, cache, "v1", "run-2")
    for _ in range(2):
        first.generate_json("sys", "texto", {"type": "object"})
    assert inner.calls == 1 and first.cache_hits == 1
    second.generate_json("sys", "texto", {"type": "object"})
    assert inner.calls == 2
    CachedJsonGenerator(inner, cache, "v2", "run-1").generate_json(
        "sys", "texto", {"type": "object"}
    )
    assert inner.calls == 3  # a new prompt version never reuses old answers


def gemini_client(handler, max_calls=10):
    pacer = RequestPacer(0, max_calls, sleep=lambda seconds: None)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return GeminiJsonClient("secret-key-123", "fake-model", pacer, http, sleep=lambda s: None)


def ok_body(text="{}"):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}


def test_client_retries_transient_errors_and_sends_the_key_only_as_a_header():
    seen = []

    def handler(request):
        seen.append(request)
        status = 503 if len(seen) == 1 else 200
        return httpx.Response(status, json=ok_body('{"items": []}'))

    generated = gemini_client(handler).generate_json("sys", "texto", {"type": "object"})
    assert generated.text == '{"items": []}' and len(seen) == 2
    assert seen[0].headers["x-goog-api-key"] == "secret-key-123"
    assert (
        "secret-key-123" not in str(seen[0].url)
        and "secret-key-123" not in seen[0].content.decode()
    )
    body = json.loads(seen[0].content)
    assert body["generationConfig"]["temperature"] == 0


def test_client_stops_on_daily_quota_and_never_leaks_the_key_in_errors():
    def handler(request):
        return httpx.Response(429, text="Quota exceeded ... GenerateRequestsPerDayPerProject")

    with pytest.raises(DailyQuotaExhaustedError) as error:
        gemini_client(handler).generate_json("sys", "texto", {"type": "object"})
    assert "secret-key-123" not in str(error.value)


def test_client_rejects_non_retryable_status_and_truncated_answers():
    with pytest.raises(GeminiApiError, match="GEMINI_HTTP_400"):
        gemini_client(lambda r: httpx.Response(400, json={})).generate_json("s", "t", {})
    truncated = {
        "candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{"}]}}]
    }
    with pytest.raises(GeminiApiError, match="GEMINI_FINISH_MAX_TOKENS"):
        gemini_client(lambda r: httpx.Response(200, json=truncated)).generate_json("s", "t", {})


def test_pacer_enforces_the_call_budget():
    pacer = RequestPacer(0, 2, sleep=lambda seconds: None)
    pacer.wait_turn()
    pacer.wait_turn()
    with pytest.raises(CallBudgetExhaustedError):
        pacer.wait_turn()


def planned(text):
    document = SimpleNamespace(sha256="a" * 64, political_party="PT")
    return SimpleNamespace(
        blinded_text=text,
        document=document,
        segment=SimpleNamespace(segment_id="PT-aaaaaaaaaaaa-0001", heading="h", text=text),
        text_origin="html",
        masked_counts={},
        indicator_hints=("E1",),
    )


def test_run_extraction_validates_both_runs_and_stops_on_budget():
    generators = {"run-1": CountingGenerator(answer()), "run-2": CountingGenerator(answer())}
    outcome = run_extraction([planned(PASSAGE)], generators, "sys", {}, {"E1"})
    result = outcome.results_by_document["a" * 64][0]
    assert result.labeled_items[0][1] == "agree" and outcome.stopped_reason is None

    class Exhausted:
        model = "fake"

        def generate_json(self, *args):
            raise CallBudgetExhaustedError("GEMINI_CALL_BUDGET_EXHAUSTED")

    stopped = run_extraction(
        [planned(PASSAGE)], {"run-1": Exhausted(), "run-2": Exhausted()}, "s", {}, {"E1"}
    )
    assert stopped.stopped_reason == "GEMINI_CALL_BUDGET_EXHAUSTED" and stopped.passages_done == 0


def indicator(code="E1", contested=False):
    return RubricIndicator(code, f"{code}_x", "economic", "rótulo", "n", "p", contested)


def record(direction=1, consistency="agree"):
    return {
        "political_party": "NOVO",
        "document": {
            "sha256": "b" * 64,
            "source_url": "manual:x.pdf",
            "document_date": None,
            "retrieved_on": "2026-10-29",
        },
        "provenance": {"model": "fake", "prompt_version": "v1"},
        "passages": [
            {
                "segment_id": "NOVO-bbbbbbbbbbbb-0003",
                "text_origin": "ocr",
                "items": [
                    {
                        "indicator": "E1",
                        "direction": direction,
                        "strength": 2,
                        "commitment_type": "generico",
                        "quote": "uma citação qualquer do texto",
                        "consistency": consistency,
                    }
                ],
            }
        ],
    }


def test_evidence_candidates_have_zero_weight_and_wait_for_review():
    evidence = convert_record(record(), {"E1": indicator()})[0]
    assert evidence["layer"] == "discourse" and evidence["weight_override"] == 0.0
    assert (
        evidence["review_status"] == "pending_human_review" and evidence["human_reviewed"] is False
    )
    assert evidence["stance"] == pytest.approx(0.667) and evidence["document_date_known"] is False
    assert evidence["display_only"] is False and evidence["year_start"] == 2026
    contested = convert_record(record(), {"E1": indicator(contested=True)})[0]
    assert contested["display_only"] is True


def test_not_applicable_items_produce_no_evidence():
    assert convert_record(record(direction=None), {"E1": indicator()}) == []


def test_kappa_matches_hand_computed_values():
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "a", "b", "b"]) == 1.0
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == 0.0
    assert cohen_kappa(["a", "a"], ["a", "a"]) is None  # no variation: chance agreement is 1
    assert cohen_kappa([], []) is None


def test_labeling_sheet_hides_the_party_and_opens_in_excel(tmp_path):
    texts = [
        f"Defendemos a privatização de empresas estatais número {n} em todo o país hoje mesmo, "
        "com regras claras para investidores e trabalhadores do setor produtivo nacional."
        for n in range(6)
    ]
    passages = [planned("\n\n".join(texts))]
    units = sample_labeling_units(passages, ("PT",), per_party=4)
    csv_path = tmp_path / "rotulagem.csv"
    write_labeling_csv(units, csv_path)
    raw = csv_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and len(units) == 4
    assert [u.unit_id for u in units] == ["T001", "T002", "T003", "T004"]
    assert b"PT" not in raw.split(b"\n", 1)[1]


def test_label_comparison_reads_sheets_and_compares_people_and_model(tmp_path):
    from service.party_discourse_extraction.label_comparison import (
        compare_label_sets,
        model_labels,
        read_labels,
    )

    header = (
        "id_do_trecho;texto;indicador_sugerido_pela_ia;indicador;direcao;forca;tipo;comentario\n"
    )
    sheet_a = header + "T001;x;;E1;+1;3;generico;\nT002;y;;nenhum;;;;\n"
    sheet_b = header + "T001;x;;E1;+1;2;generico;\nT002;y;;C2;-1;1;generico;\n"
    for name, content in (("a.csv", sheet_a), ("b.csv", sheet_b)):
        (tmp_path / name).write_text(content, encoding="utf-8-sig")
    labels_a, labels_b = read_labels(tmp_path / "a.csv"), read_labels(tmp_path / "b.csv")
    assert labels_a["T002"]["indicador"] == "nenhum"
    comparison = compare_label_sets(labels_a, labels_b)
    assert comparison["passages_compared"] == 2
    assert comparison["indicator"]["raw_agreement"] == 0.5
    model = model_labels({"T001": [{"indicator": "E1", "direction": 1, "strength": 2}], "T002": []})
    assert model["T001"] == {"indicador": "E1", "direcao": "+1"}
    assert model["T002"]["indicador"] == "nenhum"
