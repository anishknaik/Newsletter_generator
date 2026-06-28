"""Tests for password rules and rate limiting."""

import rate_limit


def test_password_too_short(client):
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "ab1"})
    assert r.status_code == 400
    assert "8 characters" in r.json()["detail"]


def test_password_needs_letter_and_number(client):
    no_digit = client.post("/auth/register", json={"email": "c@d.com", "password": "abcdefgh"})
    no_letter = client.post("/auth/register", json={"email": "e@f.com", "password": "12345678"})
    assert no_digit.status_code == 400 and no_letter.status_code == 400


def test_good_password_registers(client):
    assert client.post(
        "/auth/register", json={"email": "g@h.com", "password": "secret123"}
    ).status_code == 201


def test_login_is_rate_limited(client):
    """After the per-minute limit, further logins return 429."""
    rate_limit.limiter.enabled = True
    try:
        codes = [
            client.post(
                "/auth/login", json={"email": "x@y.com", "password": "whatever1"}
            ).status_code
            for _ in range(12)
        ]
        assert 429 in codes  # hit the limit
        assert codes.index(429) <= 10  # within the first 11 attempts
    finally:
        rate_limit.limiter.enabled = False
        rate_limit.limiter.reset()
