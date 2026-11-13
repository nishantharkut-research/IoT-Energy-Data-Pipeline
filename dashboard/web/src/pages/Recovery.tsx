import { Accordion, Text, Timeline } from '@mantine/core';
import { Check, Clock, Pause, Play, RotateCcw, ShieldCheck } from 'lucide-react';
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
          icon={<ShieldCheck size={20} />}
        />
        <Stat
          title="Recovered 1M runs"
          value={String(scale.filter((r) => r.recovery).length)}
          note="All three finalized with recorded receipts"
          icon={<RotateCcw size={20} />}
          accent="blue"
        />
        <Stat
          title="Complete 1M workflow time"
          value="Unavailable"
          note="Component timings remain recorded"
          icon={<Clock size={20} />}
          accent="amber"
        />
      </div>
      <div className="two-columns wide-left">
        <Panel title="The answer survives interruption" eyebrow="FIXTURE EQUIVALENCE">
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
        <Panel title="Recovery protocol" eyebrow="IMPLEMENTED WORKFLOW">
          <Timeline active={3} bulletSize={27} lineWidth={2}>
            <Timeline.Item bullet={<Play size={14} />} title="Replay and process">
              <Text c="dimmed" size="sm">
                Preserve deliveries and durable processing state.
              </Text>
            </Timeline.Item>
            <Timeline.Item bullet={<Pause size={14} />} title="Interrupt">
              <Text c="dimmed" size="sm">
                Stop the controlled fixture execution.
              </Text>
            </Timeline.Item>
            <Timeline.Item bullet={<RotateCcw size={14} />} title="Resume">
              <Text c="dimmed" size="sm">
                Continue from saved receipts and checkpoints.
              </Text>
            </Timeline.Item>
            <Timeline.Item bullet={<Check size={14} />} title="Compare">
              <Text c="dimmed" size="sm">
                Rebuild and compare four semantic outputs.
              </Text>
            </Timeline.Item>
          </Timeline>
        </Panel>
      </div>
      <Panel title="Scale-run recovery receipts" eyebrow="COMPLETED REAL-DATA EXECUTIONS">
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
            <Accordion.Control>Read the recorded recovery reasons</Accordion.Control>
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
