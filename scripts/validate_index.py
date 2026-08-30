"""Validate and canonicalize the public LiteyukiBot plugin index."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from license_expression import ExpressionError, get_spdx_licensing

MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_GENERATION_INPUT_BYTES = 1024 * 1024 * 1024
MAX_GENERATION_INPUTS = 256
MAX_RESOLVED_BUNDLES = 128
MAX_LOAD_PLAN_BYTES = 64 * 1024

IDENTIFIER = re.compile(r"[a-z][a-z0-9-]{0,63}")
BUNDLE_IDENTIFIER = re.compile(r"[a-z][a-z0-9.-]{0,127}")
SHA256 = re.compile(r"[0-9a-f]{64}")
ALLOWED_LICENSE_REFS = {"LicenseRef-LSO-Common-1.4", "LicenseRef-LSO-Commercial-1.4"}


class IndexValidationError(ValueError):
    """Raised when the public index violates its versioned contract."""


@lru_cache(maxsize=256)
def _validate_license_expression(expression: str) -> None:
    """Validate SPDX syntax and the index's explicit custom-license allowlist."""

    licensing = _spdx_licensing()
    try:
        licensing.parse(expression, validate=False, strict=True)
    except ExpressionError as error:
        raise IndexValidationError("license expression has invalid SPDX syntax") from error
    validation = licensing.validate(expression, strict=True)
    invalid_symbols = {str(symbol) for symbol in validation.invalid_symbols}
    if invalid_symbols - ALLOWED_LICENSE_REFS:
        raise IndexValidationError("license expression contains an unknown or disallowed identifier")


@lru_cache(maxsize=1)
def _spdx_licensing() -> Any:
    """Return the immutable SPDX catalog without rebuilding its symbol table."""

    return get_spdx_licensing()


def canonical_json(document: object) -> str:
    """Return the repository's deterministic human-reviewable JSON form."""

    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _object(value: object, subject: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise IndexValidationError(f"{subject} must contain exactly {sorted(keys)}")
    return value


def _bounded_string(value: object, subject: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
        raise IndexValidationError(f"{subject} must be a trimmed string of at most {maximum} characters")
    return value


def _identifier(value: object, subject: str, *, bundle: bool = False) -> str:
    text = _bounded_string(value, subject, 128 if bundle else 64)
    if not (BUNDLE_IDENTIFIER if bundle else IDENTIFIER).fullmatch(text):
        raise IndexValidationError(f"{subject} must be a lowercase identifier")
    return text


def _https_url(value: object, subject: str) -> str:
    text = _bounded_string(value, subject, 2048)
    parsed = urlsplit(text)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise IndexValidationError(f"{subject} must be credential-free HTTPS")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise IndexValidationError(f"{subject} must not target a local hostname")
    try:
        address = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        return text
    if not address.is_global:
        raise IndexValidationError(f"{subject} must not target a private or reserved address")
    return text


def _string_array(value: object, subject: str, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise IndexValidationError(f"{subject} must be an array with at most {maximum} entries")
    items = tuple(_bounded_string(item, subject, 128) for item in value)
    if len(set(items)) != len(items):
        raise IndexValidationError(f"{subject} must not contain duplicates")
    return items


def _validate_v1(document: dict[str, Any]) -> None:
    _object(document, "schema-1 index", {"schema", "bundles"})
    if not isinstance(document["bundles"], list):
        raise IndexValidationError("schema-1 bundles must be an array")


def _validate_artifact(value: object, subject: str) -> tuple[str, int]:
    artifact = _object(value, subject, {"url", "sha256", "bytes"})
    _https_url(artifact["url"], f"{subject} URL")
    if not isinstance(artifact["sha256"], str) or not SHA256.fullmatch(artifact["sha256"]):
        raise IndexValidationError(f"{subject} SHA-256 must be 64 lowercase hexadecimal characters")
    size = artifact["bytes"]
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= MAX_ARTIFACT_BYTES:
        raise IndexValidationError(f"{subject} byte size is outside the allowed range")
    return artifact["sha256"], size


def _validate_facet(value: object, subject: str) -> tuple[int, int]:
    facet = _object(
        value,
        subject,
        {"runtime_kind", "artifacts", "wheels", "platform", "load", "capabilities"},
    )
    if facet["runtime_kind"] != "cordis":
        raise IndexValidationError(f"{subject} runtime kind must be 'cordis'")
    if not isinstance(facet["artifacts"], list) or not isinstance(facet["wheels"], list):
        raise IndexValidationError(f"{subject} inputs must be arrays")
    if facet["artifacts"]:
        raise IndexValidationError(f"{subject} contains non-wheel artifacts; Alpha15 accepts Python wheels only")
    inputs = [*facet["artifacts"], *facet["wheels"]]
    if not inputs or len(inputs) > MAX_GENERATION_INPUTS:
        raise IndexValidationError(f"{subject} must contain between 1 and {MAX_GENERATION_INPUTS} inputs")
    records = [_validate_artifact(item, f"{subject} input") for item in inputs]
    if len({digest for digest, _size in records}) != len(records):
        raise IndexValidationError(f"{subject} inputs must not repeat an artifact digest")
    total = sum(size for _digest, size in records)
    platform = _object(facet["platform"], f"{subject} platform", {"systems", "machines", "pythons"})
    _string_array(platform["systems"], f"{subject} systems", 16)
    _string_array(platform["machines"], f"{subject} machines", 32)
    pythons = _string_array(platform["pythons"], f"{subject} Pythons", 16)
    if any(not re.fullmatch(r"\d+\.\d+", item) for item in pythons):
        raise IndexValidationError(f"{subject} Python constraints must use major.minor form")
    if not isinstance(facet["load"], dict):
        raise IndexValidationError(f"{subject} load plan must be an object")
    if len(json.dumps(facet["load"], separators=(",", ":"), sort_keys=True).encode()) > MAX_LOAD_PLAN_BYTES:
        raise IndexValidationError(f"{subject} load plan is too large")
    load = _object(facet["load"], f"{subject} load plan", {"entry_points"})
    entry_points = _string_array(load["entry_points"], f"{subject} entry points", 64)
    if any(not BUNDLE_IDENTIFIER.fullmatch(item) for item in entry_points):
        raise IndexValidationError(f"{subject} entry points must be lowercase identifiers")
    _string_array(facet["capabilities"], f"{subject} capabilities", 128)
    return len(inputs), total


def _validate_v2(document: dict[str, Any]) -> None:
    _object(document, "schema-2 index", {"schema", "bundles"})
    bundles = document["bundles"]
    if not isinstance(bundles, list) or len(bundles) > 10_000:
        raise IndexValidationError("schema-2 bundles must be an array with at most 10000 entries")
    dependencies: dict[str, tuple[str, ...]] = {}
    project_owners: dict[str, str] = {}
    entry_point_owners: dict[str, str] = {}
    for position, raw_bundle in enumerate(bundles):
        subject = f"bundle {position}"
        required = {
            "id", "version", "display_name", "summary", "publisher", "license", "repository",
            "status", "dependencies", "facets", "project_id",
        }
        optional = {"homepage", "yanked_reason", "description", "tags", "compatibility", "gallery", "changelog"}
        if (
            not isinstance(raw_bundle, dict)
            or not required <= set(raw_bundle)
            or not set(raw_bundle) <= required | optional
        ):
            raise IndexValidationError(f"{subject} has missing or unknown fields")
        bundle_id = _identifier(raw_bundle["id"], f"{subject} ID", bundle=True)
        if bundle_id in dependencies:
            raise IndexValidationError(f"duplicate bundle ID {bundle_id!r}")
        _bounded_string(raw_bundle["version"], f"{subject} version", 64)
        _bounded_string(raw_bundle["display_name"], f"{subject} display name", 120)
        _bounded_string(raw_bundle["summary"], f"{subject} summary", 240)
        project_id = _identifier(raw_bundle["project_id"], f"{subject} project ID", bundle=True)
        previous_project = project_owners.setdefault(project_id, bundle_id)
        if previous_project != bundle_id:
            raise IndexValidationError(
                f"bundles {previous_project!r} and {bundle_id!r} share project ID {project_id!r}"
            )
        if "description" in raw_bundle:
            _bounded_string(raw_bundle["description"], f"{subject} description", 8192)
        for field, maximum in (("tags", 64), ("compatibility", 64), ("gallery", 64), ("changelog", 64)):
            if field in raw_bundle:
                _string_array(raw_bundle[field], f"{subject} {field}", maximum)
        publisher = _object(raw_bundle["publisher"], f"{subject} publisher", {"id", "name", "url"})
        _identifier(publisher["id"], f"{subject} publisher ID")
        _bounded_string(publisher["name"], f"{subject} publisher name", 80)
        _https_url(publisher["url"], f"{subject} publisher URL")
        license_value = raw_bundle["license"]
        if not isinstance(license_value, dict) or set(license_value) - {"expression", "url"}:
            raise IndexValidationError(f"{subject} license has unknown fields")
        expression = _bounded_string(license_value.get("expression"), f"{subject} license expression", 128)
        _validate_license_expression(expression)
        if "LicenseRef-" in expression and "url" not in license_value:
            raise IndexValidationError(f"{subject} custom license requires a URL")
        if "url" in license_value:
            _https_url(license_value["url"], f"{subject} license URL")
        _https_url(raw_bundle["repository"], f"{subject} repository")
        if "homepage" in raw_bundle:
            _https_url(raw_bundle["homepage"], f"{subject} homepage")
        if raw_bundle["status"] not in {"active", "yanked"}:
            raise IndexValidationError(f"{subject} status must be active or yanked")
        if raw_bundle["status"] == "yanked":
            _bounded_string(raw_bundle.get("yanked_reason"), f"{subject} yanked reason", 240)
        elif "yanked_reason" in raw_bundle:
            raise IndexValidationError(f"{subject} active release cannot have a yanked reason")
        bundle_dependencies = tuple(
            _identifier(item, f"{subject} dependency", bundle=True)
            for item in _string_array(raw_bundle["dependencies"], f"{subject} dependencies", 64)
        )
        dependencies[bundle_id] = bundle_dependencies
        facets = raw_bundle["facets"]
        if not isinstance(facets, list) or not 1 <= len(facets) <= 16:
            raise IndexValidationError(f"{subject} must contain between 1 and 16 facets")
        kinds: set[str] = set()
        input_count = 0
        input_bytes = 0
        for facet_position, facet in enumerate(facets):
            count, size = _validate_facet(facet, f"{subject} facet {facet_position}")
            kind = facet["runtime_kind"]
            if kind in kinds:
                raise IndexValidationError(f"{subject} repeats runtime kind {kind!r}")
            kinds.add(kind)
            for entry_point in facet["load"]["entry_points"]:
                previous_entry_point = entry_point_owners.setdefault(entry_point, bundle_id)
                if previous_entry_point != bundle_id:
                    raise IndexValidationError(
                        f"bundles {previous_entry_point!r} and {bundle_id!r} share entry point {entry_point!r}"
                    )
            input_count += count
            input_bytes += size
        if input_count > MAX_GENERATION_INPUTS or input_bytes > MAX_GENERATION_INPUT_BYTES:
            raise IndexValidationError(f"{subject} exceeds the generation input budget")

    def closure(root: str, visiting: set[str], visited: set[str]) -> None:
        if root in visited:
            return
        if root in visiting:
            raise IndexValidationError(f"dependency cycle includes {root!r}")
        if root not in dependencies:
            raise IndexValidationError(f"unknown dependency {root!r}")
        visiting.add(root)
        for dependency in dependencies[root]:
            closure(dependency, visiting, visited)
        visiting.remove(root)
        visited.add(root)
        if len(visited) > MAX_RESOLVED_BUNDLES:
            raise IndexValidationError(f"dependency closure for {root!r} exceeds {MAX_RESOLVED_BUNDLES} bundles")

    for bundle_id in dependencies:
        closure(bundle_id, set(), set())


def validate_document(document: object) -> dict[str, Any]:
    """Validate one parsed index and return its object form."""

    if not isinstance(document, dict):
        raise IndexValidationError("plugin index must be an object")
    schema = document.get("schema")
    if isinstance(schema, bool):
        raise IndexValidationError("plugin index schema must be 1 or 2")
    if schema == 1:
        _validate_v1(document)
    elif schema == 2:
        _validate_v2(document)
    else:
        raise IndexValidationError("plugin index schema must be 1 or 2")
    return document


def validate_path(path: Path) -> dict[str, Any]:
    """Read, validate, and require canonical JSON from one path."""

    try:
        raw = path.read_text(encoding="utf-8")
        document = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IndexValidationError(f"cannot read plugin index: {error}") from error
    validated = validate_document(document)
    if raw != canonical_json(validated):
        raise IndexValidationError("plugin index is not canonical sorted two-space JSON")
    return validated


def main() -> int:
    """Run the command-line validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    arguments = parser.parse_args()
    validate_path(arguments.path)
    print(f"validated {arguments.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
