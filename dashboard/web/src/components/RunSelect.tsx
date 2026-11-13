import { Select } from '@mantine/core';
import { runName } from '../evidence';
import type { Evidence, Run } from '../types';
export function RunSelect({
  evidence,
  run,
  onChange,
  scaleOnly = false,
}: {
  evidence: Evidence;
  run: Run;
  onChange: (id: string) => void;
  scaleOnly?: boolean;
}) {
  return (
    <Select
      spellCheck={false}
      label="Recorded experiment"
      description={
        typeof run.event_count === 'number'
          ? 'Selected real-data workload'
          : 'Controlled synthetic delivery fixture'
      }
      value={run.run_id}
      data={evidence.results.runs
        .filter((r) => !scaleOnly || typeof r.event_count === 'number')
        .map((r) => ({ value: r.run_id, label: runName(r) }))}
      onChange={(v) => v && onChange(v)}
      searchable
      allowDeselect={false}
      className="run-select"
    />
  );
}
