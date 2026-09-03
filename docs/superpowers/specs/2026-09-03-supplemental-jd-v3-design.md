# Supplemental JD v3 integration design

## Scope

Ingest all 49 records from the supplied supplemental JD text as an immutable incremental source. Preserve every `standard*_v1.xlsx`, the 191-row official JD dataset, all `EMERGING-001` through `EMERGING-011` identities, and the existing commercial white frontend design.

## Data flow

`supplemental TXT -> parser -> structured records -> skill extraction -> joint deduplication -> existing-candidate mapping/new-candidate clustering -> emerging_jobs_v2 -> API/static fallback -> existing Emerging page`

The ingestion module is independent from API routing. It emits `SUP-JD-001` through `SUP-JD-049`, retains complete source text and source line ranges, records failures for manual review, and asserts parsed plus failed equals 49. Missing URLs or dates remain empty and lower evidence confidence.

## Deduplication and statistics

Supplemental records are compared with the frozen 191-JD corpus and with one another using normalized full-text SHA-256, normalized company/title keys, company-title-URL keys, text similarity, and skill-set similarity. Duplicates remain auditable but do not count in statistics; possible duplicates remain visible and require review.

## Candidate mapping

Existing candidate IDs and names are loaded from `outputs/emerging_jobs_v1.json`. Exact role evidence is weighted fully; related job-family evidence is retained separately and does not masquerade as exact evidence. Independent role clusters create consecutive IDs after `EMERGING-011`. V1 scores and confidence remain unchanged; V2 fields are additive, and singleton candidates cannot exceed weak/watch confidence.

## Outputs and compatibility

The pipeline writes the required JSON/XLSX artifacts under `data/external` and `outputs`. `SystemDataService` prefers V2 and falls back atomically to V1 if V2 is absent or invalid. Existing list/detail API routes remain unchanged. The frontend consumes V2 transparently and adds version, updated time, V1/V2 confidence, and complete evidence details without changing the site theme or page layout system.

## Verification

Automated tests cover 49-record conservation, heading variants, continuous IDs, field segmentation, skill extraction, joint deduplication, old/new mappings, non-counting duplicates, missing-source behavior, API list/detail compatibility, frontend production build, output consistency, and before/after frozen-file SHA-256 equality. The final report includes screenshots and all requested audit lists.
