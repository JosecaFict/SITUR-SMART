import pytest


@pytest.mark.parametrize("header", ["authorization", "content-type", "idempotency-key"])
def test_booking_preflight_allows_required_headers(client, header):
    response = client.options(
        "/api/v1/me/reservas/",
        HTTP_ORIGIN="https://situr-smart-web.vercel.app",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type,idempotency-key",
    )

    assert response.status_code == 200
    allowed = {
        item.strip().lower()
        for item in response.headers["Access-Control-Allow-Headers"].split(",")
    }
    assert header in allowed
