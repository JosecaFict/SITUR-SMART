"""Enlace firmado de Cloudinary para bajar una copia privada (sin red)."""

from urllib.parse import parse_qs, urlparse

from apps.backups import storage


def test_el_enlace_es_privado_firmado_y_vence(settings):
    settings.CLOUDINARY_CLOUD_NAME = "demo"
    settings.CLOUDINARY_API_KEY = "123"
    settings.CLOUDINARY_API_SECRET = "secreto"

    url = urlparse(storage.download_link("situr-smart/respaldos/situr-smart-1.dump"))
    params = parse_qs(url.query)

    assert url.path == "/v1_1/demo/raw/download"
    assert params["public_id"] == ["situr-smart/respaldos/situr-smart-1.dump"]
    assert params["type"] == ["authenticated"]
    assert int(params["expires_at"][0]) - int(params["timestamp"][0]) == storage.LINK_SECONDS
    assert params["signature"]
    assert "secreto" not in url.geturl()
