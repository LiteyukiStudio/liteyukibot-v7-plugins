# LiteyukiBot v7 Plugins

This repository owns the default metadata-only plugin index used by
LiteyukiBot v7:

```text
https://raw.githubusercontent.com/LiteyukiStudio/liteyukibot-v7-plugins/main/index.json
```

`index.json` initially remains a schema-1 empty index so existing Alpha clients
can fetch the endpoint before schema-2 support ships. Schema 2 adds publisher,
license, source, withdrawal, size, and discovery metadata covered by the index
digest. It becomes the live format only after `v7.0.0a12` is available.

The index does not host or execute plugin code. Every artifact is distributed
from a credential-free HTTPS URL and pinned by exact byte length and SHA-256.
An official listing is metadata review, not a sandbox or security endorsement.

## Validate

Use Python 3.14 or later:

```bash
python -m pip install --requirement requirements.txt
python scripts/validate_index.py index.json
python -m unittest discover -s tests -v
```

`index.json` must use the canonical, sorted, two-space-indented representation
emitted by the validator. Pull requests that change the index must also follow
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Repository metadata and validation code use LSO-Common v1.4. Indexed plugins
retain their declared licenses. The public index accepts SPDX expressions,
`LicenseRef-LSO-Common-1.4`, and conspicuously identified
`LicenseRef-LSO-Commercial-1.4`; it does not accept LSO-Private or artifacts
that cannot be redistributed publicly.
