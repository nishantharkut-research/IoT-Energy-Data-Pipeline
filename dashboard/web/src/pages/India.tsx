import { Badge, Button } from '@mantine/core';
import {
  ArrowRight,
  Building2,
  Database,
  ExternalLink,
  FileCheck2,
  Network,
  ShieldCheck,
} from 'lucide-react';
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
export function India() {
  return (
    <>
      <div className="india-hero">
        <div>
          <Badge variant="light" color="teal">
            PROPOSED DISCOM REVIEW WORKFLOW
          </Badge>
          <h2>
            Installing a smart meter is only the start.
            <br />
            Its data still has to support a decision.
          </h2>
          <p>
            A distribution utility needs to distinguish unavailable readings, delivery exceptions
            and processing differences before relying on a meter-data report.
          </p>
        </div>
        <div className="india-symbol">
          <Building2 size={62} strokeWidth={1.3} />
          <span>
            Utility-side
            <br />
            data assurance
          </span>
        </div>
      </div>
      <Panel title="Where this project fits" eyebrow="ALONGSIDE AN EXISTING HES / MDM">
        <div className="utility-flow">
          {[
            { icon: Network, title: 'Meter / HES', text: 'Collect and communicate' },
            { icon: Database, title: 'MDM / VEE', text: 'Validate and manage' },
            { icon: ShieldCheck, title: 'Independent review', text: 'Account, rebuild, compare' },
            { icon: Building2, title: 'DISCOM analyst', text: 'Inspect evidence and limits' },
          ].map((n, i) => (
            <div className={i === 2 ? 'highlight' : ''} key={n.title}>
              <n.icon size={25} />
              <strong>{n.title}</strong>
              <span>{n.text}</span>
              {i < 3 && <ArrowRight className="utility-arrow" size={18} />}
            </div>
          ))}
        </div>
        <Note>
          The implemented evaluation uses HKUST telemetry and controlled replay. An Indian
          deployment would require utility data adapters, agreed contracts, access authorization and
          field validation.
        </Note>
      </Panel>
      <Panel
        title="Problem → implemented mechanism → available evidence"
        eyebrow="CONCRETE CONNECTION"
      >
        <DataTable
          columns={['Review problem', 'Implemented mechanism', 'What the project demonstrates']}
          rows={[
            [
              'A report hides source unavailability',
              'Source audit and separately retained quality exclusions',
              '19.04M missing numeric cells in the published HKUST resampled grid.',
            ],
            [
              'Retries or late arrivals alter an operational view',
              'Bronze delivery preservation, bounded Silver, exact Gold rebuild',
              'Combined fixture accounts for 432 deliveries; restrictive Silver 143, Gold 144.',
            ],
            [
              'A completed processing job is accepted without an independent check',
              'Independent Hadoop source and aggregate comparisons',
              'All 15 recorded runs agree on declared exact fields.',
            ],
            [
              'An incomplete comparison is presented as zero impact',
              'Matching-interval support and explicit unknown exposure',
              'Two incomparable periods are not priced as zero or invented savings.',
            ],
          ]}
        />
      </Panel>
      <div className="two-columns">
        <Panel title="What is already standard" eyebrow="POSITIONING">
          <p>
            Commercial meter-data systems already offer VEE, quality monitoring, raw retention and
            audit trails. Our coursework contribution is the reproducible combination of delivery
            accounting, exact finalization and a separately implemented computation.
          </p>
          <Note>No vendor-superiority or first-of-its-kind claim is made.</Note>
        </Panel>
        <Panel title="What the current evidence cannot establish" eyebrow="EVALUATION BOUNDARY">
          <ul className="plain-list">
            <li>Actual Indian billing errors or financial savings.</li>
            <li>Repair of radio links, wiring or physical meter calibration.</li>
            <li>Live AMI performance, prepaid balance safety or statutory compliance.</li>
            <li>National prevalence inferred from two utility environments.</li>
          </ul>
        </Panel>
      </div>
      <Panel title="Evidence behind the Indian connection" eyebrow="DATED SOURCES">
        <div className="source-cards">
          {indiaSources.map((s) => (
            <article key={s.name}>
              <div className="source-card-top">
                <FileCheck2 size={19} />
                <span>{s.date}</span>
              </div>
              <h3>{s.name}</h3>
              <p>{s.finding}</p>
              <small>{s.scope}</small>
              <Button
                component="a"
                href={s.url}
                target="_blank"
                rel="noreferrer"
                variant="subtle"
                size="xs"
                rightSection={<ExternalLink size={14} />}
              >
                Read source
              </Button>
            </article>
          ))}
        </div>
      </Panel>
    </>
  );
}
