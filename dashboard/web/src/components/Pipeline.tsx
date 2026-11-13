import {
  Database,
  FileStack,
  Layers,
  ShieldCheck,
  ArrowRight,
  ArrowDownRight,
  TriangleAlert,
} from 'lucide-react';
import { number } from '../evidence';
import type { Run } from '../types';
export function Pipeline({ run }: { run: Run }) {
  const l = run.layer_counts;
  const nodes = [
    {
      name: 'Canonical input',
      value: run.source_records,
      unit: 'source records',
      icon: FileStack,
      tone: 'slate',
    },
    {
      name: 'Bronze',
      value: l.bronze_deliveries,
      unit: 'data deliveries',
      icon: Database,
      tone: 'blue',
    },
    {
      name: 'Gold',
      value: run.source_records,
      unit: 'exact source records',
      icon: Layers,
      tone: 'teal',
    },
    {
      name: 'Reconciliation',
      value: run.source_comparison.hadoop_record_count,
      unit: 'source records agree',
      icon: ShieldCheck,
      tone: 'teal',
    },
  ];
  return (
    <div className="pipeline-board">
      <div className="pipeline-main">
        {nodes.map((n, i) => (
          <div className={`pipeline-step ${n.tone}`} key={n.name}>
            <div className="pipeline-label">
              <n.icon size={17} />
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
          <ArrowDownRight size={18} />
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
          <span>
            <TriangleAlert size={14} />
            {number(l.late_valid_deliveries)} late
          </span>
        </div>
      </div>
      <div className="pipeline-foot">
        Gold rebuilds from Bronze. Hadoop independently reads the shared canonical input.
      </div>
    </div>
  );
}
