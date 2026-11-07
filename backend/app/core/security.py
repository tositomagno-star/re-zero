import base64
import hashlib
import hmac
import secrets

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LENGTH = 32


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_KEY_LENGTH,
        maxmem=128 * 1024 * 1024,
    )
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encode(salt)}${encode(digest)}"


def verify_password(password: str, encoded_hash: str) -> bool:
    algorithm, n, r, p, salt_text, digest_text = encoded_hash.split("$")
    if algorithm != "scrypt":
        raise ValueError("Unsupported password hash algorithm.")

    decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    salt = decode(salt_text)
    expected = decode(digest_text)
    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=int(n),
        r=int(r),
        p=int(p),
        dklen=len(expected),
        maxmem=128 * 1024 * 1024,
    )
    return hmac.compare_digest(actual, expected)


def create_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_session_token(token)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_rate_limit_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
