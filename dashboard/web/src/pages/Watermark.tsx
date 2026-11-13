import { useState } from 'react';
import { Accordion, SegmentedControl, Text } from '@mantine/core';
import { DataTable, Note, Panel, Status } from '../components/Workspace';

import { number } from '../evidence';
import type { Evidence } from '../types';

export function Watermark({ evidence }: { evidence: Evidence }) {
  const [mode, setMode] = useState('restrictive');
  const run = evidence.results.runs.find((r) => r.run_id === `watermark-${mode}-r01`)!;
  const d = run.decision,
    l = run.layer_counts;
  return (
    <>
      <div className="context-toolbar">
        <div>
          <SegmentedControl
            mt={8}
            value={mode}
            onChange={setMode}
            data={[
              { label: 'Retaining · 24 hours', value: 'retaining' },
              { label: 'Restrictive · 1 minute', value: 'restrictive' },
            ]}
          />
        </div>
        <span className="metadata">Same finalized Gold / Hadoop output</span>
      </div>
      <div className="watermark-grid">
        <Panel title="Operational candidate">
          <div className="large-count">
            {number(l.silver_deliveries)}
            <span>source records</span>
          </div>
          <p>
            {l.late_valid_deliveries
              ? `${l.late_valid_deliveries} valid delivery fell outside the bounded candidate.`
              : 'All received valid source events remain in the candidate.'}
          </p>
          <Status tone={l.late_valid_deliveries ? 'amber' : 'teal'}>
            {l.late_valid_deliveries
              ? 'Review late-valid disposition'
              : `Candidate retains all ${run.source_records}`}
          </Status>
        </Panel>
        <Panel title="Finalized source result">
          <div className="large-count">
            {number(run.source_records)}
            <span>source records</span>
          </div>
          <p>Exact source identity is rebuilt from received Bronze records after completion.</p>
          <Status>Independent comparison agrees</Status>
        </Panel>
      </div>
      <Panel title="Consumption comparison">
        <div className="coverage-strip">
          <div>
            <strong>{d.comparable_meter_period_count}</strong>
            <span>comparable periods</span>
          </div>
          <div className={d.incomparable_meter_period_count ? 'amber-text' : ''}>
            <strong>{d.incomparable_meter_period_count}</strong>
            <span>incomparable periods</span>
          </div>
          <div>
            <strong>
              {d.absolute_kwh_discrepancy} <small>kWh</small>
            </strong>
            <span>comparable subtotal only</span>
          </div>
          <div>
            <strong className="unknown">Unknown</strong>
            <span>residual financial exposure</span>
          </div>
        </div>
        <DataTable
          columns={['Derivation', 'Silver candidate', 'Verified Gold']}
          rows={[
            ['Derived intervals', d.candidate_interval_count, d.verified_interval_count],
            ['Flagged records', d.candidate_flagged_record_count, d.verified_flagged_record_count],
          ]}
        />
        <Note tone="amber">
          A zero subtotal over matching periods does not establish zero total energy error.
          Unmatched supports are not assigned an invented kWh value or a rupee loss.
        </Note>
      </Panel>
      <Accordion variant="separated" radius="md">
        <Accordion.Item value="policy">
          <Accordion.Control>Exclusion rules</Accordion.Control>
          <Accordion.Panel>
            Only supported cumulative-kWh readings are differenced. Initial baselines, ambiguous
            duplicate timestamps, the first new baseline after ambiguity, negative deltas and
            unresolved resets are flagged. Two physical source rows at one timestamp remain separate
            source events even when their values agree.
          </Accordion.Panel>
        </Accordion.Item>
        <Accordion.Item value="rates">
          <Accordion.Control>Declared hypothetical tariff scenarios</Accordion.Control>
          <Accordion.Panel>
            <DataTable
              columns={[
                'Normalized rate / kWh',
                'Comparable scenario subtotal',
                'Residual exposure',
              ]}
              rows={d.tariff_scenarios.map((r) => [
                r.normalized_rate,
                r.gross_exposure,
                r.residual_exposure_after_verification ?? 'Unknown',
              ])}
            />
            <Text size="sm" c="dimmed">
              Scenario currency units only. Neither HKUST financial results nor Indian tariffs.
            </Text>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </>
  );
}
