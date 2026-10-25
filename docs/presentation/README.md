# Presentation pages

Two standalone pages for presenting Fantadamus, modelled on gamegusto's. Open either file directly in a
browser. The fonts load from Google Fonts; without a network the pages fall back to system fonts.

| File | What it shows | Published copy (private until shared) |
|---|---|---|
| `product.html` | The product, for players: what to ask, sample answers, how it decides, cost, privacy, status | <https://claude.ai/artifact/DZG2BpHZaYeEA6wipC1rix> |
| `architecture.html` | How it's built: the MCP shape, one question end to end, storage, the engine, guardrails, gates, hosting, roadmap | <https://claude.ai/artifact/HkF2GGpUrHNN2DArB4aC7m> |

- **Sample answers** on the product page are the worked examples from the method's tests
  ([method §A9](../method.md)), with the players anonymised. They show the shape of an answer, not real
  data, and the page says so.
- **Figures** on both pages (tasks done, tests, coverage, checks, contracts, approved sites) were measured
  against the code on 25 October 2026. Update them when the system changes, and re-measure before sharing.
- **To republish** a page as a claude.ai artifact, drop its first four lines (the doctype, `html` and
  `meta` tags): the artifact host adds its own document wrapper.
