from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from azure.storage.blob import BlobServiceClient

from backend.config import settings


@dataclass(frozen=True)
class RawFile:
    source: str
    local_path: Path


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(8192), b''):
            digest.update(chunk)
    return digest.hexdigest()


def upload_raw_files(tenant: str, business_date: date, files: list[RawFile]) -> None:
    client = BlobServiceClient.from_connection_string(settings.azurite_connection_string)
    container = client.get_container_client(settings.azure_raw_container)

    if not container.exists():
        container.create_container()

    yyyy = business_date.strftime('%Y')
    mm = business_date.strftime('%m')
    dd = business_date.strftime('%d')

    for raw_file in files:
        blob_path = f'{tenant}/{raw_file.source}/{yyyy}/{mm}/{dd}/{raw_file.local_path.name}'
        blob_client = container.get_blob_client(blob_path)

        with raw_file.local_path.open('rb') as stream:
            blob_client.upload_blob(stream, overwrite=True)

        print(
            f'Uploaded {raw_file.local_path} -> {settings.azure_raw_container}/{blob_path} '
            f'(sha256={checksum(raw_file.local_path)})'
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Upload sample raw files into Azurite by tenant/date path.')
    parser.add_argument('--tenant', default='bike-team-gmbh', help='Tenant code used in blob path')
    parser.add_argument(
        '--business-date',
        default='2026-03-19',
        help='Business date partition in YYYY-MM-DD format',
    )
    parser.add_argument(
        '--extra-tenants',
        default='',
        help='Comma-separated additional tenant codes for multi-tenant demo setup',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_path = Path(__file__).resolve().parents[1] / 'data'

    files = [
        RawFile(source='bank-statement', local_path=base_path / 'Sample Bank Statement.xlsx'),
        RawFile(source='remittance', local_path=base_path / 'Sample Payment Advice.pdf'),
    ]

    business_date = date.fromisoformat(args.business_date)
    upload_raw_files(args.tenant, business_date, files)
    for extra_tenant in [tenant.strip() for tenant in args.extra_tenants.split(',') if tenant.strip()]:
        upload_raw_files(extra_tenant, business_date, files)


if __name__ == '__main__':
    main()
