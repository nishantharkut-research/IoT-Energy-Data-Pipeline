# Source audit: 27 October 2026

The verified Dryad v5 package contains separate raw and cleaned variants.
These counts come from the deposited files, not from the article's meter totals.

| Measurement | Raw | Clean |
| --- | ---: | ---: |
| Workbooks | 1,394 | 1,329 |
| Physical data rows | 50,903,710 | 63,273,828 |
| Workbook meters joined to Brick | 1,394 | 1,329 |
| Workbook meters without a Brick match | 0 | 0 |
| Repeated registration | Byte-identical | Byte-identical |
| Repeated profiling | Byte-identical | Byte-identical |

The graph has 1,432 meter references. It has 38 references without raw
workbooks and 103 without clean workbooks. The clean set excludes 65 raw
meters and introduces no new meter. Per-meter exclusion causes have not been
assigned from membership counts alone. The complete raw audit now shows that
these same 65 excluded meter workbooks have no physical data rows. This is an
observed file condition, not an attribution of the authors' exclusion decision.
All matched workbook meters have a
kWh unit. Multiple building memberships are retained.

## Complete telemetry audits

| Observation | Raw | Clean |
| --- | ---: | ---: |
| Finite numeric readings | 50,903,710 | 44,238,638 |
| Missing numeric cells | 0 | 19,035,190 |
| Negative readings | 134,612 | 134,612 |
| Zero readings | 1,651,811 | 1,330,732 |
| Ordered numeric decreases | 50,675 | 67,878 |
| Duplicate decoded timestamps | 853,595 | 0 |
| Out-of-order timestamps | 147 | 0 |
| Invalid decoded timestamps | 0 | 0 |
| Empty workbooks | 65 | 0 |

Every timestamp in both variants is naive. The audit assigns no
timezone. A decrease is not by itself a confirmed reset. These observations
do not constitute consumption, savings, or billing results.

The source reader retains stored numeric cell text before conversion to a
Python float can alter it. A bounded representation check found a signed-int64
failure in meter D0779: `26724.7` at its observed scale 15 requires the exact
integer `26724700000000000000`. The signed 38-digit storage contract passed an
actual Spark JSON/Parquet/JSON round trip, including its boundary values and
overflow rejection. This preserves stored decimals; it does not establish
physical measurement accuracy.

## Evidence

Local generated files are under `reports/generated/20261027/`:

- `package-verification.json`: wrapper and inner-archive hashes.
- `raw-manifest.json`, `clean-manifest.json`: registered source files.
- `registration-reproducibility.json`: repeated-manifest byte comparison.
- `profiling-reproducibility.json`: repeated-profile byte comparison.
- `raw-profile.json`, `clean-profile.json`: all-workbook structural profiles.
- `brick-coverage.json`: per-meter units, memberships, and join coverage.
- `clean-source-audit-exact.json`: exhaustive clean telemetry audit.
- `raw-source-audit-exact.json`: exhaustive raw telemetry audit.
- `int64-feasibility-prefix.json`: bounded precision-failure witnesses.
- `measurement-contract-candidates.json`: unit/scale candidates with no timezone.

Source files and generated row-level evidence are not committed. Real-data
canonicalization and scale measurements require the remaining evidence and
acceptance gates; synthetic fixture results are reported separately.
