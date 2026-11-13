import { useState } from 'react';
import { Select } from '@mantine/core';
import { FileStack, Layers, ShieldCheck } from 'lucide-react';
import {
  Bars,
  DataTable,
  Hash,
  Legend,
  Note,
  Panel,
  Stat,
  Status,
  palette,
} from '../components/Workspace';

import { label, number } from '../evidence';
import type { Evidence } from '../types';

export function Faults({ evidence }: { evidence: Evidence }) {
  const [fault, setFault] = useState('combined');
  const runs = evidence.results.runs.filter((r) => r.experiment === 'correctness');
  const run = runs.find((r) => r.fault === fault)!;
  const hashes = evidence.results.correctness_semantic_equivalence.run_hashes[run.run_id];
  return (
    <>
      <div className="stats-grid three">
        <Stat
          title="Controlled schedules"
          value={`${runs.length}`}
          note="Clean, duplicate, delayed, malformed, combined"
          icon={<FileStack size={20} />}
          accent="blue"
        />
        <Stat
          title="Final source events / schedule"
          value={number(run.source_records)}
          note="Same finalized population in every fixture"
          icon={<Layers size={20} />}
        />
        <Stat
          title="Semantic artifacts unchanged"
          value={`${Object.keys(hashes).length} / 4`}
          note="Corresponding output hashes agree"
          icon={<ShieldCheck size={20} />}
        />
      </div>
      <div className="two-columns wide-left">
        <Panel title="How the delivery counts change" eyebrow="FAULT DISPOSITION">
          <Legend
            items={[
              { label: 'Silver candidate', color: palette.teal },
              { label: 'Duplicate', color: palette.slate },
              { label: 'Quarantine', color: palette.amber },
            ]}
          />
          <Bars
            height={285}
            stacked
            data={runs.map((r) => ({
              name: label(r.fault),
              Silver: r.layer_counts.silver_deliveries,
              Duplicate: r.layer_counts.duplicate_valid_deliveries,
              Quarantine: r.layer_counts.quarantine_deliveries,
            }))}
            series={[
              { key: 'Silver', name: 'Silver', color: palette.teal },
              { key: 'Duplicate', name: 'Duplicate', color: palette.slate },
              { key: 'Quarantine', name: 'Quarantine', color: palette.amber },
            ]}
          />
          <span className="muted-small">
            Counts are deliveries. Gold retains 144 unique valid source events in every schedule.
          </span>
        </Panel>
        <Panel title="Inspect a schedule" eyebrow="RECORDED CASE">
          <Select
            label="Schedule"
            data={runs.map((r) => ({ value: r.fault, label: label(r.fault) }))}
            value={fault}
            onChange={(v) => v && setFault(v)}
            allowDeselect={false}
          />
          <div className="case-count">
            <strong>{number(run.layer_counts.bronze_deliveries)}</strong>
            <span>Bronze data deliveries</span>
          </div>
          <DataTable
            columns={['Outcome', 'Count']}
            rows={[
              ['Unique Gold events', run.source_records],
              ['Duplicate deliveries', run.layer_counts.duplicate_valid_deliveries],
              ['Quarantine deliveries', run.layer_counts.quarantine_deliveries],
            ]}
          />
          <Status>Semantic result unchanged</Status>
        </Panel>
      </div>
      <Panel title="Same answer, different delivery histories" eyebrow="CROSS-RUN EVIDENCE">
        <DataTable
          columns={['Semantic output', 'Selected schedule SHA-256', 'Result']}
          rows={Object.entries(hashes).map(([key, value]) => [
            label(key),
            <Hash value={value} />,
            <Status>Matches clean run</Status>,
          ])}
        />
      </Panel>
      <Note>
        These faults are controlled delivery schedules. They do not measure real utility failure
        rates, and unchanged retries do not imply a nonzero consumption error.
      </Note>
    </>
  );
}
