import { useEffect, useState } from 'react';
import {
  ActionIcon,
  AppShell,
  Burger,
  Button,
  Group,
  Loader,
  Menu,
  Modal,
  NavLink,
  ScrollArea,
  Text,
  Tooltip,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  Building2,
  ClipboardCheck,
  ChartColumn,
  ChevronDown,
  Database,
  Download,
  FileJson,
  FileText,
  GitCompare,
  GitFork,
  Code2,
  LayoutDashboard,
  RotateCcw,
  ShieldCheck,
  TableProperties,
  TriangleAlert,
} from 'lucide-react';
import { loadEvidence, download, exportCSV } from './evidence';
import { DataTable, Hash, Note, RunDetails } from './components/Workspace';
import { Overview } from './pages/Overview';
import { Delivery } from './pages/Delivery';
import { Faults } from './pages/Faults';
import { Verification } from './pages/Verification';
import { Watermark } from './pages/Watermark';
import { SourceAudit } from './pages/SourceAudit';
import { Recovery } from './pages/Recovery';
import { Storage } from './pages/Storage';
import { India } from './pages/India';
import { MeterReview } from './pages/MeterReview';
import type { Evidence, Page, Run } from './types';
const pages: { name: Page; icon: typeof Database; subtitle: string }[] = [
  {
    name: 'Meter review demo',
    icon: ClipboardCheck,
    subtitle: 'Explore a fictional meter case, compare readings and record a review decision.',
  },
  {
    name: 'Overview',
    icon: LayoutDashboard,
    subtitle: 'Completed fixtures and scale experiments, through 1M source records.',
  },
  {
    name: 'Source audit',
    icon: Database,
    subtitle: 'Raw and publisher-resampled HKUST records.',
  },
  {
    name: 'Delivery inspector',
    icon: GitFork,
    subtitle: 'Deliveries, dispositions and finalized source records.',
  },
  {
    name: 'Fault comparison',
    icon: TriangleAlert,
    subtitle: 'Clean, duplicate, delayed, malformed and combined schedules.',
  },
  {
    name: 'Verification',
    icon: ShieldCheck,
    subtitle: 'Exact-field comparisons of Spark Gold and independent Hadoop outputs.',
  },
  {
    name: 'Watermark review',
    icon: GitCompare,
    subtitle: 'Candidate omissions and matching-interval consumption coverage.',
  },
  {
    name: 'Recovery',
    icon: RotateCcw,
    subtitle: 'Interrupted and uninterrupted outputs, compared by semantic digest.',
  },
  {
    name: 'Storage & SQL',
    icon: ChartColumn,
    subtitle: 'Recorded verification costs, file sizes and query timings.',
  },
  {
    name: 'India use case',
    icon: Building2,
    subtitle: 'A proposed DISCOM review of metering-provider data.',
  },
];
export const slug = (p: Page) => p.toLowerCase().replaceAll(' & ', '-').replaceAll(' ', '-');
function initialPage(): Page {
  return pages.find((p) => `#${slug(p.name)}` === location.hash)?.name ?? 'Overview';
}
export default function App() {
  const [evidence, setEvidence] = useState<Evidence | null>(null),
    [error, setError] = useState(''),
    [page, setPage] = useState<Page>(initialPage),
    [selected, setSelected] = useState('correctness-combined-r01'),
    [detail, setDetail] = useState<Run | null>(null);
  const [opened, { toggle, close }] = useDisclosure(false),
    [provenance, { open: openEvidence, close: closeEvidence }] = useDisclosure(false);
  async function load() {
    setEvidence(null);
    setError('');
    try {
      setEvidence(await loadEvidence());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Evidence could not be loaded.');
    }
  }
  useEffect(() => {
    void load();
    const change = () => setPage(initialPage());
    window.addEventListener('hashchange', change);
    return () => window.removeEventListener('hashchange', change);
  }, []);
  function navigate(value: Page) {
    setPage(value);
    location.hash = slug(value);
    close();
    window.scrollTo({ top: 0, behavior: 'instant' });
  }
  const current = pages.find((p) => p.name === page)!;
  const run = evidence?.results.runs.find((r) => r.run_id === selected);
  return (
    <AppShell
      layout="alt"
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: 'md', collapsed: { mobile: !opened } }}
      padding={0}
    >
      <AppShell.Navbar className="sidebar">
        <a className="brand" href="#overview" onClick={() => navigate('Overview')}>
          <span>
            <strong>MeterTrace</strong>
          </span>
        </a>
        <ScrollArea className="nav-scroll" type="auto">
          <nav aria-label="Project navigation">
            {pages
              .filter((p) => p.name !== 'India use case')
              .map((p) => (
                <NavLink
                  key={p.name}
                  label={p.name}
                  leftSection={<p.icon size={19} strokeWidth={1.7} />}
                  active={p.name === page}
                  onClick={() => navigate(p.name)}
                  className="workspace-nav"
                />
              ))}
            <div className="nav-divider" />
            <NavLink
              label="India use case"
              leftSection={<Building2 size={19} strokeWidth={1.7} />}
              active={page === 'India use case'}
              onClick={() => navigate('India use case')}
              className="workspace-nav"
            />
          </nav>
        </ScrollArea>
        <div className="sidebar-foot">
          <div className="evidence-status">
            <strong>
              {error ? 'Evidence unavailable' : evidence ? 'Saved results' : 'Loading data'}
            </strong>
          </div>
          <button onClick={openEvidence} disabled={!evidence}>
            Data provenance
          </button>
        </div>
      </AppShell.Navbar>
      <AppShell.Header className="topbar">
        <Group justify="space-between" h="100%" px="xl" wrap="nowrap">
          <Group gap="sm">
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="md"
              size="sm"
              aria-label="Toggle navigation"
            />
            <span className="breadcrumb">
              {page === 'Meter review demo'
                ? 'Illustrative meter-review workspace'
                : 'HKUST smart-meter telemetry'}
            </span>
          </Group>
          <Group gap="sm" wrap="nowrap">
            {evidence?.manifest.report_available && (
              <Button
                component="a"
                href="/project-report.pdf"
                target="_blank"
                variant="default"
                leftSection={<FileText size={16} />}
                size="sm"
              >
                Project report
              </Button>
            )}
            <Tooltip label="Open project repository">
              <ActionIcon
                component="a"
                href="https://github.com/nishantharkut-research/IoT-Energy-Data-Pipeline"
                target="_blank"
                rel="noreferrer"
                variant="default"
                size="lg"
                aria-label="Open project repository"
              >
                <Code2 size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Main>
        <div className="workspace">
          {!evidence ? (
            <div className="loading-state">
              {error ? (
                <>
                  <TriangleAlert size={36} />
                  <h1>Evidence could not be displayed</h1>
                  <p>{error}</p>
                  <Button onClick={() => void load()}>Try again</Button>
                </>
              ) : (
                <>
                  <Loader color="teal" />
                  <p>Checking saved source and experiment summaries…</p>
                </>
              )}
            </div>
          ) : (
            run && (
              <>
                <div className="page-header">
                  <div>
                    <h1>{page}</h1>
                    <p>{current.subtitle}</p>
                  </div>
                  <Menu shadow="md" width={215} position="bottom-end">
                    <Menu.Target>
                      <Button
                        variant="default"
                        leftSection={<Download size={16} />}
                        rightSection={<ChevronDown size={14} />}
                      >
                        Export evidence
                      </Button>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<TableProperties size={16} />}
                        onClick={() => exportCSV(evidence.results.runs)}
                      >
                        Run register · CSV
                      </Menu.Item>
                      <Menu.Item
                        component="a"
                        href="/evidence/final-results.json"
                        download="final-results.json"
                        leftSection={<FileJson size={16} />}
                      >
                        Full saved results · JSON
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<FileJson size={16} />}
                        onClick={() => download('evidence-bindings.json', evidence.manifest)}
                      >
                        Evidence bindings · JSON
                      </Menu.Item>
                    </Menu.Dropdown>
                  </Menu>
                </div>
                {page === 'Overview' && (
                  <Overview
                    evidence={evidence}
                    selected={run}
                    setSelected={setSelected}
                    navigate={navigate}
                    inspect={setDetail}
                  />
                )}
                {page === 'Source audit' && <SourceAudit evidence={evidence} />}
                {page === 'Delivery inspector' && (
                  <Delivery evidence={evidence} run={run} setSelected={setSelected} />
                )}
                {page === 'Fault comparison' && <Faults evidence={evidence} />}
                {page === 'Verification' && (
                  <Verification evidence={evidence} run={run} setSelected={setSelected} />
                )}
                {page === 'Watermark review' && <Watermark evidence={evidence} />}
                {page === 'Recovery' && <Recovery evidence={evidence} />}
                {page === 'Storage & SQL' && (
                  <Storage evidence={evidence} run={run} setSelected={setSelected} />
                )}
                {page === 'India use case' && <India evidence={evidence} />}
                {page === 'Meter review demo' && <MeterReview />}
                <footer className="workspace-footer">
                  <span>
                    {page === 'Meter review demo'
                      ? 'Synthetic readings · local session only'
                      : 'Original artifact verification: 2 Nov 2026'}
                  </span>
                  <span>
                    {page === 'Meter review demo'
                      ? 'Sample clock times · no utility data or measured savings'
                      : 'HKUST evaluation · assumed Hong Kong timezone · selected workloads through 1M'}
                  </span>
                </footer>
              </>
            )
          )}
        </div>
      </AppShell.Main>
      <RunDetails run={detail} onClose={() => setDetail(null)} />
      <Modal
        opened={provenance}
        onClose={closeEvidence}
        title="Evidence provenance"
        size="xl"
        radius="lg"
      >
        {evidence && (
          <>
            <Group mb="lg">
              <span className="metadata">Summary bytes checked in this browser</span>
            </Group>
            <DataTable
              columns={['Saved input', 'SHA-256 binding', 'Bytes']}
              rows={Object.entries(evidence.manifest.inputs).map(([name, e]) => [
                name.replaceAll('_', ' '),
                <Hash value={e.sha256} />,
                e.byte_size.toLocaleString(),
              ])}
            />
            <Note>
              These files are the original committed summaries and their scope bindings. The
              recorded original runtime verification was completed on{' '}
              {new Date(evidence.results.verified_at_utc).toLocaleDateString('en-GB', {
                dateStyle: 'long',
              })}
              . This browser does not reverify the large source dataset, audit JSON or original run
              artifact directories.
            </Note>
            <Text mt="md" size="sm" c="dimmed">
              The original strict artifact viewer remains available separately through
              dashboard/app.py.
            </Text>
          </>
        )}
      </Modal>
    </AppShell>
  );
}
