import bcrypt

# bcrypt only considers the first 72 bytes of the password. bcrypt < 5 truncated
# silently; bcrypt >= 5 raises ValueError instead. We truncate ourselves to keep
# the historic behaviour: an over-long login password yields a normal auth result
# (not a 500), and hashes generated under the old silent-truncation stay verifiable.
_BCRYPT_MAX_BYTES = 72


def _encode(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(_encode(password), hashed.encode("utf-8"))
