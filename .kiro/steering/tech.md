---
inclusion: always
---

# Technology

Decisions marked **pending ADR** are proposals until their ADR in `docs/adr/` is approved. No code may
depend on a pending decision (research gate, `quality.md`).

## Shape of the system

- **Two releases** (see `product.md`). In the **MVP**, Fantadamus's collector fetches the round's facts from
  the approved pages on the user's Mac, on demand and on a schedule, under ADR-0004's rules
  ([ADR-0006](../../docs/adr/0006-mvp-fantadamus-collects-round-facts.md), proposed). When a page can't be
  read, each user's Claude collects it instead: the MCP tools say what's missing and where to read it, Claude
  submits structured facts ([ADR-0005](../../docs/adr/0005-mvp-claude-collects-tools-decide.md)). The tools
  validate everything, store it in a DuckDB/Parquet medallion and answer from the data products. **v1**
  automates ingestion on AWS, as described below.
- **v1: AWS, serverless-first, batch plus micro-batch.** Most data moves on a fixture-driven batch
  schedule. One path is near-real-time: **official lineups**, which need minutes, not hours.
- **Collect once, serve many.** All facts land in a lakehouse on a refresh schedule; questions are answered
  from precomputed gold data products. The chat model never browses per question.
- **Single AWS account for v1: the account the owner's `gamegusto` project already uses** (owner
  decision, 2026-10-17; recorded in ADR-0003). The AWS Budgets alarm filters on `Project=fantadamus`.
  Projects are isolated by the `fantadamus-` name prefix, a permissions boundary and a scoped
  deploy role (see "Deploy identity" below).
- Region: **pending ADR-0003.** Proposal: `eu-north-1` (Stockholm), where the account already runs
  gamegusto, if S3 Tables, Glue Data Quality, Lake Formation and Iceberg materialized views are available
  there; otherwise `eu-west-1`.

## MVP: collector mode

| Concern | MVP choice | Notes |
|---|---|---|
| Interface | **MCP server** exposing the Fantadamus tools to each user's Claude app | stdio on the owner's Mac first; then a remote endpoint (AWS Lambda) for the second user. Auth for the remote endpoint is decided in the `chat-agent` MVP design |
| Collection | **Fantadamus's collector** fetches the approved pages (robots.txt honoured, one request a second per host, an identifying user agent) when `compare_players` needs a fact and on a schedule; **the user's Claude app** collects only what the collector couldn't, guided by the refresh plan | Pages, readers and cadences are in the `mvp-collect` spec; stdlib-only fetching unless its design's ADR says otherwise |
| Submission | MCP **submit tools** whose input schemas are the pydantic contracts | Validated for contract, allowed source host, name resolution and quality rules; a rejection returns its reason |
| Bronze | The submitted payload with its source URL, the source's publication time, `received_at` and a content hash | No page text is stored ([ADR-0005](../../docs/adr/0005-mvp-claude-collects-tools-decide.md), guardrail 4) |
| Freshness | Per data product, for example probable lineups a few hours, fixtures a week; a refresh by one user serves both | Targets are set in Spec 1; the refresh plan lists whatever is past its target |
| Storage | **DuckDB over Parquet**, same medallion layout and contracts as v1 | Local `data/private/` first; the same layout on a private S3 prefix once the endpoint is remote |
| Approved for v1, unused in the MVP | Brave Search, The Odds API, API-Football (registry D-S6, D-T1); search-driven fetching (ADR-0004) | They return when v1 automates collection; ADR-0006 brings only fetching of the approved fixed pages forward |

The MVP doesn't use Iceberg, Glue, Athena, Step Functions or EventBridge. Those arrive with v1.

## Data platform (v1)

| Concern | Choice | Notes |
|---|---|---|
| Storage | Medallion lakehouse on S3 with **Apache Iceberg** | Bronze: raw, immutable, timestamped, hashed snapshots per source. Silver: normalised, resolved, validated tables. Gold: data products read by the engine and agent. |
| Iceberg flavour | **S3 Tables** (managed) vs self-managed Iceberg on general-purpose S3, **pending ADR in Spec 1** | AWS guidance points small teams to S3 Tables and notes self-managed can be cheaper for small, infrequent workloads. Decide on cost per refresh at our volumes. |
| Catalog and governance | AWS Glue Data Catalog, Lake Formation permissions | |
| Query | Amazon Athena | |
| Transforms | AWS Glue (PySpark or Python shell) or Lambda, **whichever is cheaper per job** | Evaluate Iceberg materialized views for silver and gold. Their limits: minimum refresh interval one hour, refreshes don't cascade, deletes need a full refresh. **The official-lineup fast path must not depend on them.** |
| Orchestration | EventBridge Scheduler (schedules generated from the fixture calendar) and Step Functions (one state machine per source pipeline) | |
| Data quality | AWS Glue Data Quality (or equivalent) plus pydantic data contracts in the repo | Each rule is defined once and runs on fixtures in CI, on DuckDB locally and in AWS after each ingestion. |
| Local dev mode | **DuckDB** reading the same Parquet and Iceberg data | Tests run in seconds without AWS. |

### Data mesh, sized honestly

Data mesh solves an *organisational* scaling problem (many teams, many domains). For v1:

- adopt its **product thinking**: domain-oriented data products, each with an owner, a contract, a
  freshness target and a catalog entry;
- run in **one AWS account**;
- Spec 1's design documents the path to multi-account governance (Amazon DataZone / SageMaker Catalog,
  data.all, Lake Formation-only), with costs, and recommends whether any of it is worth adopting now.

## Infrastructure as code

**CDK or Terraform, pending ADR-0002**, decided in Phase 3 when the AWS work is built (moved from Spec 0
by the 2026-10-26 re-plan). Leaning: **Terraform (≥ 1.11)**. The owner already
runs Terraform in the same AWS account (gamegusto), with a reviewed least-privilege bootstrap, a deploy
role, a permissions boundary and a policy evaluator that we reuse rather than rebuild in CDK. The
toolchain is `terraform fmt`, `validate`, `tflint`, `checkov`, and `terraform test` with `override_data`
or mock providers so that CI plans offline, plus the IAM policy evaluator. Terraform is licensed under
BSL 1.1, which is fine for our own use; OpenTofu is a drop-in, MPL-2.0 alternative. CDK's advantages
(Python tests, cdk-nag) are real but don't outweigh reusing a proven model. Either way:

- the **AWS Budgets alarm is in the first module applied** (the bootstrap);
- infrastructure is synthesised and policy-checked in CI, and is **never deployed from CI** without the
  owner's approval (deploy gate, `quality.md`).

### Deploy identity (pattern from gamegusto)

```text
owner's admin identity ──applies once──▶ infra/bootstrap/   (local state, git-ignored)
                                          state bucket · permissions boundary · deploy role · budget
fantadamus-terraform   ──assume──▶ fantadamus-deploy ──applies──▶ infra/stack/   (remote state)
   (assume-only user)                (prefix-scoped, bounded, ≤ 1 h sessions)
```

- Every Allow is scoped to `fantadamus-*` ARNs; the security lives in the Deny statements: no changes to
  its own role, policy, boundary or user; no role without the boundary; `iam:PassRole` only to the services
  we use. Service wildcards over scoped ARNs keep the policy under IAM's 6,144-character limit.
- List and describe APIs that reject scoped ARNs are granted on `"*"`, each with a reason. Secret-reading
  actions (`ssm:GetParameter`) are never granted on `"*"`.
- Terraform never creates access keys (they would land in state). A GitHub OIDC principal can be added to
  the deploy role's trust later, without changing any policy, if deploys ever move into CI.

## Language and tooling

- **Python 3.12**, managed with **uv**, with a committed `uv.lock`. `src/` layout.
- **pytest** with Hypothesis; pydantic v2 for contracts; DuckDB locally; moto for AWS mocks.
- The full toolchain and the gates are in `quality.md`. Tool choices are confirmed in ADR-0001.
- Hosting and CI: a **public** GitHub repository on the Free plan (enforced rulesets, free Actions minutes,
  secret scanning with push protection), with GitHub Actions.
- Node.js is a build-time dependency only if CDK is chosen (the CDK CLI), and for markdownlint.

## LLM use

- **MVP:** our code calls no LLM. Each user's Claude does the reading and extraction while collecting,
  and its output is validated against our contracts (ADR-0005). The conversation and the collection both
  run in the users' own Claude apps, so neither is on our bill.
- **v1:** a small model extracts structured data from permitted unstructured sources, and parses questions
  when the alias table fails.
- Use a small model; validate its JSON against the schema; cache results by URL plus content hash; store a
  confidence score and provenance with every extracted claim.
- All lineup arithmetic is deterministic Python with tests, never model reasoning.

## Cost guardrails

- A monthly cost estimate in every design.md that adds AWS resources.
- An **AWS Budgets alarm from day one**.
- **Ask the owner before adding any paid service** beyond the agreed stack (S3, S3 Tables, Glue, Athena,
  Lake Formation, Lambda, Step Functions, EventBridge, CloudWatch, Budgets, plus the LLM API for extraction;
  the candidate is Amazon Bedrock, already enabled in the account for gamegusto, and the choice is an ADR in Spec 1).
  This includes paid SaaS such as GitHub plans and third-party data feeds. The free plans of the Brave
  Search API, The Odds API and API-Football are agreed for v1 (the MVP uses none of them); moving any of
  them to a paid plan needs approval.

### Parametric token-cost model

Spec 1's design compares (a) an agent that browses per question with (b) ingest-once, serve-many, in
tokens, with prices as inputs and nothing hardcoded. Starting shape (refined in design.md):

```text
Let U = users, R = rounds, q = questions per user per round,
    S = sources, f = refreshes per source per round,
    t_page = tokens per fetched page, t_extract = extraction tokens per page,
    t_card = tokens of precomputed cards per answer, t_sys / t_ans = system prompt / answer tokens.

(a) per-question browsing:  T_a = U·R·q · (S·t_page + t_sys + t_ans)
(b) ingest once:            T_b = R·S·f·t_extract  +  U·R·q · (t_card + t_sys + t_ans)

Crossover when U·q · (S·t_page − t_card) = S·f·t_extract,
i.e. (b) wins once U·q > S·f·t_extract / (S·t_page − t_card).
```

## Decision audit (method §A8)

Every probability the engine publishes (p_start, P(scores), P(clean sheet), and the market's de-margined
equivalent where one exists) is logged append-only with its as-of time and the snapshots it used. After each
round a calibration report scores them (Brier score, reliability by probability bucket) next to the market
and the users' overrides; the *(start)* constants are recalibrated from it.

## Time and identifiers

- Store timestamps in UTC (`captured_at`, `published_at`); show kickoffs and deadlines in `Europe/Rome`.
- The player master ID is the official list's `Id`.

## References

Cite these in design.md where they inform a decision:

- AWS Big Data Blog, [Navigating architectural choices for a lakehouse using Amazon SageMaker](https://aws.amazon.com/blogs/big-data/navigating-architectural-choices-for-a-lakehouse-using-amazon-sagemaker/)
- AWS Big Data Blog, [Building medallion architecture with Iceberg materialized views in Amazon SageMaker](https://aws.amazon.com/blogs/big-data/building-medallion-architecture-with-iceberg-materialized-views-in-amazon-sagemaker/)
- [Guidance for Data Lakes on AWS](https://docs.aws.amazon.com/solutions/data-lakes-on-aws/)
- [Deploy and manage a serverless data lake on the AWS Cloud by using infrastructure as code](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/deploy-and-manage-a-serverless-data-lake-on-the-aws-cloud-by-using-infrastructure-as-code.html)
- [Data mesh principles](https://docs.aws.amazon.com/guidance/latest/automotive-data-platform-on-aws/data-mesh-principles-section.html) and [AWS implementation options](https://docs.aws.amazon.com/guidance/latest/automotive-data-platform-on-aws/data-mesh-aws-options-section.html)
- [Strategies for building a data mesh-based enterprise solution on AWS](https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/strategy-data-mesh/strategy-data-mesh.pdf)
- [Build an enterprise data mesh with Amazon DataZone, AWS CDK, and AWS CloudFormation](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/build-enterprise-data-mesh-amazon-data-zone.html)
- [Implement a data mesh pattern in Amazon SageMaker Catalog](https://aws.amazon.com/blogs/big-data/implement-a-data-mesh-pattern-with-amazon-sagemaker-catalog-without-making-changes-to-your-applications/)
- [Getting started with AWS Glue Data Quality from the AWS Glue Data Catalog](https://aws.amazon.com/blogs/big-data/getting-started-with-aws-glue-data-quality-from-the-aws-glue-data-catalog/)
- Testing and delivery references are listed in `quality.md`.
