from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_index import (
    IndexValidationError,
    _validate_license_expression,
    canonical_json,
    validate_document,
    validate_path,
)
from generate_reference_index import build_entry


class IndexValidationTests(unittest.TestCase):
    def test_committed_empty_index_is_canonical_schema_one(self) -> None:
        self.assertEqual(validate_path(ROOT / "index.json"), {"schema": 1, "bundles": []})

    def test_schema_two_metadata_and_artifact_are_accepted(self) -> None:
        document = {
            "schema": 2,
            "bundles": [
                {
                    "id": "example.echo",
                    "version": "1.0.0",
                    "display_name": "Example Echo",
                    "summary": "A bounded example plugin.",
                    "publisher": {"id": "example", "name": "Example", "url": "https://example.invalid"},
                    "license": {"expression": "MIT"},
                    "repository": "https://example.invalid/source",
                    "status": "active",
                    "dependencies": [],
                    "facets": [
                        {
                            "runtime_kind": "nonebot",
                            "artifacts": [],
                            "wheels": [
                                {
                                    "url": "https://example.invalid/example.whl",
                                    "sha256": "a" * 64,
                                    "bytes": 1024,
                                }
                            ],
                            "platform": {"systems": [], "machines": [], "pythons": ["3.14"]},
                            "load": {"plugins": ["example_echo"]},
                            "capabilities": [],
                        }
                    ],
                }
            ],
        }

        self.assertEqual(validate_document(document), document)
        self.assertEqual(json.loads(canonical_json(document)), document)

    def test_schema_two_rejects_private_literal_url(self) -> None:
        document = {"schema": 2, "bundles": []}
        validate_document(document)
        document["bundles"] = [
            {
                "id": "example.echo",
                "version": "1",
                "display_name": "Echo",
                "summary": "Echo plugin.",
                "publisher": {"id": "example", "name": "Example", "url": "https://127.0.0.1"},
                "license": {"expression": "MIT"},
                "repository": "https://example.invalid/source",
                "status": "active",
                "dependencies": [],
                "facets": [],
            }
        ]

        with self.assertRaisesRegex(IndexValidationError, "private or reserved"):
            validate_document(document)

    def test_schema_two_rejects_unknown_bundle_metadata(self) -> None:
        document = {
            "schema": 2,
            "bundles": [
                {
                    "id": "example.echo",
                    "version": "1",
                    "display_name": "Echo",
                    "summary": "Echo plugin.",
                    "publisher": {"id": "example", "name": "Example", "url": "https://example.invalid"},
                    "license": {"expression": "MIT"},
                    "repository": "https://example.invalid/source",
                    "status": "active",
                    "dependencies": [],
                    "facets": [
                        {
                            "runtime_kind": "nonebot",
                            "artifacts": [],
                            "wheels": [
                                {
                                    "url": "https://example.invalid/example.whl",
                                    "sha256": "a" * 64,
                                    "bytes": 1024,
                                }
                            ],
                            "platform": {"systems": [], "machines": [], "pythons": []},
                            "load": {"plugins": ["example_echo"]},
                            "capabilities": [],
                        }
                    ],
                    "unknown": True,
                }
            ],
        }

        with self.assertRaisesRegex(IndexValidationError, "unknown fields"):
            validate_document(document)

    def test_schema_two_rejects_repeated_artifact_digest(self) -> None:
        document = {
            "schema": 2,
            "bundles": [
                {
                    "id": "example.echo",
                    "version": "1",
                    "display_name": "Echo",
                    "summary": "Echo plugin.",
                    "publisher": {"id": "example", "name": "Example", "url": "https://example.invalid"},
                    "license": {"expression": "MIT"},
                    "repository": "https://example.invalid/source",
                    "status": "active",
                    "dependencies": [],
                    "facets": [
                        {
                            "runtime_kind": "nonebot",
                            "artifacts": [
                                {
                                    "url": "https://example.invalid/one.zip",
                                    "sha256": "a" * 64,
                                    "bytes": 1024,
                                }
                            ],
                            "wheels": [
                                {
                                    "url": "https://example.invalid/two.whl",
                                    "sha256": "a" * 64,
                                    "bytes": 1024,
                                }
                            ],
                            "platform": {"systems": [], "machines": [], "pythons": []},
                            "load": {"plugins": ["example_echo"]},
                            "capabilities": [],
                        }
                    ],
                }
            ],
        }

        with self.assertRaisesRegex(IndexValidationError, "repeat"):
            validate_document(document)

    def test_schema_boolean_is_not_a_schema_version(self) -> None:
        with self.assertRaisesRegex(IndexValidationError, "schema must be 1 or 2"):
            validate_document({"schema": True, "bundles": []})

    def test_schema_two_rejects_dependency_cycle(self) -> None:
        def bundle(bundle_id: str, dependency: str) -> dict[str, object]:
            return {
                "id": bundle_id,
                "version": "1",
                "display_name": bundle_id,
                "summary": "Cycle fixture.",
                "publisher": {"id": "example", "name": "Example", "url": "https://example.invalid"},
                "license": {"expression": "MIT"},
                "repository": "https://example.invalid/source",
                "status": "active",
                "dependencies": [dependency],
                "facets": [
                    {
                        "runtime_kind": "nonebot",
                        "artifacts": [],
                        "wheels": [
                            {"url": "https://example.invalid/plugin.whl", "sha256": "b" * 64, "bytes": 1}
                        ],
                        "platform": {"systems": [], "machines": [], "pythons": []},
                        "load": {"plugins": ["example"]},
                        "capabilities": [],
                    }
                ],
            }

        with self.assertRaisesRegex(IndexValidationError, "dependency cycle"):
            validate_document(
                {
                    "schema": 2,
                    "bundles": [
                        bundle("example.first", "example.second"),
                        bundle("example.second", "example.first"),
                    ],
                }
            )

    def test_license_validation_uses_spdx_symbols_and_explicit_lso_allowlist(self) -> None:
        _validate_license_expression("MIT OR LicenseRef-LSO-Common-1.4")
        _validate_license_expression("LicenseRef-LSO-Commercial-1.4")

        with self.assertRaisesRegex(IndexValidationError, "unknown or disallowed"):
            _validate_license_expression("Definitely-Not-SPDX")
        with self.assertRaisesRegex(IndexValidationError, "unknown or disallowed"):
            _validate_license_expression("LicenseRef-LSO-Private-1.4")

    def test_reference_entry_uses_manifest_artifact_identity(self) -> None:
        manifest = {
            "release": {"tag": "v7.0.0a12", "version": "7.0.0a12"},
            "artifacts": [
                {
                    "filename": "liteyukibot_v7_example_nonebot_plugin-0.1.0-py3-none-any.whl",
                    "bytes": 1234,
                    "sha256": "a" * 64,
                    "distribution": "liteyukibot-v7-example-nonebot-plugin",
                    "version": "0.1.0",
                    "kind": "wheel",
                }
            ],
        }

        entry = build_entry(manifest)
        wheel = entry["facets"][0]["wheels"][0]
        self.assertEqual(wheel["bytes"], 1234)
        self.assertEqual(wheel["sha256"], "a" * 64)
        self.assertIn("liteyukibot_v7_example_nonebot_plugin-0.1.0-py3-none-any.whl", wheel["url"])


if __name__ == "__main__":
    unittest.main()
