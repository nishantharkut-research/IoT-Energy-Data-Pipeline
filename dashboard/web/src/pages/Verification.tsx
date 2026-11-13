import { Button, Tabs, Text } from '@mantine/core';
import { Check, Database, FileStack, Layers, ShieldCheck } from 'lucide-react';
import { DataTable, ExactFields, Hash, Note, Panel, Stat, Status } from '../components/Workspace';

import { download, label, number } from '../evidence';
import type { Evidence, Run } from '../types';
import { RunSelect } from '../components/RunSelect';
export function Verification({
  evidence,
  run,
  setSelected,
}: {
  evidence: Evidence;
  run: Run;
  setSelected: (id: string) => void;
}) {
  return (
    <>
      <div className="context-toolbar">
        <RunSelect evidence={evidence} run={run} onChange={setSelected} />
        <Button
          variant="default"
          onClick={() =>
            download(`${run.run_id}-comparison.json`, {
              source: run.source_comparison,
              aggregates: run.aggregate_comparison,
            })
          }
        >
          Export comparison
        </Button>
      </div>
      <div className="stats-grid three">
        <Stat
          title="Exact source fields"
          value={String(run.source_comparison.exact_fields.length)}
          note="Identity, value, provenance and metadata"
          icon={<FileStack size={20} />}
          accent="blue"
        />
        <Stat
          title="Exact aggregate fields"
          value={String(run.aggregate_comparison.exact_fields.length)}
          note="Counts, scaled sums and timestamp bounds"
          icon={<Layers size={20} />}
          accent="blue"
        />
        <Stat
          title="Recorded comparison errors"
          value={String(
            run.source_comparison.errors.length + run.aggregate_comparison.errors.length,
          )}
          note="For the selected finalized experiment"
          icon={<ShieldCheck size={20} />}
        />
      </div>
      <Panel title="Two implementations, one declared comparison" eyebrow="SPARK ↔ HADOOP">
        <div className="verification-path">
          <div>
            <span className="engine-icon blue">
              <Layers size={24} />
            </span>
            <h3>Spark Gold</h3>
            <span>Rebuilt from Bronze</span>
          </div>
          <div className="agreement-line">
            <ShieldCheck size={24} />
            <strong>Exact agreement</strong>
            <small>Source + aggregate records</small>
          </div>
          <div>
            <span className="engine-icon teal">
              <Database size={24} />
            </span>
            <h3>Hadoop Streaming</h3>
            <span>Reads canonical NDJSON</span>
          </div>
        </div>
        <DataTable
          columns={['Output', 'Spark records', 'Hadoop records', 'Comparison']}
          rows={[
            [
              'Source events',
              number(run.source_comparison.spark_record_count),
              number(run.source_comparison.hadoop_record_count),
              <Status>Agreed</Status>,
            ],
            [
              'Aggregates',
              number(run.aggregate_comparison.spark_record_count),
              number(run.aggregate_comparison.hadoop_record_count),
              <Status>Agreed</Status>,
            ],
          ]}
        />
        <Note>
          Both engines share canonical preparation. This comparison checks downstream
          transformations, not physical meter accuracy or source normalization independently.
        </Note>
      </Panel>
      <Panel title="What is compared?" eyebrow="EXACT FIELD CONTRACT">
        <Tabs defaultValue="source">
          <Tabs.List>
            <Tabs.Tab value="source">
              Source fields · {run.source_comparison.exact_fields.length}
            </Tabs.Tab>
            <Tabs.Tab value="aggregate">
              Aggregate fields · {run.aggregate_comparison.exact_fields.length}
            </Tabs.Tab>
            <Tabs.Tab value="binding">Original manifest binding</Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="source" pt="lg">
            <ExactFields run={run} />
          </Tabs.Panel>
          <Tabs.Panel value="aggregate" pt="lg">
            <div className="field-list">
              {run.aggregate_comparison.exact_fields.map((f) => (
                <span key={f}>
                  <Check size={13} />
                  {label(f)}
                </span>
              ))}
            </div>
          </Tabs.Panel>
          <Tabs.Panel value="binding" pt="lg">
            <Hash value={run.manifest_sha256} />
            <Text size="sm" c="dimmed" mt="md">
              Original run-manifest digest, bound by the completed scope. Original runtime files are
              not loaded by this app.
            </Text>
          </Tabs.Panel>
        </Tabs>
      </Panel>
    </>
  );
}
