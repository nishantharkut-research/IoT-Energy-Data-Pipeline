import type { Evidence } from '../types';
import { compact, number } from '../evidence';

import { ArrowRight, ExternalLink } from 'lucide-react';
import { DataTable, Note, Panel } from '../components/Workspace';
export const indiaSources = [
  {
    name: 'CSIS utility survey',
    date: '30 October 2026',
    scope: 'Original survey of TNPDCL and Tata Power–operated Odisha utilities.',
    finding:
      'Reports communication failures and data-integration limitations. Existing validation, estimation and editing are acknowledged.',
    url: 'https://www.csis.org/analysis/meters-machine-learning-building-ai-ready-utilities-india',
  },
  {
    name: 'MSEDCL AMISP procurement',
    date: '19 September 2022 · §2.4.4',
    scope:
      'An existing utility procurement requirement, not a nationwide compliance determination.',
    finding:
      'Requires original received raw data, VEE data and audit trails. Retention and validation are established practice.',
    url: 'https://www.mahadiscom.in/supplier/wp-content/uploads/2022/09/FILE_MMD_T-NSC-06_0922_version_1_1663594929641-Package-1.pdf',
  },
  {
    name: 'CAG Tripura audit',
    date: '2025 report · printed p. 144',
    scope: 'Historical project observations from 2018–2021, not a current national failure rate.',
    finding:
      'Records communication and missing management-reporting problems that prevented performance testing.',
    url: 'https://cag.gov.in/uploads/download_audit_report/2025/6--Chapter-4-069ccbc5e407049.02992125.pdf',
  },
];
export function India({ evidence }: { evidence: Evidence }) {
  const combined = evidence.results.runs.find((r) => r.run_id === 'correctness-combined-r01')!;
  const restrictive = evidence.results.runs.find((r) => r.run_id === 'watermark-restrictive-r01')!;
  return (
    <>
      <Panel title="Utility review workflow">
        <p>
          A DISCOM analyst reviewing metering-provider outputs needs to separate source gaps,
          delivery exceptions and processing differences. This project provides a reproducible check
          of received data and finalized results.
        </p>
        <div className="utility-flow">
          {['Meter / HES', 'MDM / VEE', 'Independent review', 'DISCOM analyst'].map((name, i) => (
            <div key={name}>
              <strong>{name}</strong>
              {i < 3 && <ArrowRight className="utility-arrow" size={18} />}
            </div>
          ))}
        </div>
        <Note>
          Evaluation uses HKUST telemetry and controlled replay. An Indian deployment would require
          authorized utility inputs, data adapters, agreed contracts and field validation.
        </Note>
      </Panel>
      <Panel title="Problem and available evidence">
        <DataTable
          columns={['Review question', 'Implemented mechanism', 'Existing result']}
          rows={[
            [
              'Was the source incomplete?',
              'Source audit and quality exclusions',
              `${compact(evidence.counts['Missing numeric cells'].clean)} missing numeric cells in the published HKUST resampled grid.`,
            ],
            [
              'Did delivery behaviour change the operational result?',
              'Preserve Bronze; bound Silver; rebuild exact Gold',
              `${number(combined.layer_counts.bronze_deliveries)} combined-fixture deliveries accounted for. Restrictive Silver ${restrictive.layer_counts.silver_deliveries}; Gold ${restrictive.source_records}.`,
            ],
            [
              'Does an independent computation agree?',
              'Hadoop source and aggregate comparison with Spark Gold',
              `All ${evidence.results.runs.length} saved runs agree on the declared exact fields.`,
            ],
            [
              'Is zero impact supported by sufficient coverage?',
              'Compare matching consumption intervals; retain unknown exposure',
              `${restrictive.decision.incomparable_meter_period_count} incomparable periods. Total financial exposure remains unknown.`,
            ],
          ]}
        />
      </Panel>
      <Panel title="Scope">
        <p>
          Commercial MDM systems already provide VEE, quality monitoring, raw retention and audit
          trails. The pipeline combines delivery accounting, exact finalization and a separately
          implemented computation.
        </p>
        <p>
          Gold can recover a received valid event omitted by Silver. A reading that never arrived
          remains unavailable. The evaluation establishes neither Indian billing savings nor live
          AMI reliability, physical-meter accuracy or statutory compliance.
        </p>
      </Panel>
      <Panel title="Indian sources">
        <div className="source-list">
          {indiaSources.map((s) => (
            <article key={s.name}>
              <h3>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.name}
                  <ExternalLink size={13} />
                </a>
                <span>{s.date}</span>
              </h3>
              <p>{s.finding}</p>
              <p className="muted-small">{s.scope}</p>
            </article>
          ))}
        </div>
      </Panel>
    </>
  );
}
