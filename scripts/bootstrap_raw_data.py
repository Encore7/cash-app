from __future__ import annotations

import argparse
import hashlib
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from azure.storage.blob import BlobServiceClient

from backend.config import settings


@dataclass(frozen=True)
class RawFile:
    source: str
    local_path: Path


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_raw_files(
    tenant: str, business_date: date, files: list[RawFile]
) -> list[str]:
    """Upload files to Azurite and return the list of blob paths uploaded."""
    client = BlobServiceClient.from_connection_string(
        settings.azurite_connection_string
    )
    container = client.get_container_client(settings.azure_raw_container)

    if not container.exists():
        container.create_container()

    yyyy = business_date.strftime("%Y")
    mm = business_date.strftime("%m")
    dd = business_date.strftime("%d")

    blob_paths: list[str] = []
    for raw_file in files:
        unique_prefix = uuid.uuid4().hex[:8]
        blob_name = f"{unique_prefix}_{raw_file.local_path.name}"
        blob_path = f"{tenant}/{raw_file.source}/{yyyy}/{mm}/{dd}/{blob_name}"
        blob_client = container.get_blob_client(blob_path)

        with raw_file.local_path.open("rb") as stream:
            blob_client.upload_blob(stream, overwrite=True)

        print(
            f"Uploaded {raw_file.local_path} -> {settings.azure_raw_container}/{blob_path} "
            f"(sha256={checksum(raw_file.local_path)})"
        )
        blob_paths.append(blob_path)

    return blob_paths


def register_blobs_in_db(
    tenant_code: str, business_date: date, files: list[RawFile], blob_paths: list[str]
) -> None:
    """Register uploaded blobs in the blob_objects table with is_parsed=False."""
    from uuid import uuid4 as _uuid4

    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from backend.db.session import SessionLocal
    from backend.models.core import BlobObject, Tenant
    from backend.models.enums import SourceType

    source_map = {
        "bank-statement": SourceType.BANK_STATEMENT,
        "remittance": SourceType.REMITTANCE,
    }

    db = SessionLocal()
    try:
        tenant_obj = db.scalar(select(Tenant).where(Tenant.code == tenant_code))
        if not tenant_obj:
            tenant_obj = Tenant(
                code=tenant_code,
                name=tenant_code.replace("-", " ").title(),
                is_active=True,
            )
            db.add(tenant_obj)
            db.flush()

        for raw_file, blob_path in zip(files, blob_paths):
            content = raw_file.local_path.read_bytes()
            content_hash = hashlib.sha256(content).hexdigest()
            source_type = source_map[raw_file.source]

            stmt = (
                pg_insert(BlobObject)
                .values(
                    id=_uuid4(),
                    tenant_id=tenant_obj.id,
                    source_type=source_type,
                    business_date=business_date,
                    container_name=settings.azure_raw_container,
                    blob_path=blob_path,
                    original_file_name=raw_file.local_path.name,
                    content_hash=content_hash,
                    size_bytes=len(content),
                    is_parsed=False,
                )
                .on_conflict_do_nothing(constraint="uq_blob_dedup")
            )
            db.execute(stmt)
            print(
                f"  DB registered: {raw_file.local_path.name} as {source_type.value} (is_parsed=False)"
            )

        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"Warning: could not register blobs in DB: {exc}")
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload sample raw files into Azurite by tenant/date path."
    )
    parser.add_argument(
        "--tenant", default="bike-team-gmbh", help="Tenant code used in blob path"
    )
    parser.add_argument(
        "--business-date",
        default="2026-03-19",
        help="Business date partition in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--extra-tenants",
        default="",
        help="Comma-separated additional tenant codes for multi-tenant demo setup",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_path = Path(__file__).resolve().parents[1] / "data"

    files = [
        RawFile(
            source="bank-statement", local_path=base_path / "Sample Bank Statement.xlsx"
        ),
        RawFile(
            source="remittance", local_path=base_path / "Sample Payment Advice.pdf"
        ),
    ]

    business_date = date.fromisoformat(args.business_date)

    blob_paths = upload_raw_files(args.tenant, business_date, files)
    register_blobs_in_db(args.tenant, business_date, files, blob_paths)

    for extra_tenant in [
        tenant.strip() for tenant in args.extra_tenants.split(",") if tenant.strip()
    ]:
        extra_paths = upload_raw_files(extra_tenant, business_date, files)
        register_blobs_in_db(extra_tenant, business_date, files, extra_paths)


if __name__ == "__main__":
    main()
