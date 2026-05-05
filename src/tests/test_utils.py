import pytest

from facilito.utils import canonical_content_url, ensure_absolute_url


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "/cursos/bootcamp-premium-java-cierre?play=true",
            "https://codigofacilito.com/cursos/bootcamp-premium-java-cierre",
        ),
        (
            "https://codigofacilito.com/cursos/docker?play=true",
            "https://codigofacilito.com/cursos/docker",
        ),
        (
            "https://codigofacilito.com/cursos/docker?foo=bar&play=true",
            "https://codigofacilito.com/cursos/docker?foo=bar",
        ),
    ],
)
def test_canonical_content_url_removes_player_query(url, expected):
    assert canonical_content_url(url) == expected


def test_ensure_absolute_url_keeps_absolute_urls_unchanged():
    url = "https://codigofacilito.com/videos/abc"
    assert ensure_absolute_url(url) == url
