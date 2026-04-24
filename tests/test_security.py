from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("s3cret!")
    assert verify_password("s3cret!", h)
    assert not verify_password("wrong", h)


def test_access_token_contains_role():
    t = create_access_token(42, "admin")
    decoded = decode_token(t)
    assert decoded["sub"] == "42"
    assert decoded["role"] == "admin"
    assert decoded["type"] == "access"


def test_refresh_token_type():
    t = create_refresh_token(1)
    assert decode_token(t)["type"] == "refresh"
