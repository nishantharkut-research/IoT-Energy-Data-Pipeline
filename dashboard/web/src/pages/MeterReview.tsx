import { useState } from 'react';
import { Badge, Button, Group, Select, Textarea } from '@mantine/core';
import { ClipboardCheck, Download, RotateCcw } from 'lucide-react';
import { DataTable, Note, Panel, Stat } from '../components/Workspace';
import { download } from '../evidence';

export const reviewCases = [
  {
    id: 'DEMO-1042',
    issue: 'Late reading',
    location: 'Residential feeder A',
    detail: 'A received reading missed the operational cutoff.',
    action: 'Use reconstructed records for interval review.',
    candidate: 3,
    verified: 4,
    missing: false,
  },
  {
    id: 'DEMO-2087',
    issue: 'Duplicate delivery',
    location: 'Residential feeder B',
    detail: 'The same source event was delivered twice.',
    action: 'Retain the receipt and exclude the repeated source event.',
    candidate: 5,
    verified: 4,
    missing: false,
  },
  {
    id: 'DEMO-3016',
    issue: 'Source gap',
    location: 'Commercial feeder C',
    detail: 'The intermediate reading was never supplied.',
    action: 'Request the missing source reading; keep interval exposure unresolved.',
    candidate: 3,
    verified: 3,
    missing: true,
  },
];

export function MeterReview() {
  const [selected, setSelected] = useState(reviewCases[0].id);
  const [filter, setFilter] = useState('All exceptions');
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [reviewed, setReviewed] = useState<Record<string, boolean>>({});
  const item = reviewCases.find((c) => c.id === selected)!;
  const readings = [1000, 1001, 1003, 1004];
  const times = ['09:00', '09:30', '10:00', '10:30'];
  const visible = reviewCases.filter((c) => filter === 'All exceptions' || c.issue === filter);
  const rows = readings.map((value, i) => {
    const affected = i === 1;
    const operational =
      affected && item.issue !== 'Duplicate delivery'
        ? 'Absent'
        : `${value.toFixed(1)} kWh${affected && item.issue === 'Duplicate delivery' ? ' × 2 receipts' : ''}`;
    const exact = affected && item.missing ? 'Unavailable' : `${value.toFixed(1)} kWh`;
    return [
      times[i],
      operational,
      exact,
      affected
        ? item.missing
          ? 'Not received · request source'
          : item.issue === 'Late reading'
            ? 'Received late · recovered'
            : 'Two receipts · one source event'
        : 'Unchanged',
    ];
  });
  function exportReview() {
    download(`${item.id}-illustrative-review.json`, {
      basis: 'Synthetic demonstration; not measured experiment or utility data',
      scenario: item,
      readings: rows,
      note: notes[item.id] ?? '',
      reviewed: reviewed[item.id] ?? false,
      persistence: 'Browser-session state only',
    });
  }
  return (
    <>
      <div className="review-demo-banner">
        <Badge variant="light" color="blue">
          Illustrative scenario
        </Badge>
        <span>
          Fixed sample readings · fictional meter IDs · separate from the 15 measured runs
        </span>
      </div>
      <div className="review-summary">
        <Stat title="Review queue" value="3" note="One case per exception type" />
        <Stat
          title="Reviewed this session"
          value={String(Object.values(reviewed).filter(Boolean).length)}
          note="Decisions stay in this browser session"
        />
        <Stat title="Current exception" value={item.issue} note={item.id} />
      </div>
      <div className="review-layout">
        <Panel title="Meter exception queue" className="review-queue">
          <Select
            aria-label="Filter meter exceptions"
            value={filter}
            onChange={(v) => setFilter(v ?? 'All exceptions')}
            data={['All exceptions', 'Late reading', 'Duplicate delivery', 'Source gap']}
          />
          <div className="review-case-list">
            {visible.map((c) => (
              <button
                key={c.id}
                className={`review-case ${selected === c.id ? 'selected' : ''}`}
                onClick={() => setSelected(c.id)}
                aria-pressed={selected === c.id}
              >
                <span className="review-case-top">
                  <strong>{c.id}</strong>
                  <Badge size="sm" color={reviewed[c.id] ? 'teal' : 'gray'} variant="light">
                    {reviewed[c.id] ? 'Reviewed' : 'Open'}
                  </Badge>
                </span>
                <span>{c.issue}</span>
                <small>{c.location}</small>
              </button>
            ))}
          </div>
        </Panel>
        <Panel
          title={`${item.id} · Reading review`}
          action={
            <Badge color="orange" variant="light">
              {item.issue}
            </Badge>
          }
        >
          <p className="review-lead">{item.detail}</p>
          <div className="review-comparison">
            <div>
              <small>Operational records</small>
              <strong>{item.candidate}</strong>
            </div>
            <div>
              <small>Reconstructed records</small>
              <strong>{item.verified}</strong>
            </div>
            <div>
              <small>Review window</small>
              <strong>90 min</strong>
            </div>
          </div>
          <DataTable
            columns={['Sample time', 'Operational view', 'Reconstructed view', 'Disposition']}
            rows={rows}
          />
          <Note tone={item.missing ? 'amber' : 'teal'}>
            {item.missing
              ? 'An absent source reading remains absent. The 4.0 kWh endpoint difference is known, but the two half-hour allocations around the gap are unresolved.'
              : item.issue === 'Late reading'
                ? 'The late reading restores the 09:00–09:30 and 09:30–10:00 interval boundaries. The whole-window endpoint difference remains 4.0 kWh.'
                : 'Five operational records reduce to four unique source events. The repeated receipt does not represent additional consumption; the endpoint difference remains 4.0 kWh.'}
          </Note>
        </Panel>
      </div>
      <Panel
        title="Review outcome"
        action={
          <Badge color={item.missing ? 'orange' : 'teal'} variant="light">
            {item.missing ? 'Source follow-up required' : 'Ready for analyst review'}
          </Badge>
        }
      >
        <p>{item.action}</p>
        <Textarea
          label="Analyst note"
          description="Optional note for this fictional case. Export to keep a copy; refreshing clears session decisions."
          placeholder="Record the reason for your decision…"
          value={notes[item.id] ?? ''}
          onChange={(e) => setNotes({ ...notes, [item.id]: e.currentTarget.value })}
          minRows={2}
        />
        <Group mt="md" justify="space-between">
          <Group>
            <Button
              leftSection={<ClipboardCheck size={16} />}
              onClick={() => setReviewed({ ...reviewed, [item.id]: true })}
              disabled={reviewed[item.id]}
            >
              Mark reviewed
            </Button>
            <Button variant="default" leftSection={<Download size={16} />} onClick={exportReview}>
              Export review
            </Button>
          </Group>
          <Button
            variant="subtle"
            color="gray"
            leftSection={<RotateCcw size={16} />}
            onClick={() => {
              setReviewed({});
              setNotes({});
            }}
          >
            Reset session
          </Button>
        </Group>
      </Panel>
    </>
  );
}
