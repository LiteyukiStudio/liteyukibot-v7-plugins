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


if __name__ == "__main__":
    unittest.main()
