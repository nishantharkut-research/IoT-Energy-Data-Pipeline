import type { Counts, Evidence, Plan, Results, Run, Scope } from './types';
export const number = (value: number) => new Intl.NumberFormat('en-GB').format(value);
export const compact = (value: number) =>
  new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 }).format(value);
export const label = (value: string) =>
  value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
export const runName = (r: Run) => {
  if (r.experiment === 'recovery')
    return r.run_id.includes('interrupted_resumed')
      ? 'Recovery · Interrupted & resumed'
      : 'Recovery · Uninterrupted';
  if (r.experiment === 'watermark')
    return `Watermark · ${r.run_id.includes('restrictive') ? 'Restrictive' : 'Retaining'} · ${r.watermark}`;
  return r.event_count === 'fixture'
    ? `${label(r.experiment)} · ${label(r.fault)}`
    : `${r.event_count === 100000 ? '100K' : '1M'} · repetition ${Number(r.run_id.slice(-2))}`;
};
export function filterRuns(runs: Run[], family: string, query: string) {
  return runs.filter(
    (r) =>
      (family === 'all' ||
        (family === 'scale' ? typeof r.event_count === 'number' : r.experiment === family)) &&
      `${r.run_id} ${runName(r)}`.toLowerCase().includes(query.toLowerCase()),
  );
}
export async function verifyBytes(bytes: Uint8Array, expected: string, size: number) {
  const digest = await crypto.subtle.digest('SHA-256', new Uint8Array(bytes));
  const hex = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
  if (bytes.length !== size || hex !== expected)
    throw Error('Saved evidence binding failed. No results will be displayed.');
}
export function validateResults(results: Results, scope: Scope, plan: Plan) {
  const ids = results.runs.map((r) => r.run_id),
    expected = new Map(scope.completed_runs.map((r) => [r.run_id, r.run_manifest_sha256]));
  const planned = plan.runs
    .filter((r) => !scope.excluded_runs.includes(r.run_id))
    .map((r) => r.run_id);
  if (
    results.schema_version !== 'coursework-closure-v1' ||
    results.status !== 'complete_for_final_scope' ||
    ids.length !== 15 ||
    new Set(ids).size !== 15 ||
    expected.size !== 15 ||
    planned.length !== 15 ||
    ids.some((id) => !expected.has(id) || !planned.includes(id))
  )
    throw Error('Run scope does not match the completed experiment.');
  for (const r of results.runs) {
    if (r.status !== 'finalized' || expected.get(r.run_id) !== r.manifest_sha256)
      throw Error('Run scope binding failed.');
    for (const c of [r.source_comparison, r.aggregate_comparison])
      if (
        c.errors.length ||
        !c.exact_fields.length ||
        c.spark_record_count !== c.hadoop_record_count
      )
        throw Error('Recorded comparison does not agree.');
    if (r.source_records !== r.source_comparison.spark_record_count)
      throw Error('Source comparison count differs.');
    const l = r.layer_counts;
    if (
      l.bronze_deliveries !== l.parsed_valid_deliveries + l.quarantine_deliveries ||
      l.parsed_valid_deliveries !==
        l.silver_deliveries + l.duplicate_valid_deliveries + l.late_valid_deliveries
    )
      throw Error('Delivery conservation failed.');
  }
}
export function parseSourceCounts(text: string): Counts {
  const counts: Counts = {};
  for (const line of text.split('\n')) {
    const m = line.replace(/\r$/, '').match(/^\| ([^|]+?) \| ([\d,]+) \| ([\d,]+) \|$/);
    if (m)
      counts[m[1]] = {
        raw: Number(m[2].replaceAll(',', '')),
        clean: Number(m[3].replaceAll(',', '')),
      };
  }
  for (const v of ['raw', 'clean'] as const) {
    if (
      !counts['Physical data rows'] ||
      counts['Physical data rows'][v] !==
        counts['Finite numeric readings'][v] + counts['Missing numeric cells'][v]
    )
      throw Error('Source-row accounting is unavailable.');
  }
  return counts;
}
export async function loadEvidence(): Promise<Evidence> {
  const response = await fetch('/evidence/manifest.json', { cache: 'no-store' });
  if (!response.ok) throw Error('Evidence bundle is absent. Run npm run evidence.');
  const manifest: Evidence['manifest'] = await response.json();
  if (manifest.schema_version !== 'web-evidence-v1' || manifest.runtime_reverified !== false)
    throw Error('Unsupported evidence bundle.');
  const files = {
    results: 'final-results.json',
    scope: 'final-scope.json',
    plan: 'experiment-plan.json',
    source_audit: 'source-audit.md',
  };
  const docs: Record<string, string> = {};
  await Promise.all(
    Object.entries(files).map(async ([name, file]) => {
      const e = manifest.inputs[name];
      if (e?.file !== file) throw Error('Evidence file mapping is invalid.');
      const r = await fetch(`/evidence/${file}`, { cache: 'no-store' });
      if (!r.ok) throw Error(`Missing evidence: ${file}`);
      const bytes = new Uint8Array(await r.arrayBuffer());
      await verifyBytes(bytes, e.sha256, e.byte_size);
      docs[name] = new TextDecoder().decode(bytes).replace(/^\uFEFF/, '');
    }),
  );
  const results: Results = JSON.parse(docs.results),
    scope: Scope = JSON.parse(docs.scope),
    plan: Plan = JSON.parse(docs.plan);
  if (
    results.original_plan_sha256 !== manifest.inputs.plan.sha256 ||
    results.final_scope_sha256 !== manifest.inputs.scope.sha256 ||
    scope.original_plan_sha256 !== results.original_plan_sha256
  )
    throw Error('Original plan / scope binding differs.');
  validateResults(results, scope, plan);
  return { results, counts: parseSourceCounts(docs.source_audit), manifest };
}
export function download(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function exportCSV(runs: Run[]) {
  const rows = [
    ['Run', 'Family', 'Bronze', 'Silver', 'Gold', 'Duplicates', 'Late', 'Quarantine'],
    ...runs.map((r) => [
      r.run_id,
      r.experiment,
      r.layer_counts.bronze_deliveries,
      r.layer_counts.silver_deliveries,
      r.source_records,
      r.layer_counts.duplicate_valid_deliveries,
      r.layer_counts.late_valid_deliveries,
      r.layer_counts.quarantine_deliveries,
    ]),
  ];
  const data = rows
    .map((row) => row.map((c) => `"${String(c).replaceAll('"', '""')}"`).join(','))
    .join('\n');
  const url = URL.createObjectURL(new Blob([data], { type: 'text/csv' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = 'completed-runs.csv';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
