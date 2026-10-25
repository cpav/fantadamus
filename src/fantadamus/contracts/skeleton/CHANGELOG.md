# Changelog: skeleton contracts

Each contract has a semantic version. A schema change needs a version bump and an entry here; a breaking
change (a field removed or renamed, a type or value set narrowed, a field newly required) needs a major bump
(R13.1 to R13.3). Headings are `## <Contract> <version> (<date>)`.

## SkeletonPlayer 1.0.0 (2026-10-25)

- First version: `player_id`, `name`, `club` and `role` (Spec 0, C10).

## SkeletonPlayerRecord 1.0.0 (2026-10-25)

- First version of silver `skeleton_players`: the `SkeletonPlayer` fields plus `source_url`, `captured_at`
  and `bronze_sha256`.

## SkeletonRoleCount 1.0.0 (2026-10-25)

- First version of gold `skeleton_role_counts`: `club`, `role`, `n_players` and `source_urls`.
