"""Generate the official reference Cordis entry from a verified manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote, urlsplit

from validate_index import IndexValidationError, canonical_json, validate_path, validate_document

REFERENCE_DISTRIBUTION = "liteyukibot-v7-example-cordis-plugin"
REFERENCE_BUNDLE_ID = "liteyuki.reference.cordis"
REFERENCE_ENTRY_POINT = "liteyuki.reference.cordis"
OFFICIAL_REPOSITORY = "https://github.com/LiteyukiStudio/LiteyukiBot"


def _manifest(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IndexValidationError(f"cannot read Alpha manifest: {error}") from error
    if raw != json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"):
        raise IndexValidationError("Alpha manifest is not canonical UTF-8 JSON")
    if not isinstance(value, dict):
        raise IndexValidationError("Alpha manifest must be an object")
    release = value.get("release")
    if not isinstance(release, dict) or not isinstance(release.get("tag"), str):
        raise IndexValidationError("Alpha manifest has no release tag")
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or not all(isinstance(item, dict) for item in artifacts):
        raise IndexValidationError("Alpha manifest artifacts are invalid")
    return value


def _artifact(manifest: dict[str, object]) -> dict[str, object]:
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    matches = tuple(
        item
        for item in artifacts
        if isinstance(item, dict)
        and item.get("distribution") == REFERENCE_DISTRIBUTION
        and item.get("kind") == "wheel"
    )
    if len(matches) != 1:
        raise IndexValidationError(
            f"Alpha manifest must contain exactly one reference wheel; found {len(matches)}"
        )
    record = matches[0]
    required = {"filename", "bytes", "sha256", "distribution", "version", "kind"}
    if set(record) != required or record.get("version") != "0.1.0":
        raise IndexValidationError("reference wheel manifest record is incomplete")
    filename = record.get("filename")
    size = record.get("bytes")
    digest = record.get("sha256")
    if not isinstance(filename, str) or not filename.endswith(".whl"):
        raise IndexValidationError("reference wheel filename is invalid")
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise IndexValidationError("reference wheel byte size is invalid")
    if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise IndexValidationError("reference wheel digest is invalid")
    return {"filename": filename, "bytes": size, "sha256": digest}


def _release_base_url(tag: str) -> str:
    return f"{OFFICIAL_REPOSITORY}/releases/download/{quote(tag, safe='')}"


def _require_https(url: str, subject: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise IndexValidationError(f"{subject} must be credential-free HTTPS")


def build_entry(manifest: dict[str, object]) -> dict[str, object]:
    release = manifest["release"]
    assert isinstance(release, dict)
    tag = release["tag"]
    assert isinstance(tag, str)
    artifact = _artifact(manifest)
    artifact_url = f"{_release_base_url(tag)}/{quote(str(artifact['filename']), safe='')}"
    license_url = f"https://raw.githubusercontent.com/LiteyukiStudio/LiteyukiBot/{quote(tag, safe='')}/LICENSE.zh-CN"
    repository_url = f"{OFFICIAL_REPOSITORY}/tree/{quote(tag, safe='')}/examples/cordis-plugin"
    for subject, url in (
        ("artifact URL", artifact_url),
        ("license URL", license_url),
        ("repository URL", repository_url),
    ):
        _require_https(url, subject)
    return {
        "id": REFERENCE_BUNDLE_ID,
        "version": "0.1.0",
        "display_name": "LiteyukiBot Reference Cordis Plugin",
        "summary": "Executable reference for Alpha15 Cordis plugins.",
        "publisher": {
            "id": "liteyuki",
            "name": "Liteyuki Studio",
            "url": "https://github.com/LiteyukiStudio",
        },
        "license": {"expression": "LicenseRef-LSO-Common-1.4", "url": license_url},
        "repository": repository_url,
        "project_id": REFERENCE_DISTRIBUTION,
        "status": "active",
        "dependencies": [],
        "facets": [
            {
                "runtime_kind": "cordis",
                "artifacts": [],
                "wheels": [
                    {
                        "url": artifact_url,
                        "sha256": artifact["sha256"],
                        "bytes": artifact["bytes"],
                    }
                ],
                "platform": {"systems": [], "machines": [], "pythons": ["3.14"]},
                "load": {"entry_points": [REFERENCE_ENTRY_POINT]},
                "capabilities": [],
            }
        ],
    }


def write_index(manifest_path: Path, output_path: Path) -> None:
    """Replace the reference entry using artifact identity read from a manifest."""

    manifest = _manifest(manifest_path)
    entry = build_entry(manifest)
    if output_path.is_file():
        current = validate_path(output_path)
        bundles = current.get("bundles")
        assert isinstance(bundles, list)
        remaining = [bundle for bundle in bundles if isinstance(bundle, dict) and bundle.get("id") != entry["id"]]
    else:
        remaining = []
    document = validate_document({"schema": 2, "bundles": [*remaining, entry]})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(canonical_json(document), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_index(args.manifest, args.output)
    print(f"generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
