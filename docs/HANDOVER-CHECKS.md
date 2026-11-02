# Handover checks

Performed on 2 November 2026 against the completed local project.

| Check | Result |
| --- | --- |
| Unit, property, and contract suite | 565 passed, 11 skipped |
| Repository independence scan | Passed |
| Ruff on the closure script and edited dashboard | Passed |
| Closure evidence checks | Three tests passed: coverage, scope binding, and altered-output rejection |
| Actual browser: six dashboard tabs | Rendered without Streamlit exceptions |
| Actual browser: light theme | Visually inspected at 1440 and 1280 pixels wide |
| Actual browser: restrictive watermark | Two affected and incomparable periods; residual exposure displayed as Unknown |
| Actual browser: incomplete run | Rejected with missing manifest/seal message |

The test log and browser screenshots are retained locally under
`reports/generated/handover-20261102/`. Three generated LaTeX intermediates were
removed from Git tracking; the local files remain available. They are excluded
from the handover archive.

The final report generator freshly checks scope-bound run seals, published
Gold/Hadoop outputs, and report hashes in all 15 runs, then checks fault,
recovery, and watermark semantic comparisons. Checkpoints and operational logs
are covered by the original seals and are not rehashed in this handover check. Its
successful output is recorded in `results/final/final-results.json`, including
the verification timestamp. The original plan and scope hashes bind that output.

No new distributed experiment was executed for these checks. The previously
sealed distributed runs remain the evidence of actual Kafka, Spark, HDFS, and
Hadoop execution. Skipped lightweight tests are not presented as passed tests.
