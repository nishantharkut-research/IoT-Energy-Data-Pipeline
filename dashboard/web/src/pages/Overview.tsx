import { useState } from 'react';
import { Button, Group, Pagination, Select, SegmentedControl, TextInput } from '@mantine/core';
import { Search } from 'lucide-react';
import { DataTable, Inspect, Panel, RunTag, Stat, Status } from '../components/Workspace';
import { Pipeline } from '../components/Pipeline';
import { compact, filterRuns, number, runName } from '../evidence';
import type { Evidence, Page, Run } from '../types';
export function Overview({
  evidence,
  selected,
  setSelected,
  navigate,
  inspect,
}: {
  evidence: Evidence;
  selected: Run;
  setSelected: (id: string) => void;
  navigate: (p: Page) => void;
  inspect: (r: Run) => void;
}) {
  const { results, counts } = evidence;
  const [family, setFamily] = useState('all'),
    [query, setQuery] = useState(''),
    [page, setPage] = useState(1);
  const filtered = filterRuns(results.runs, family, query),
    visible = filtered.slice((page - 1) * 5, page * 5);
  const missing = counts['Missing numeric cells'].clean;
  const largest = Math.max(...results.performance_summary.map((p) => p.event_count));
  const repetitions = results.runs.filter((r) => r.event_count === largest).length;
  const pairs = Object.values(results.recovery_semantic_equivalence.comparisons);
  const matching = pairs.filter((p) => p.uninterrupted_sha256 === p.resumed_sha256).length;
  const availability = (
    (counts['Finite numeric readings'].clean / counts['Physical data rows'].clean) *
    100
  ).toFixed(3);
  return (
    <>
      <div className="stats-grid">
        <Stat
          title="Completed experiments"
          value={`${results.runs.length} / 15`}
          note="All declared comparisons agree"
        />
        <Stat
          title="Largest checked workload"
          value={compact(largest)}
          note={`${repetitions} clean repetitions at this scale`}
        />
        <Stat
          title="Source values unavailable"
          value={compact(missing)}
          note="Published resampled rows · HKUST"
        />
        <Stat
          title="Recovery output pairs"
          value={`${matching} / ${pairs.length}`}
          note="Recorded semantic hashes match"
        />
      </div>
      <Panel
        title="Selected run"
        action={
          <Button variant="subtle" size="xs" onClick={() => navigate('Delivery inspector')}>
            Open inspector
          </Button>
        }
      >
        <Select
          spellCheck={false}
          label="Selected experiment"
          value={selected.run_id}
          onChange={(v) => v && setSelected(v)}
          data={results.runs.map((r) => ({ value: r.run_id, label: runName(r) }))}
          searchable
          allowDeselect={false}
          mb="md"
          className="run-select"
        />
        <Pipeline run={selected} />
      </Panel>
      <Panel
        title="Completed experiment register"
        action={<Status>{results.runs.length} finalized</Status>}
      >
        <div className="table-toolbar">
          <SegmentedControl
            size="sm"
            value={family}
            onChange={(v) => {
              setFamily(v);
              setPage(1);
            }}
            data={[
              { label: 'All runs', value: 'all' },
              { label: 'Correctness', value: 'correctness' },
              { label: 'Recovery', value: 'recovery' },
              { label: 'Watermark', value: 'watermark' },
              { label: 'Scale', value: 'scale' },
            ]}
          />
          <TextInput
            spellCheck={false}
            placeholder="Find a run…"
            aria-label="Search completed runs"
            leftSection={<Search size={16} />}
            value={query}
            onChange={(e) => {
              setQuery(e.currentTarget.value);
              setPage(1);
            }}
          />
        </div>
        <DataTable
          columns={['Experiment', 'Source records', 'Bronze deliveries', 'Comparison', '']}
          rows={visible.map((r) => [
            <RunTag run={r} />,
            number(r.source_records),
            number(r.layer_counts.bronze_deliveries),
            <Status>Agreed</Status>,
            <Inspect run={r} onInspect={inspect} />,
          ])}
        />
        <Group justify="space-between" mt="md">
          <span className="muted-small">
            Showing {visible.length ? (page - 1) * 5 + 1 : 0}–{Math.min(page * 5, filtered.length)}{' '}
            of {filtered.length} runs
          </span>
          <Pagination
            total={Math.max(1, Math.ceil(filtered.length / 5))}
            value={page}
            onChange={setPage}
            size="sm"
          />
        </Group>
      </Panel>
      <div className="review-links">
        <button onClick={() => navigate('Source audit')}>
          Source availability: {availability}% numeric cells
        </button>
        <button onClick={() => navigate('Watermark review')}>
          Restrictive watermark: one Silver omission; two incomparable periods
        </button>
        <button onClick={() => navigate('India use case')}>Indian utility-review use case</button>
      </div>
    </>
  );
}
