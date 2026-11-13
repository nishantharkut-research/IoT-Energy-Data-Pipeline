# Submission verification

13 November 2026. This record covers the final report, desktop presentation and supporting code. The report cover identifies Nishant Harkut (2023IMG-040) and instructor Amandeep Kaur. The current layout scope is desktop. No new distributed experiment was executed. Commands, input bindings and exact check results are in [verification.json](verification.json); presentation asset hashes are in [asset-manifest.json](asset-manifest.json).

| Check | Result |
| --- | --- |
| Python unit, contract and property checks | 582 passed, 7 skipped |
| Frontend evidence tests | 8 passed |
| TypeScript and Vite production build | Passed, including strict unused-import checking |
| Prettier and Ruff | Passed |
| Repository independence and Git whitespace | Passed |
| Desktop layout | 74 rendered layout/state cases passed across eight desktop sizes, from 1024×768 to 1920×1080 |
| Browser interactions | Source and watermark switching, register search/pagination, run inspection, delivery tabs, provenance, exact original JSON download and CSV export passed |
| Mutated summary input | Viewer rejected it before displaying affirmative results |
| Production build | All nine views, metric alignment, watermark spacing, count-table fit, menus, dialogs and selected 1M results passed; the prior fresh-install record is retained with its revision |
| Report download | Served PDF digest matches the current tracked report |
| Standalone LaTeX source | Compiles independently with 14 figure/table assets to 22 pages |
| Vector figures | All box labels have internal clearance; repeated PDF/SVG generation is byte-identical in the checked environment |
| PDF | 22 pages: technical report plus nine landscape application captures; two vector diagrams; no unresolved references or overfull boxes |
| Additional independent reviewer | Unavailable because of usage limit; no successful review claimed for this revision |

The regression check reproduced the old watermark defect as a 0.125 px gap between neighbouring text. The corrected production build passes the spacing check. The forced table minimum was removed, metric labels now reserve a consistent height, and 1M conservation equations use full width on smaller desktop windows. Mobile-specific changes explored during investigation were discarded.

The seven Python skips are four Windows-specific rename cases, one mutation fixture whose size condition is not applicable, one duplicate-sheet case openpyxl cannot construct, and one PySpark-dependent check because PySpark is absent. Docker/Kafka/Spark/Hadoop integration workloads were not rerun.

The production bundle triggers Vite's size advisory (about 938 kB before gzip). It builds and renders successfully; the advisory is not a measured dashboard-performance result.

Original final-results, scope, plan and published source-audit bytes remain unchanged. The original artifact verification date is 2 November 2026. This checkout checks the saved summaries and their bindings; it does not contain or freshly reverify the original runtime trees, complete dataset or original audit JSON. These checks establish declared byte bindings and consistency, not physical measurement truth or adversarial authenticity.

The Indian connection is a sourced proposed DISCOM review role alongside HES/MDM. It is not an evaluated Indian deployment, billing-saving result or replacement for commercial VEE.
