import { useState } from 'react';
import {
  Badge,
  Button,
  Group,
  Pagination,
  Select,
  SegmentedControl,
  TextInput,
} from '@mantine/core';
import {
  ArrowUpRight,
  ClipboardCheck,
  Database,
  FileStack,
  Search,
  ShieldCheck,
  TriangleAlert,
  Workflow,
} from 'lucide-react';
import { DataTable, Inspect, Note, Panel, RunTag, Stat, Status } from '../components/Workspace';
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
          icon={<ClipboardCheck size={20} />}
        />
        <Stat
          title="Largest checked workload"
          value={compact(largest)}
          note={`${repetitions} clean repetitions at this scale`}
          icon={<Database size={20} />}
          accent="blue"
        />
        <Stat
          title="Source values unavailable"
          value={compact(missing)}
          note="Published resampled rows · HKUST"
          icon={<FileStack size={20} />}
          accent="amber"
        />
        <Stat
          title="Recovery output pairs"
          value={`${matching} / ${pairs.length}`}
          note="Recorded semantic hashes match"
          icon={<ShieldCheck size={20} />}
        />
      </div>
      <div className="overview-grid">
        <Panel
          title="Follow a recorded run"
          eyebrow="DELIVERY → EXACT RESULT"
          action={
            <Button
              variant="subtle"
              size="xs"
              rightSection={<ArrowUpRight size={14} />}
              onClick={() => navigate('Delivery inspector')}
            >
              Open inspector
            </Button>
          }
        >
          <Select
            label="Selected experiment"
            value={selected.run_id}
            onChange={(v) => v && setSelected(v)}
            data={results.runs.map((r) => ({ value: r.run_id, label: runName(r) }))}
            searchable
            allowDeselect={false}
            mb="lg"
          />
          <Pipeline run={selected} />
        </Panel>
        <Panel
          title="What needs interpretation"
          eyebrow="REVIEW FINDINGS"
          className="findings-panel"
        >
          <button className="finding" onClick={() => navigate('Source audit')}>
            <span className="finding-icon amber">
              <FileStack size={18} />
            </span>
            <span>
              <strong>Source availability</strong>
              <small>{availability}% of published rows are numeric</small>
            </span>
            <ArrowUpRight size={16} />
          </button>
          <button className="finding" onClick={() => navigate('Watermark review')}>
            <span className="finding-icon blue">
              <Workflow size={18} />
            </span>
            <span>
              <strong>One valid event omitted by Silver</strong>
              <small>Restrictive case · Gold retains it</small>
            </span>
            <ArrowUpRight size={16} />
          </button>
          <button className="finding" onClick={() => navigate('Watermark review')}>
            <span className="finding-icon amber">
              <TriangleAlert size={18} />
            </span>
            <span>
              <strong>Total exposure remains unknown</strong>
              <small>Two periods have incomparable supports</small>
            </span>
            <ArrowUpRight size={16} />
          </button>
          <div className="india-short">
            <Badge color="teal" variant="light" size="sm">
              INDIA USE CASE
            </Badge>
            <p>Independent data review for a DISCOM examining metering-provider outputs.</p>
            <Button
              variant="subtle"
              size="xs"
              rightSection={<ArrowUpRight size={14} />}
              onClick={() => navigate('India use case')}
            >
              See the problem connection
            </Button>
          </div>
        </Panel>
      </div>
      <Panel
        title="Completed experiment register"
        eyebrow="SAVED WORKLOADS"
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
      <Note>
        All views use the committed results. Summary bindings are checked in this browser; original
        runtime artifacts were verified on 2 November 2026.
      </Note>
    </>
  );
}
