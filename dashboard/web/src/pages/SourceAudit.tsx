import { useState } from 'react';
import { Badge, Button, RingProgress, SegmentedControl } from '@mantine/core';
import { Database, Layers, TriangleAlert } from 'lucide-react';
import { DataTable, Note, Panel, Stat, palette } from '../components/Workspace';

import { compact, download, number } from '../evidence';
import type { Evidence } from '../types';
export function SourceAudit({ evidence }: { evidence: Evidence }) {
  const [variant, setVariant] = useState<'raw' | 'clean'>('clean');
  const c = evidence.counts,
    total = c['Physical data rows'][variant],
    finite = c['Finite numeric readings'][variant],
    missing = c['Missing numeric cells'][variant],
    availability = (finite / total) * 100;
  const observations = [
    'Negative readings',
    'Ordered numeric decreases',
    'Duplicate decoded timestamps',
    'Out-of-order timestamps',
    'Invalid decoded timestamps',
    'Zero readings',
  ];
  return (
    <>
      <div className="context-toolbar">
        <SegmentedControl
          value={variant}
          onChange={(v) => setVariant(v as 'raw' | 'clean')}
          data={[
            { label: 'Publisher-resampled source', value: 'clean' },
            { label: 'Raw source', value: 'raw' },
          ]}
        />
        <Badge color="gray" variant="light">
          HKUST · published audit, 27 Oct 2026
        </Badge>
      </div>
      <div className="stats-grid three">
        <Stat
          title="Published rows"
          value={compact(total)}
          note={`${number(total)} physical data rows`}
          icon={<Database size={20} />}
          accent="blue"
        />
        <Stat
          title="Finite numeric readings"
          value={compact(finite)}
          note="Numeric representation, not physical validity"
          icon={<Layers size={20} />}
        />
        <Stat
          title="Missing numeric values"
          value={compact(missing)}
          note="Retained as source-quality exclusions"
          icon={<TriangleAlert size={20} />}
          accent="amber"
        />
      </div>
      <div className="two-columns wide-left">
        <Panel title="What is available to processing?" eyebrow="SOURCE ROW ACCOUNTING">
          <div className="availability-panel">
            <RingProgress
              size={190}
              thickness={17}
              roundCaps
              sections={[
                { value: availability, color: palette.teal },
                { value: 100 - availability, color: '#edc98c' },
              ]}
              label={
                <div className="ring-label">
                  <strong>{availability.toFixed(3)}%</strong>
                  <span>numeric cells</span>
                </div>
              }
            />
            <div className="availability-details">
              <div>
                <i className="dot teal" />
                <span>Finite numeric rows</span>
                <strong>{number(finite)}</strong>
              </div>
              <div>
                <i className="dot amber" />
                <span>Missing numeric rows</span>
                <strong>{number(missing)}</strong>
              </div>
              <div className="total-row">
                <span>Published rows</span>
                <strong>{number(total)}</strong>
              </div>
            </div>
          </div>
          <Note>
            The denominator is the published row grid. This percentage does not measure temporal
            coverage, physical accuracy or a utility SLA.
          </Note>
        </Panel>
        <Panel title="Preparation preserves context" eyebrow="SOURCE CONTRACT">
          <div className="compact-fact">
            <span>Registered workbooks</span>
            <strong>{number(c.Workbooks[variant])}</strong>
          </div>
          <div className="compact-fact">
            <span>Workbook meters joined to Brick</span>
            <strong>{number(c['Workbook meters joined to Brick'][variant])}</strong>
          </div>
          <div className="compact-fact">
            <span>Unmatched workbook meters</span>
            <strong>{c['Workbook meters without a Brick match'][variant]}</strong>
          </div>
          <p className="muted-text">
            Raw and resampled variants stay separate. Original numeric and timestamp text
            accompanies structural source identity.
          </p>
        </Panel>
      </div>
      <Panel
        title="Observed quality conditions"
        eyebrow="REVIEW CATEGORIES"
        action={
          <Button
            size="xs"
            variant="default"
            onClick={() =>
              download(
                `source-audit-${variant}.json`,
                Object.fromEntries(Object.entries(c).map(([key, value]) => [key, value[variant]])),
              )
            }
          >
            Export counters
          </Button>
        }
      >
        <DataTable
          columns={['Observation', 'Raw source', 'Resampled source', 'Interpretation']}
          rows={observations
            .filter((k) => c[k])
            .map((k) => [
              k,
              number(c[k].raw),
              number(c[k].clean),
              k === 'Ordered numeric decreases'
                ? 'Not a confirmed reset'
                : k === 'Duplicate decoded timestamps'
                  ? 'Physical rows remain distinct source events'
                  : k === 'Negative readings'
                    ? 'Review condition; cause not assigned'
                    : k === 'Invalid decoded timestamps'
                      ? 'Decoded timestamp contract'
                      : 'Descriptive observation',
            ])}
        />
        <span className="muted-small">
          Categories overlap. Do not add them to estimate a unique faulty-meter population.
        </span>
      </Panel>
      <Note>
        These counters come from the committed audit summary. Original full audit JSON and row-level
        telemetry are not included in this portable bundle.
      </Note>
    </>
  );
}
