from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config.config import JWT_ALGORITHM, loader
from app.core.exception.error_base import Unauthorized
from app.core.security import keys
from app.core.security.auth import decode_token, issue_access_token


def test_decode_accepts_issued_access_token() -> None:
    token = issue_access_token("admin", 1)
    assert decode_token(token)["sub"] == "admin"


@pytest.mark.parametrize("missing", ["exp", "iat", "sub"])
def test_decode_rejects_token_without_required_claim(missing: str) -> None:
    cfg = loader.config
    now = datetime.now(tz=UTC)
    claims: dict[str, object] = {
        "sub": "admin",
        "iss": cfg.JWT_ISSUER,
        "aud": cfg.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "tv": 1,
        "typ": "access",
    }
    del claims[missing]
    token = jwt.encode(claims, keys.private_key(), algorithm=JWT_ALGORITHM)
    with pytest.raises(Unauthorized):
        decode_token(token)
