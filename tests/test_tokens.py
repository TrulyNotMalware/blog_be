from datetime import UTC, datetime

import jwt
import pytest

from app.core.config.config import JWT_ALGORITHM, loader
from app.core.exception.error_base import Unauthorized
from app.core.security import keys
from app.core.security.auth import decode_token, issue_access_token


def test_decode_accepts_issued_access_token() -> None:
    token = issue_access_token("admin", 1)
    assert decode_token(token)["sub"] == "admin"


def test_decode_rejects_token_without_exp() -> None:
    cfg = loader.config
    claims = {
        "sub": "admin",
        "iss": cfg.JWT_ISSUER,
        "aud": cfg.JWT_AUDIENCE,
        "iat": int(datetime.now(tz=UTC).timestamp()),
        "tv": 1,
        "typ": "access",
    }
    token = jwt.encode(claims, keys.private_key(), algorithm=JWT_ALGORITHM)
    with pytest.raises(Unauthorized):
        decode_token(token)
