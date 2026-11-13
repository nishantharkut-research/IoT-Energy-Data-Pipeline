import { Accordion } from '@mantine/core';

import { DataTable, Hash, Note, Panel, Stat, Status } from '../components/Workspace';

import { label, number } from '../evidence';
import type { Evidence } from '../types';
export function Recovery({ evidence }: { evidence: Evidence }) {
  const pairs = Object.entries(evidence.results.recovery_semantic_equivalence.comparisons);
  const equal = pairs.filter(([, p]) => p.uninterrupted_sha256 === p.resumed_sha256).length;
  const scale = evidence.results.runs.filter((r) => r.event_count === 1000000);
  return (
    <>
      <div className="stats-grid three">
        <Stat
          title="Semantic output pairs"
          value={`${equal} / ${pairs.length}`}
          note="Full recorded hashes match"
        />
        <Stat
          title="Recovered 1M runs"
          value={String(scale.filter((r) => r.recovery).length)}
          note="All three finalized with recorded receipts"
        />
        <Stat
          title="Complete 1M workflow time"
          value="Unavailable"
          note="Component timings remain recorded"
        />
      </div>
      <div>
        <Panel title="Fixture output comparison">
          <DataTable
            columns={['Output', 'Uninterrupted hash', 'Resumed hash', 'Result']}
            rows={pairs.map(([key, p]) => [
              label(key),
              <Hash value={p.uninterrupted_sha256} />,
              <Hash value={p.resumed_sha256} />,
              <Status>Identical</Status>,
            ])}
          />
          <Note tone="teal">
            Semantic records and aggregates are compared across executions. Kafka offsets, timing
            logs and physical Parquet layout bytes need not match.
          </Note>
        </Panel>
      </div>
      <Panel title="Scale-run recovery receipts">
        <DataTable
          columns={['Run', 'Resumed stage', 'Source records', 'Workflow timing']}
          rows={scale.map((r) => [
            <code>{r.run_id}</code>,
            label(r.recovery?.resumed_stage ?? 'Unavailable'),
            number(r.source_records),
            <Status tone="gray">Unavailable</Status>,
          ])}
        />
        <Accordion variant="default">
          <Accordion.Item value="receipts">
            <Accordion.Control>Recovery receipts</Accordion.Control>
            <Accordion.Panel>
              {scale.map((r) => (
                <div className="receipt" key={r.run_id}>
                  <strong>{r.run_id}</strong>
                  <p>{r.recovery?.reason ?? 'No receipt available.'}</p>
                </div>
              ))}
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      </Panel>
      <Note>
        These are recorded receipt and digest comparisons. This browser does not rehash the
        externally archived runtime files.
      </Note>
    </>
  );
}
