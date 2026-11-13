import type { ReactNode } from 'react';
import {
  Button,
  Group,
  Modal,
  Paper,
  ScrollArea,
  Table,
  Text,
  Title,
  Tooltip,
  CopyButton,
  ActionIcon,
} from '@mantine/core';
import { ArrowUpRight, Check, Copy, Download, FileJson } from 'lucide-react';
import {
  BarChart,
  Bar,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as ChartTip,
  XAxis,
  YAxis,
  LabelList,
} from 'recharts';
import { compact, download, label, number, runName } from '../evidence';
import type { Run } from '../types';
export function Panel({
  title,
  action,
  children,
  className = '',
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Paper className={`panel ${className}`} radius={0} withBorder>
      <div className="panel-heading">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </Paper>
  );
}
export function Stat({ title, value, note }: { title: string; value: string; note: string }) {
  return (
    <div className="stat-card">
      <span className="stat-title">{title}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
export function Note({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'amber' | 'teal';
}) {
  return <div className={`context-note ${tone}`}>{children}</div>;
}
export function Status({
  children = 'Agreed',
  tone = 'teal',
}: {
  children?: ReactNode;
  tone?: 'teal' | 'amber' | 'gray';
}) {
  return <span className={`result-status ${tone}`}>{children}</span>;
}
export function DataTable({ columns, rows }: { columns: string[]; rows: ReactNode[][] }) {
  return (
    <ScrollArea type="auto">
      <Table className="data-table" verticalSpacing="sm" horizontalSpacing="md">
        <Table.Thead>
          <Table.Tr>
            {columns.map((c) => (
              <Table.Th key={c}>{c}</Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((cells, i) => (
            <Table.Tr key={i}>
              {cells.map((c, j) => (
                <Table.Td key={j}>{c}</Table.Td>
              ))}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  );
}
export function Hash({ value }: { value: string }) {
  return (
    <Group gap={6} wrap="nowrap">
      <code className="hash">{value.slice(0, 16)}…</code>
      <CopyButton value={value}>
        {({ copied, copy }) => (
          <Tooltip label={copied ? 'Copied' : 'Copy full SHA-256'}>
            <ActionIcon
              variant="subtle"
              size="sm"
              color="gray"
              onClick={copy}
              aria-label="Copy full SHA-256"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </ActionIcon>
          </Tooltip>
        )}
      </CopyButton>
    </Group>
  );
}
export function Bars({
  data,
  series,
  height = 240,
  stacked = false,
  percent = false,
}: {
  data: Record<string, string | number>[];
  series: { key: string; name: string; color: string }[];
  height?: number;
  stacked?: boolean;
  percent?: boolean;
}) {
  return (
    <div className="chart-wrap" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 24, right: 14, left: 0, bottom: 0 }}
          barCategoryGap="28%"
        >
          <CartesianGrid vertical={false} stroke="#e9edf1" />
          <XAxis
            dataKey="name"
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#6c7a89', fontSize: 14 }}
            height={42}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#6c7a89', fontSize: 14 }}
            width={58}
            tickFormatter={(v) => (percent ? `${v}%` : compact(v))}
          />
          <ChartTip
            cursor={{ fill: '#f3f6f8' }}
            contentStyle={{ border: '1px solid #e1e7ed', borderRadius: 10, fontSize: 14 }}
            formatter={(v) =>
              typeof v === 'number' ? (percent ? `${v.toFixed(2)}%` : number(v)) : String(v)
            }
          />
          {series.map((s) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.name}
              fill={s.color}
              stackId={stacked ? 'total' : undefined}
              radius={stacked ? 0 : [4, 4, 0, 0]}
              isAnimationActive={false}
            >
              <LabelList
                dataKey={s.key}
                position={stacked ? 'center' : 'top'}
                fill={stacked ? 'white' : '#24384a'}
                fontSize={14}
                formatter={(v: unknown) =>
                  typeof v === 'number' && v > 0 ? (percent ? `${v.toFixed(1)}%` : compact(v)) : ''
                }
              />
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="chart-legend">
      {items.map((i) => (
        <span key={i.label}>
          <i style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}
export function RunTag({ run }: { run: Run }) {
  return (
    <div className="run-name">
      <span>{runName(run)}</span>
      <code>{run.run_id}</code>
    </div>
  );
}
export function RunDetails({ run, onClose }: { run: Run | null; onClose: () => void }) {
  return (
    <Modal
      opened={!!run}
      onClose={onClose}
      title="Recorded run · evidence details"
      size="xl"
      radius="sm"
    >
      {run && (
        <>
          <Group justify="space-between" mb="lg">
            <div>
              <Title order={3}>{runName(run)}</Title>
              <Text c="dimmed" size="sm">
                {run.run_id}
              </Text>
            </div>
            <Status>Finalized</Status>
          </Group>
          <DataTable
            columns={['Recorded property', 'Value']}
            rows={[
              ['Source records', number(run.source_records)],
              ['Bronze deliveries', number(run.layer_counts.bronze_deliveries)],
              ['Watermark', run.watermark],
              ['Kafka partitions', run.partition_count],
              ['Maximum offsets / trigger', number(run.max_offsets_per_trigger)],
              ['Source fields compared', run.source_comparison.exact_fields.length],
              ['Aggregate fields compared', run.aggregate_comparison.exact_fields.length],
              ['Original manifest SHA-256', <Hash value={run.manifest_sha256} />],
            ]}
          />
          <Note>
            These are saved experiment results. Opening this dialog checks no original runtime
            files.
          </Note>
          <Group justify="flex-end" mt="md">
            <Button
              variant="default"
              leftSection={<FileJson size={16} />}
              onClick={() =>
                download(`${run.run_id}-summary.json`, {
                  export_kind: 'saved_run_summary',
                  runtime_reverified: false,
                  run,
                })
              }
            >
              Export run JSON
            </Button>
            <Button onClick={onClose}>Done</Button>
          </Group>
        </>
      )}
    </Modal>
  );
}
export function Inspect({ run, onInspect }: { run: Run; onInspect: (r: Run) => void }) {
  return (
    <Button
      variant="subtle"
      size="xs"
      rightSection={<ArrowUpRight size={14} />}
      onClick={() => onInspect(run)}
      aria-label={`Inspect ${run.run_id}`}
    >
      Inspect
    </Button>
  );
}
export function DownloadButton({
  onClick,
  children,
}: {
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button variant="default" leftSection={<Download size={16} />} onClick={onClick}>
      {children}
    </Button>
  );
}
export const palette = {
  teal: '#278476',
  blue: '#547a9e',
  amber: '#a86d26',
  slate: '#637b8c',
  navy: '#21384b',
};
export function ExactFields({ run }: { run: Run }) {
  return (
    <div className="field-list">
      {run.source_comparison.exact_fields.map((f) => (
        <span key={f}>{label(f)}</span>
      ))}
    </div>
  );
}
