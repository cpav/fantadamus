# Changelog: shared contracts

Each contract has a semantic version. A schema change needs a version bump and an entry here; a breaking
change (a field removed or renamed, a type or value set narrowed, a field newly required) needs a major bump
(R13.1 to R13.3). Headings are `## <Contract> <version> (<date>)`.

## BronzeEnvelope 1.0.0 (2026-10-25)

- First version: `source`, `source_url`, `published_at`, `captured_at`, `received_at`, `content_sha256`,
  `contract_version`, `submitted_by` and `payload` (R16.2).
