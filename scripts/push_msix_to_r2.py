#!/usr/bin/env python3
"""
Push Lunifier MSIX packages meant for Windows Store to a Cloudflare R2 bucket.

Credentials and configuration can be passed via:
  - Environment variables:
      R2_ACCOUNT_ID
      R2_ACCESS_KEY_ID
      R2_SECRET_ACCESS_KEY
      R2_BUCKET_NAME
      R2_PREFIX (optional, default: "msix/")
      R2_PUBLIC_URL (optional, e.g. "https://pub-xxxx.r2.dev" or custom domain)
  - CLI arguments:
      --account-id, --access-key-id, --secret-access-key, --bucket, --prefix, --public-url
  - Optional .env file in the workspace directory

Usage:
  python scripts/push_msix_to_r2.py --bucket my-r2-bucket --account-id <id> ...
  python scripts/push_msix_to_r2.py --version latest
  python scripts/push_msix_to_r2.py --dry-run
"""

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import boto3
    from botocore.config import Config
except ImportError:
    boto3 = None
    Config = None


def load_env_file(env_path: Path):
    """Load simple KEY=VALUE pairs from a .env file if it exists."""
    if not env_path.is_file():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as ex:
        print(f"[WARN] Error reading {env_path}: {ex}", file=sys.stderr)


def compute_sha256(filepath: Path) -> str:
    """Calculate SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest().upper()


def find_msix_packages(
    dist_dir: Path,
    version_filter: Optional[str] = None,
    edition_filter: str = "all"
) -> List[Path]:
    """
    Find MSIX packages in the dist directory matching the given version and edition.
    """
    if not dist_dir.is_dir():
        return []

    all_msix = sorted(dist_dir.glob("*.msix"))
    if not all_msix:
        return []

    # Filter by edition
    filtered = []
    for pkg in all_msix:
        name = pkg.name.lower()
        is_nobtsync = "nobtsync" in name
        if edition_filter == "standard" and is_nobtsync:
            continue
        if edition_filter == "nobtsync" and not is_nobtsync:
            continue
        filtered.append(pkg)

    if not version_filter or version_filter.lower() == "all":
        return filtered

    if version_filter.lower() == "latest":
        # Extract version tags like 2.2.2 or 2.2.2.0 from filename
        def parse_version(p: Path) -> Tuple[int, ...]:
            m = re.search(r"(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?", p.name)
            if m:
                parts = [int(x) if x is not None else 0 for x in m.groups()]
                return tuple(parts)
            return (0, 0, 0, 0)

        versions = [parse_version(p) for p in filtered if parse_version(p) != (0, 0, 0, 0)]
        if not versions:
            return filtered
        max_ver = max(versions)
        ver_str_3 = f"{max_ver[0]}.{max_ver[1]}.{max_ver[2]}"
        ver_str_4 = f"{max_ver[0]}.{max_ver[1]}.{max_ver[2]}.{max_ver[3]}"
        return [p for p in filtered if ver_str_3 in p.name or ver_str_4 in p.name]

    # Specific version string
    ver = version_filter.strip().lstrip("v")
    return [p for p in filtered if ver in p.name]


def create_r2_client(account_id: str, access_key_id: str, secret_access_key: str):
    """Instantiate a boto3 S3 client configured for Cloudflare R2."""
    if boto3 is None:
        raise RuntimeError("boto3 is not installed. Please run: pip install boto3")

    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"}
        )
    )


def upload_packages(
    packages: List[Path],
    account_id: str,
    access_key_id: str,
    secret_access_key: str,
    bucket_name: str,
    prefix: str = "msix/",
    public_url: Optional[str] = None,
    dry_run: bool = False
) -> int:
    """
    Upload MSIX packages to the Cloudflare R2 bucket.
    """
    if not packages:
        print("[INFO] No MSIX packages found matching the criteria.")
        return 0

    print("===================================================")
    print(f" Cloudflare R2 MSIX Package Uploader")
    print(f" Target Bucket: {bucket_name}")
    print(f" Prefix:        {prefix}")
    print(f" Packages ({len(packages)}):")
    for p in packages:
        size_mb = p.stat().st_size / (1024 * 1024)
        print(f"   - {p.name} ({size_mb:.2f} MB)")
    print("===================================================")

    if dry_run:
        print("[DRY-RUN] No files were uploaded. Credentials check and preview complete.")
        return 0

    client = create_r2_client(account_id, access_key_id, secret_access_key)

    prefix_norm = prefix.strip("/")
    if prefix_norm:
        prefix_norm += "/"

    success_count = 0
    failures = []

    for pkg in packages:
        dest_key = f"{prefix_norm}{pkg.name}"
        sha256 = compute_sha256(pkg)
        size_bytes = pkg.stat().st_size
        size_mb = size_bytes / (1024 * 1024)

        print(f"\n[UPLOADING] {pkg.name} ({size_mb:.2f} MB)")
        print(f"  Destination Key: {dest_key}")
        print(f"  SHA-256:         {sha256}")

        try:
            extra_args = {
                "ContentType": "application/msix",
                "ContentDisposition": f'attachment; filename="{pkg.name}"',
                "Metadata": {
                    "sha256": sha256,
                    "target": "windows-store"
                }
            }

            client.upload_file(
                Filename=str(pkg),
                Bucket=bucket_name,
                Key=dest_key,
                ExtraArgs=extra_args
            )

            print(f"  [OK] Successfully uploaded to s3://{bucket_name}/{dest_key}")
            if public_url:
                base = public_url.rstrip("/")
                print(f"  Public URL: {base}/{dest_key}")

            success_count += 1
        except Exception as ex:
            print(f"  [ERROR] Failed to upload {pkg.name}: {ex}", file=sys.stderr)
            failures.append((pkg.name, str(ex)))

    print("\n===================================================")
    print(f" Upload Summary: {success_count}/{len(packages)} succeeded.")
    if failures:
        print(f" Failures ({len(failures)}):")
        for name, err in failures:
            print(f"   - {name}: {err}")
        return 1
    print("===================================================")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Upload Lunifier Windows Store MSIX packages to Cloudflare R2 bucket."
    )
    parser.add_argument(
        "--account-id",
        default=os.environ.get("R2_ACCOUNT_ID"),
        help="Cloudflare Account ID (or env R2_ACCOUNT_ID)"
    )
    parser.add_argument(
        "--access-key-id",
        default=os.environ.get("R2_ACCESS_KEY_ID"),
        help="Cloudflare R2 Access Key ID (or env R2_ACCESS_KEY_ID)"
    )
    parser.add_argument(
        "--secret-access-key",
        default=os.environ.get("R2_SECRET_ACCESS_KEY"),
        help="Cloudflare R2 Secret Access Key (or env R2_SECRET_ACCESS_KEY)"
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("R2_BUCKET_NAME"),
        help="Cloudflare R2 Bucket Name (or env R2_BUCKET_NAME)"
    )
    parser.add_argument(
        "--prefix",
        default=os.environ.get("R2_PREFIX", "msix/"),
        help="Destination path prefix in R2 bucket (default: 'msix/')"
    )
    parser.add_argument(
        "--public-url",
        default=os.environ.get("R2_PUBLIC_URL"),
        help="Public R2 or custom domain base URL (e.g. 'https://r2.mydomain.com')"
    )
    parser.add_argument(
        "--version",
        default="latest",
        help="Version filter: 'latest' (default), 'all', or specific e.g. '2.2.2'"
    )
    parser.add_argument(
        "--edition",
        choices=["all", "standard", "nobtsync"],
        default="all",
        help="Filter edition: 'all' (default), 'standard', or 'nobtsync'"
    )
    parser.add_argument(
        "--dist-dir",
        default=str(Path(__file__).resolve().parent.parent / "dist"),
        help="Path to dist directory containing .msix packages"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate and print actions without uploading to R2"
    )

    # Automatically load .env if present in workspace root
    workspace_root = Path(__file__).resolve().parent.parent
    load_env_file(workspace_root / ".env")

    args = parser.parse_args()

    # Re-evaluate env vars in case .env just loaded them
    account_id = args.account_id or os.environ.get("R2_ACCOUNT_ID")
    access_key_id = args.access_key_id or os.environ.get("R2_ACCESS_KEY_ID")
    secret_access_key = args.secret_access_key or os.environ.get("R2_SECRET_ACCESS_KEY")
    bucket_name = args.bucket or os.environ.get("R2_BUCKET_NAME")
    prefix = args.prefix or os.environ.get("R2_PREFIX", "msix/")
    public_url = args.public_url or os.environ.get("R2_PUBLIC_URL")

    dist_dir = Path(args.dist_dir)
    packages = find_msix_packages(dist_dir, version_filter=args.version, edition_filter=args.edition)

    if not packages:
        print(f"[ERROR] No MSIX packages found in {dist_dir} matching version='{args.version}', edition='{args.edition}'", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        return upload_packages(
            packages=packages,
            account_id=account_id or "dummy_account",
            access_key_id=access_key_id or "dummy_key",
            secret_access_key=secret_access_key or "dummy_secret",
            bucket_name=bucket_name or "dummy_bucket",
            prefix=prefix,
            public_url=public_url,
            dry_run=True
        )

    # Validate required credentials
    missing = []
    if not account_id:
        missing.append("R2_ACCOUNT_ID (--account-id)")
    if not access_key_id:
        missing.append("R2_ACCESS_KEY_ID (--access-key-id)")
    if not secret_access_key:
        missing.append("R2_SECRET_ACCESS_KEY (--secret-access-key)")
    if not bucket_name:
        missing.append("R2_BUCKET_NAME (--bucket)")

    if missing:
        print("[ERROR] Missing required Cloudflare R2 credentials/parameters:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print("\nPlease set these in your environment, pass via CLI options, or put in .env file.", file=sys.stderr)
        print("Tip: Run with --dry-run to preview files without credentials.", file=sys.stderr)
        sys.exit(1)

    exit_code = upload_packages(
        packages=packages,
        account_id=account_id,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        bucket_name=bucket_name,
        prefix=prefix,
        public_url=public_url,
        dry_run=False
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
