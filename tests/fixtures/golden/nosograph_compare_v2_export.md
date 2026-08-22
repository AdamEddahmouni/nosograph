# NosoGraph comparison

**Status:** `comparable`

## Conditions

- Condition 1 (`MONDO:0000001`)
- Condition 2 (`MONDO:0000002`)
- Condition 3 (`MONDO:0000003`)

## Dimensions

Phenotype, Gene, Pathway, Treatment, Evidence coverage

## Phenotype

### Shared

- **All conditions:** `HP:0000001`
- **Condition 1, Condition 2:** `HP:0000002`

### Distinct

- **Condition 1:** `HP:0000003`, `HP:0000007`
- **Condition 2:** `HP:0000004`
- **Condition 3:** `HP:0000005`, `HP:0000006`

### Missing data

- `HP:0000002` — Condition 3: `NOT_RECORDED`
- `HP:0000003` — Condition 2: `NOT_RECORDED`; Condition 3: `NOT_RECORDED`
- `HP:0000004` — Condition 1: `NOT_RECORDED`; Condition 3: `NOT_RECORDED`
- `HP:0000005` — Condition 1: `NOT_RECORDED`; Condition 2: `NOT_RECORDED`
- `HP:0000006` — Condition 1: `KNOWN_ABSENT`; Condition 2: `NOT_RECORDED`
- `HP:0000007` — Condition 2: `NOT_RECORDED`; Condition 3: `NOT_RECORDED`

### Evidence coverage

| Condition | Claims | Positive | Negated | Evidence | Sources | Snapshots |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Condition 1 | 6 | 4 | 2 | 6 | 1 | 1 |
| Condition 2 | 3 | 3 | 0 | 3 | 1 | 1 |
| Condition 3 | 3 | 3 | 0 | 3 | 1 | 1 |

### Warnings

- MONDO:0000001 has positive and negated assertions for HP:0000007 in phenotype; PRESENT takes precedence.

## Gene

### Shared

- **Condition 1, Condition 2:** `HGNC:1`
- **Condition 1, Condition 2:** `HGNC:2`
- **Condition 1, Condition 2:** `HGNC:3`

### Distinct

- **Condition 1:** `HGNC:4`, `HGNC:5`, `HGNC:6`

### Missing data

- `HGNC:1` — Condition 3: `NOT_RECORDED`
- `HGNC:2` — Condition 3: `NOT_RECORDED`
- `HGNC:3` — Condition 3: `NOT_RECORDED`
- `HGNC:4` — Condition 2: `NOT_RECORDED`; Condition 3: `NOT_RECORDED`
- `HGNC:5` — Condition 2: `NOT_RECORDED`; Condition 3: `NOT_RECORDED`
- `HGNC:6` — Condition 2: `NOT_RECORDED`; Condition 3: `NOT_RECORDED`

### Evidence coverage

| Condition | Claims | Positive | Negated | Evidence | Sources | Snapshots |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Condition 1 | 6 | 6 | 0 | 6 | 1 | 1 |
| Condition 2 | 3 | 3 | 0 | 3 | 1 | 1 |
| Condition 3 | 0 | 0 | 0 | 0 | 0 | 0 |

### Warnings

- Positive gene claim counts differ by at least 2x and by at least 3 claims.
- No positive gene claims are recorded for: MONDO:0000003.

## Pathway

### Shared

- **All conditions:** `REACT:R-HSA-1`

### Distinct

- **Condition 1:** `REACT:R-HSA-2`

### Missing data

- `REACT:R-HSA-2` — Condition 2: `NOT_RECORDED`; Condition 3: `NOT_RECORDED`

### Evidence coverage

| Condition | Claims | Positive | Negated | Evidence | Sources | Snapshots |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Condition 1 | 2 | 2 | 0 | 2 | 1 | 1 |
| Condition 2 | 1 | 1 | 0 | 1 | 1 | 1 |
| Condition 3 | 1 | 1 | 0 | 1 | 1 | 1 |

### Warnings

No warnings were recorded for this dimension.

## Treatment

### Shared

- **All conditions:** `DRUG:1`

### Distinct

No condition-distinct entities were recorded.

### Missing data

No missing-data cells were recorded.

### Evidence coverage

| Condition | Claims | Positive | Negated | Evidence | Sources | Snapshots |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Condition 1 | 1 | 1 | 0 | 1 | 1 | 1 |
| Condition 2 | 1 | 1 | 0 | 1 | 1 | 1 |
| Condition 3 | 1 | 1 | 0 | 1 | 1 | 1 |

### Warnings

No warnings were recorded for this dimension.

## Evidence coverage

### Shared

This dimension summarizes evidence coverage rather than entity membership.

### Distinct

No condition-distinct entities were recorded.

### Missing data

No missing-data cells were recorded.

### Evidence coverage

| Condition | Claims | Positive | Negated | Evidence | Sources | Snapshots |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Condition 1 | 15 | 13 | 2 | 15 | 1 | 1 |
| Condition 2 | 8 | 8 | 0 | 8 | 1 | 1 |
| Condition 3 | 5 | 5 | 0 | 5 | 1 | 1 |

### Warnings

- Positive evidence\_coverage claim counts differ by at least 2x and by at least 3 claims.

## Curation warnings

- Positive evidence\_coverage claim counts differ by at least 2x and by at least 3 claims.
- Positive gene claim counts differ by at least 2x and by at least 3 claims.
- No positive gene claims are recorded for: MONDO:0000003.
- MONDO:0000001 has positive and negated assertions for HP:0000007 in phenotype; PRESENT takes precedence.

## Reproducibility

- **Run ID:** `555ef2e2-2330-58eb-bf3c-2c1bd3dcc6f0`
- **Result schema:** `2.0`
- **Algorithm:** `nosograph-compare-v2` `2.0.0`
- **Claim-set fingerprint:** `9a694a40affb26e10a5589d88c26f831276e5567fe74fe1f287b1b8657569ce7`
- **Snapshot IDs:** `6b040219-cfe7-5cbe-b038-d8f1525ba591`

## Research-use disclaimer

> For research and exploratory analysis only. Results summarize supporting evidence and contradictory evidence from imported biomedical sources. Not for clinical decision-making, treatment recommendations, or probability-of-disease claims.
