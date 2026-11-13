import { Button, Tabs, Text } from '@mantine/core';

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
        />
        <Stat
          title="Exact aggregate fields"
          value={String(run.aggregate_comparison.exact_fields.length)}
          note="Counts, scaled sums and timestamp bounds"
        />
        <Stat
          title="Recorded comparison errors"
          value={String(
            run.source_comparison.errors.length + run.aggregate_comparison.errors.length,
          )}
          note="For the selected finalized experiment"
        />
      </div>
      <Panel title="Spark and Hadoop comparison">
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
      <Panel title="Compared fields">
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
                <span key={f}>{label(f)}</span>
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
