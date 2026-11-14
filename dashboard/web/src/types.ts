export type Stats = { n: number; minimum: number; median: number; maximum: number };
export type Comparison = {
  errors: string[];
  exact_fields: string[];
  spark_record_count: number;
  hadoop_record_count: number;
};
export type Layers = {
  bronze_deliveries: number;
  parsed_valid_deliveries: number;
  silver_deliveries: number;
  duplicate_valid_deliveries: number;
  late_valid_deliveries: number;
  quarantine_deliveries: number;
  terminal_records: number;
};
export type Run = {
  run_id: string;
  experiment: string;
  fault: string;
  event_count: number | 'fixture';
  seed: number;
  watermark: string;
  partition_count: number;
  max_offsets_per_trigger: number;
  status: string;
  source_records: number;
  manifest_sha256: string;
  layer_counts: Layers;
  source_comparison: Comparison;
  aggregate_comparison: Comparison;
  decision: {
    candidate_interval_count: number;
    verified_interval_count: number;
    candidate_flagged_record_count: number;
    verified_flagged_record_count: number;
    comparable_meter_period_count: number;
    incomparable_meter_period_count: number;
    affected_meter_period_count: number;
    absolute_kwh_discrepancy: string;
    verification_seconds: number;
    verification_storage_bytes: number;
    tariff_scenarios: {
      normalized_rate: string;
      gross_exposure: string;
      residual_exposure_after_verification: null | string;
    }[];
    coverage_limits: string[];
  };
  storage: {
    formats: Record<string, { byte_size: number; relative_to_ndjson: number; file_count: number }>;
  };
  queries: {
    execution_policy: string;
    results: {
      query: string;
      row_count: number;
      repetitions: number;
      seconds: Stats;
      result_sha256: string;
      timings_seconds: number[];
    }[];
  };
  recovery: null | {
    full_workflow_seconds: null | number;
    reason: string;
    resumed_stage: string;
    query_configuration: Record<string, string>;
  };
};
export type Results = {
  schema_version: string;
  status: string;
  verified_at_utc: string;
  original_plan_sha256: string;
  final_scope_sha256: string;
  excluded_runs: string[];
  runs: Run[];
  performance_summary: {
    event_count: number;
    verification_seconds: Stats;
    verification_bytes: Stats;
  }[];
  correctness_semantic_equivalence: {
    status: string;
    run_hashes: Record<string, Record<string, string>>;
  };
  recovery_semantic_equivalence: {
    status: string;
    comparisons: Record<string, { uninterrupted_sha256: string; resumed_sha256: string }>;
  };
  watermark_effect: { gold_status: string; candidate_difference_exposed: boolean };
};
export type Scope = {
  original_plan_sha256: string;
  completed_runs: { run_id: string; run_manifest_sha256: string }[];
  excluded_runs: string[];
};
export type Plan = { runs: { run_id: string }[] };
export type Counts = Record<string, { raw: number; clean: number }>;
export type Entry = { path: string; file: string; sha256: string; byte_size: number };
export type Evidence = {
  results: Results;
  counts: Counts;
  manifest: {
    schema_version: string;
    inputs: Record<string, Entry>;
    runtime_reverified: boolean;
    report_available: boolean;
  };
};
export type Page =
  | 'Overview'
  | 'Source audit'
  | 'Delivery inspector'
  | 'Fault comparison'
  | 'Verification'
  | 'Watermark review'
  | 'Recovery'
  | 'Storage & SQL'
  | 'India use case'
  | 'Meter review demo';
