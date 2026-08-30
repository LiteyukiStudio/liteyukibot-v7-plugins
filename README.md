# LiteyukiBot v7 Plugins

This repository owns the default metadata-only plugin index used by
LiteyukiBot v7:

```text
https://raw.githubusercontent.com/LiteyukiStudio/liteyukibot-v7-plugins/main/index.json
```

`index.json` is a schema-2 index. Alpha15 bundles use the current Cordis
contract: `project_id` identifies the PyPI distribution and the selected facet
uses `load.entry_points` to name entries in the
`liteyukibot.cordis_plugins` group. Each indexed bundle must provide a
compatible Python wheel with exact size and SHA-256 metadata.

The live index is currently empty because the packages previously registered
under the `liteyukibot-v7-*` names expose the historical
`liteyukibot.plugins` group and are not Alpha15-compatible. Add a bundle only
after its Alpha15 wheel has been published and its entry point has been
verified against the current host.

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

Generate a schema-2 reference entry from a signed release manifest rather than
predicting a wheel name or digest:

```bash
python scripts/generate_reference_index.py \
  --manifest artifacts.manifest.json \
  --output index.json
```

Run `python scripts/validate_index.py index.json` and submit the generated file
through the normal pull-request review.

## License

Repository metadata and validation code use LSO-Common v1.4. Indexed plugins
retain their declared licenses. The public index accepts SPDX expressions,
`LicenseRef-LSO-Common-1.4`, and conspicuously identified
`LicenseRef-LSO-Commercial-1.4`; it does not accept LSO-Private or artifacts
that cannot be redistributed publicly.
