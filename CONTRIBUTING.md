# Contributing Index Entries

Submit one plugin bundle per pull request unless a dependency group must be
reviewed atomically. A submission must provide:

- a stable lowercase bundle ID and release version;
- publisher identity and a public HTTPS contact or project URL;
- a public source repository and immutable release/tag/commit reference;
- a valid SPDX expression or accepted LSO v1.4 `LicenseRef`, plus the complete
  license URL for a custom license;
- the exact PyPI distribution name in `project_id`;
- exact artifact URLs, byte lengths, and lowercase SHA-256 digests;
- the `cordis` runtime facet, platform restriction, `load.entry_points` values
  from the `liteyukibot.cordis_plugins` group, and requested capabilities;
- installation, startup, shutdown, update, rollback, and uninstall evidence;
- a security-reporting path controlled by the plugin publisher.

LSO-Commercial entries must say that commercial use requires separate
authorization in their summary or linked documentation. LSO-Private, missing
licenses, mutable artifact URLs, credential-bearing URLs, and artifacts that
cannot be publicly redistributed are rejected.

CI validates metadata but never imports or executes submitted plugin code.
Reviewers may download an artifact only to verify its declared size, digest,
archive safety, and package metadata. A listing confirms that the submitted
release meets the index contract; it is not a quality, safety, or compatibility
guarantee beyond the recorded evidence.

Security fixes may yank a release immediately. A yanked entry remains visible
with a reason so installed generations keep reproducible provenance, but
clients must reject new installation and update to that release.
