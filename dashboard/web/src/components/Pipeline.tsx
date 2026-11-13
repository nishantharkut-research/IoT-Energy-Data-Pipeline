import { ArrowRight } from 'lucide-react';
import { number } from '../evidence';
import type { Run } from '../types';
export function Pipeline({ run }: { run: Run }) {
  const l = run.layer_counts;
  const nodes = [
    {
      name: 'Canonical input',
      value: run.source_records,
      unit: 'source records',
    },
    {
      name: 'Bronze',
      value: l.bronze_deliveries,
      unit: 'data deliveries',
    },
    {
      name: 'Gold',
      value: run.source_records,
      unit: 'exact source records',
    },
    {
      name: 'Reconciliation',
      value: run.source_comparison.hadoop_record_count,
      unit: 'source records agree',
    },
  ];
  return (
    <div className="pipeline-board">
      <div className="pipeline-main">
        {nodes.map((n, i) => (
          <div className="pipeline-step" key={n.name}>
            <div className="pipeline-label">
              <span>{n.name}</span>
            </div>
            <strong>{number(n.value)}</strong>
            <small>{n.unit}</small>
            {i < 3 && <ArrowRight className="pipeline-arrow" size={19} />}
          </div>
        ))}
      </div>
      <div className="pipeline-bottom">
        <div className="silver-branch">
          <div>
            <strong>Silver candidate</strong>
            <span>{number(l.silver_deliveries)} records · watermark bounded</span>
          </div>
        </div>
        <div className="disposition-summary">
          <span>
            <i className="dot slate" />
            {number(l.duplicate_valid_deliveries)} duplicates
          </span>
          <span>
            <i className="dot amber" />
            {number(l.quarantine_deliveries)} quarantine
          </span>
          <span>{number(l.late_valid_deliveries)} late</span>
        </div>
      </div>
      <div className="pipeline-foot">
        Gold rebuilds from Bronze. Hadoop independently reads the shared canonical input.
      </div>
    </div>
  );
}
