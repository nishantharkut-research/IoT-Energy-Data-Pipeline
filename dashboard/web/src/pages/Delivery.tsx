import { Tabs } from '@mantine/core';
import { ClipboardCheck, FileStack, Layers } from 'lucide-react';
import { DataTable, Hash, Panel, Stat, Status } from '../components/Workspace';
import { Pipeline } from '../components/Pipeline';
import { number } from '../evidence';
import type { Evidence, Run } from '../types';
import { RunSelect } from '../components/RunSelect';
export function Delivery({
  evidence,
  run,
  setSelected,
}: {
  evidence: Evidence;
  run: Run;
  setSelected: (id: string) => void;
}) {
  const l = run.layer_counts;
  return (
    <>
      <div className="context-toolbar">
        <RunSelect evidence={evidence} run={run} onChange={setSelected} />
        <Status>Conservation holds</Status>
      </div>
      <div className="stats-grid three">
        <Stat
          title="Bronze deliveries"
          value={number(l.bronze_deliveries)}
          note="Every data delivery is retained"
        />
        <Stat
          title="Silver candidate"
          value={number(l.silver_deliveries)}
          note="Operational watermark-bounded result"
        />
        <Stat
          title="Exact Gold"
          value={number(run.source_records)}
          note="Unique valid source identities"
        />
      </div>
      <Panel title="Delivery path">
        <Tabs defaultValue="path">
          <Tabs.List>
            <Tabs.Tab value="path" leftSection={<Layers size={16} />}>
              Pipeline
            </Tabs.Tab>
            <Tabs.Tab value="accounting" leftSection={<ClipboardCheck size={16} />}>
              Accounting
            </Tabs.Tab>
            <Tabs.Tab value="contract" leftSection={<FileStack size={16} />}>
              Run contract
            </Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="path" pt="xl">
            <Pipeline run={run} />
            <div className="equation-grid">
              <div>
                <span>Data deliveries</span>
                <strong>
                  {number(l.bronze_deliveries)} <i>=</i> {number(l.parsed_valid_deliveries)}{' '}
                  <small>valid</small> <i>+</i> {number(l.quarantine_deliveries)}{' '}
                  <small>quarantine</small>
                </strong>
              </div>
              <div>
                <span>Valid disposition</span>
                <strong>
                  {number(l.parsed_valid_deliveries)} <i>=</i> {number(l.silver_deliveries)}{' '}
                  <small>Silver</small> <i>+</i> {number(l.duplicate_valid_deliveries)}{' '}
                  <small>duplicate</small> <i>+</i> {number(l.late_valid_deliveries)}{' '}
                  <small>late</small>
                </strong>
              </div>
            </div>
          </Tabs.Panel>
          <Tabs.Panel value="accounting" pt="lg">
            <DataTable
              columns={['Disposition', 'Deliveries', 'What it means']}
              rows={[
                [
                  <Status>Silver</Status>,
                  number(l.silver_deliveries),
                  'Valid operational candidate',
                ],
                [
                  <Status tone="gray">Duplicate</Status>,
                  number(l.duplicate_valid_deliveries),
                  'Repeated delivery of an existing source event',
                ],
                [
                  <Status tone="amber">Late valid</Status>,
                  number(l.late_valid_deliveries),
                  'Valid source event outside Silver acceptance',
                ],
                [
                  <Status tone="amber">Quarantine</Status>,
                  number(l.quarantine_deliveries),
                  'Malformed or contract-violating delivery',
                ],
              ]}
            />
          </Tabs.Panel>
          <Tabs.Panel value="contract" pt="lg">
            <DataTable
              columns={['Parameter', 'Recorded value']}
              rows={[
                ['Run identity', <code>{run.run_id}</code>],
                ['Watermark', run.watermark],
                ['Partitions', run.partition_count],
                ['Offsets per trigger', number(run.max_offsets_per_trigger)],
                ['Seed', run.seed],
                ['Manifest binding', <Hash value={run.manifest_sha256} />],
              ]}
            />
          </Tabs.Panel>
        </Tabs>
      </Panel>
      <details className="processing-notes">
        <summary>Processing and completion rules</summary>
        <p>
          Silver releases state to remain bounded. Gold rebuilds exact source identities from Bronze
          after replay completion. Late valid records have a separate disposition from quarantine.
        </p>
        <p>
          {l.terminal_records} terminal partition records are separate from data deliveries.
          Acknowledgements, partition termination and layer counts are checked before finalization.
        </p>
      </details>
    </>
  );
}
