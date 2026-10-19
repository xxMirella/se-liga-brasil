"""Official media requires explicit trust; HTTP upgrade is opt-in."""

import pytest

from normalization.official_media import normalize_official_media_url

HOSTS = {"www.senado.leg.br"}


def test_explicit_official_http_photo_can_be_upgraded():
    url = "http://www.senado.leg.br/senadores/img/fotos-oficiais/senador123.jpg"
    assert normalize_official_media_url(url, HOSTS, upgrade_http=True) == url.replace(
        "http:", "https:"
    )
    assert normalize_official_media_url(url, HOSTS) is None


@pytest.mark.parametrize(
    "url",
    [
        None,
        "https://www.senado.leg.br.evil.test/f",
        "https://user@www.senado.leg.br/f",
        "https://www.senado.leg.br:8080/f",
        "file:///f",
        "https://www.senado.leg.br/f#x",
    ],
)
def test_invalid_media_is_rejected(url):
    assert normalize_official_media_url(url, HOSTS, upgrade_http=True) is None
