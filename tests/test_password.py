from app.core.security.password import hash_password, verify_password


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong", hashed)


def test_verify_empty_hash_is_false() -> None:
    assert not verify_password("anything", "")


def test_over_72_byte_password_does_not_raise() -> None:
    # bcrypt >= 5 raises ValueError for > 72 bytes; we truncate so hashing and
    # verifying an over-long password stays a normal operation, never a 500.
    long_pw = "a" * 100
    hashed = hash_password(long_pw)
    assert verify_password(long_pw, hashed)


def test_password_compared_on_first_72_bytes() -> None:
    # Two passwords sharing the first 72 bytes are equivalent (historic bcrypt
    # truncation behaviour preserved across the bcrypt 5 upgrade).
    base = "a" * 72
    hashed = hash_password(base + "X")
    assert verify_password(base + "Y", hashed)
