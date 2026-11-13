import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { validateResults, parseSourceCounts, verifyBytes, filterRuns } from './evidence';
const results = JSON.parse(
  readFileSync(new URL('../../../docs/results/final/final-results.json', import.meta.url), 'utf8'),
);
const scope = JSON.parse(
  readFileSync(
    new URL('../../../docs/results/final/final-coursework-scope.json', import.meta.url),
    'utf8',
  ),
);
const plan = JSON.parse(
  readFileSync(
    new URL('../../../docs/results/final/experiment-plan.json', import.meta.url),
    'utf8',
  ),
);
describe('saved evidence', () => {
  it('accepts the original 15-run scope', () =>
    expect(() => validateResults(results, scope, plan)).not.toThrow());
  it('rejects inconsistent delivery accounting', () => {
    const copy = structuredClone(results);
    copy.runs[0].layer_counts.bronze_deliveries++;
    expect(() => validateResults(copy, scope, plan)).toThrow(/conservation/);
  });
  it('rejects a comparison difference', () => {
    const copy = structuredClone(results);
    copy.runs[0].source_comparison.errors = ['difference'];
    expect(() => validateResults(copy, scope, plan)).toThrow(/comparison/);
  });
  it('rejects duplicate run identity', () => {
    const copy = structuredClone(results);
    copy.runs[1] = copy.runs[0];
    expect(() => validateResults(copy, scope, plan)).toThrow(/scope/);
  });
  it('keeps unknown exposure as null', () => {
    const run = results.runs.find(
      (r: { run_id: string }) => r.run_id === 'watermark-restrictive-r01',
    );
    expect(run.decision.tariff_scenarios[0].residual_exposure_after_verification).toBeNull();
  });
  it('uses published source-row counters', () => {
    const md = readFileSync(
      new URL('../../../docs/results/source-audit-2026-10-27.md', import.meta.url),
      'utf8',
    );
    const counts = parseSourceCounts(md);
    expect(counts['Missing numeric cells'].clean).toBe(19035190);
    expect(counts['Physical data rows'].clean).toBe(63273828);
  });
  it('checks actual bytes against the recorded digest', async () => {
    const bytes = readFileSync(
      new URL('../../../docs/results/final/final-results.json', import.meta.url),
    );
    await expect(
      verifyBytes(
        bytes,
        '1e18dbfeae8e708ab31e60b468afb9bbe04dc788176af532e2bf66885326dfcc',
        bytes.length,
      ),
    ).resolves.toBeUndefined();
    await expect(verifyBytes(bytes, '0'.repeat(64), bytes.length)).rejects.toThrow(/binding/);
  });
  it('filters the selected workload rather than inventing a new run', () => {
    expect(filterRuns(results.runs, 'scale', '')).toHaveLength(6);
    expect(filterRuns(results.runs, 'all', 'restrictive').map((r) => r.run_id)).toEqual([
      'watermark-restrictive-r01',
    ]);
  });
});
