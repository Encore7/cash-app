from __future__ import annotations

import hashlib
from datetime import date


def build_blob_prefix(tenant_code: str, source: str, business_date: date) -> str:
    return (
        f"{tenant_code}/{source}/{business_date.strftime('%Y')}/"
        f"{business_date.strftime('%m')}/{business_date.strftime('%d')}/"
    )


def sha256_bytes(payload: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(payload)
    return digest.hexdigest()
