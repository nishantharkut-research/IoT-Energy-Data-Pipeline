import { Bars, DataTable, Hash, Note, Panel, Stat, palette } from '../components/Workspace';
import { RunSelect } from '../components/RunSelect';
import { label, number } from '../evidence';
import type { Evidence, Run } from '../types';
export function Storage({
  evidence,
  run,
  setSelected,
}: {
  evidence: Evidence;
  run: Run;
  setSelected: (id: string) => void;
}) {
  const selected =
    typeof run.event_count === 'number'
      ? run
      : evidence.results.runs.find((r) => r.event_count === 100000)!;
  const p = evidence.results.performance_summary.find(
    (r) => r.event_count === selected.event_count,
  )!;
  const formats = selected.storage.formats;
  return (
    <>
      <div className="context-toolbar">
        <RunSelect evidence={evidence} run={selected} onChange={setSelected} scaleOnly />
        <span className="metadata">Three repetitions per scale / query</span>
      </div>
      <div className="stats-grid three">
        <Stat
          title="Verification median"
          value={`${(p.verification_seconds.median / 60).toFixed(2)} min`}
          note={`Range ${(p.verification_seconds.minimum / 60).toFixed(2)}–${(p.verification_seconds.maximum / 60).toFixed(2)} min`}
        />
        <Stat
          title="Verification artifact storage"
          value={`${(p.verification_bytes.median / 1e6).toLocaleString('en-GB', { maximumFractionDigits: 2 })} MB`}
          note="Median · decimal MB · scoped artifacts"
        />
        <Stat
          title="SQL workloads"
          value={String(selected.queries.results.length)}
          note="Full ordered results are hashed"
        />
      </div>
      <div className="two-columns">
        <Panel title="Verification time">
          <div className="chart-unit">Median verification time · minutes</div>
          <Bars
            data={evidence.results.performance_summary.map((p) => ({
              name: p.event_count === 100000 ? '100K events' : '1M events',
              Minutes: Number((p.verification_seconds.median / 60).toFixed(2)),
            }))}
            series={[{ key: 'Minutes', name: 'Median minutes', color: palette.blue }]}
            height={245}
          />
          <span className="muted-small">
            Gold finalization + layer audit + Hadoop + reconciliation. Not full workflow time.
          </span>
        </Panel>
        <Panel title="Stored size relative to NDJSON">
          <Bars
            percent
            data={[
              { name: 'NDJSON', Ratio: 100 },
              {
                name: 'Zstd Parquet',
                Ratio: formats.parquet_zstd_unpartitioned.relative_to_ndjson * 100,
              },
              {
                name: 'Partitioned',
                Ratio: formats.parquet_zstd_partitioned.relative_to_ndjson * 100,
              },
            ]}
            series={[{ key: 'Ratio', name: 'Stored size / NDJSON', color: palette.teal }]}
            height={245}
          />
          <span className="muted-small">
            NDJSON input: {(formats.ndjson.byte_size / 1e6).toFixed(2)} MB. Smaller ratio means less
            storage.
          </span>
        </Panel>
      </div>
      <Panel title="Read-only SQL measurements">
        <DataTable
          columns={[
            'Workload',
            'Result rows',
            'Minimum (s)',
            'Median (s)',
            'Maximum (s)',
            'Result binding',
          ]}
          rows={selected.queries.results.map((q) => [
            label(q.query),
            number(q.row_count),
            q.seconds.minimum.toFixed(3),
            <strong>{q.seconds.median.toFixed(3)}</strong>,
            q.seconds.maximum.toFixed(3),
            <Hash value={q.result_sha256} />,
          ])}
        />
        <Note>
          These cached-result timings include serialization, transfer and hashing. The 100K and 1M
          query configurations differ; they are not a controlled scaling comparison.
        </Note>
      </Panel>
    </>
  );
}
