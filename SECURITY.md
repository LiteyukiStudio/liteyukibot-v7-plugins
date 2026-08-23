# Security Policy

Do not open a public issue for an unpatched vulnerability in an indexed plugin,
the index validator, or the LiteyukiBot plugin installer. Use GitHub private
vulnerability reporting for the affected LiteyukiStudio repository. When the
problem belongs to a third-party plugin, also use the publisher's security
contact linked from its repository.

Maintainers may yank an affected entry while preserving its ID, version, hash,
and reason. Yanking prevents new installs; it does not delete a user's already
verified local generation. Revocation of already running code requires an
operator decision because LiteyukiBot does not claim hostile-code containment.

The official index is authenticated by GitHub HTTPS and protected repository
governance. Artifacts are separately pinned by size and SHA-256. This model does
not protect against compromise of repository administrators, GitHub, or a
plugin publisher before the reviewed bytes are indexed.
