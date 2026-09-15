import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from .config import settings


def _key_material() -> bytes:
    return hashlib.sha256(settings.cpf_encryption_key.encode("utf-8")).digest()


def _cipher() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_key_material()))


def encrypt_cpf(cpf: str) -> str:
    return _cipher().encrypt(cpf.encode("ascii")).decode("ascii")


def decrypt_cpf(encrypted_cpf: str) -> str:
    try:
        return _cipher().decrypt(encrypted_cpf.encode("ascii")).decode("ascii")
    except InvalidToken as error:
        raise ValueError("CPF não pôde ser descriptografado com a chave configurada") from error


def cpf_lookup_hash(cpf: str) -> str:
    lookup_key = hashlib.sha256(_key_material() + b":cpf-lookup").digest()
    return hmac.new(lookup_key, cpf.encode("ascii"), hashlib.sha256).hexdigest()
