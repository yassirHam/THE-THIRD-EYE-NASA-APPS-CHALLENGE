/**
 * THE THIRD EYE auto-generated TypeScript contract types.
 * Contract version 1.5.0. DO NOT EDIT.
 * Source: contracts/schemas/*.py via `python -m contracts.generate_ts`.
 */

export interface AnnualCoverage {
  sensor: "MODIS_Aqua" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21";
  year: number;
  days_in_period: number;
  days_with_file: number;
  is_partial_period: boolean;
  partial_period_reason: "outside_sensor_record" | "snpp_record_ended_2026_11_02" | null;
}

export interface ApplicabilityCheck {
  check_id: string;
  status: "passed" | "failed" | "missing" | "out_of_domain";
  detail: string;
  evidence_version?: string | null;
}

export interface BaselineYearExclusion {
  year: number;
  reason: "sealed_evaluation_window" | "partial_record_year" | "required_year_invalid";
  detail?: string | null;
}

export interface BenchmarkBaselineMetrics {
  status: "available" | "unavailable";
  evaluated_case_count: number;
  answered_case_count: number;
  abstention_count: number;
  mean_reference_relative_error?: number | null;
  directional_error_count?: number | null;
  decision_coverage_percent?: number | null;
  unavailable_reason?: string | null;
}

export interface BoundingBox {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface CacheKey {
  artifact_version: string;
  geometry_id: string;
  period_spec: string;
  method_id: string;
  policy_id: string;
}

export interface CalendarArtifact {
  contract_version: "1.5.0";
  artifact_version: string;
  geometry_id: string;
  period_spec: string;
  method_id: string;
  policy_id: string;
  data_classification: "production" | "synthetic_dev_fixture";
  fixture_label?: "[SYNTHETIC DEV FIXTURE]" | null;
  region_name: string;
  measurement_name?: "fire_activity_index";
  measurement_unit: "detected_fire_cell_days_per_1000_usable_land_cell_days";
  snpp_delivery_end_at: string;
  monthly_series: MonthlyCalendarSeries[];
  weekly_series: WeeklyCalendarSeries[];
  seasonal_baselines: SeasonalBaselineInfo[];
  sealed_window: SealedWindow | null;
  week_53_rule: Week53Rule | null;
  footprint_certification: FootprintCertification | null;
  sensor_coverage: SensorCoverage[];
  snpp_cutoff_status: "active" | "reserved_inactive";
  annual_coverage: AnnualCoverage[];
}

export interface CalibrationFactorVariant {
  variant_id: string;
  factor_value: number;
  factor_type: "own_support_a_H" | "common_support_a_C";
  training_years: number[];
  effect_delta: number;
  direction: "increase" | "decrease" | "no_change";
}

export interface ClaimAuditRecord {
  contract_version: "1.5.0";
  artifact_version: string;
  geometry_id: string;
  period_spec: string;
  method_id: string;
  policy_id: string;
  data_classification: "production" | "synthetic_dev_fixture";
  fixture_label?: "[SYNTHETIC DEV FIXTURE]" | null;
  record_id: string;
  statement: string;
  analyst_entity?: string | null;
  target_region: string;
  date_range_tested: string;
  dataset_versions: string[];
  formulas_applied: string[];
  sensitivity_status: "stable_across_displayed_settings" | "sensitive_to_assumptions" | "unavailable";
  applicability_status: "applicable" | "failed_applicability" | "missing_required_support" | "out_of_domain";
  inference_status?: "not_established";
  practical_change: PracticalChange;
  applicability_checks: ApplicabilityCheck[];
  missing_evidence_reasons?: string[];
  conclusion_eligible: boolean;
  reviewed_summary: ReviewedTemplateSummary;
  counterexample_interpretations?: Array<Record<string, unknown>>;
  reproducibility_sha256: string;
  verification_steps: string[];
  evidence_artifact_versions: string[];
}

export interface ComparisonResult {
  contract_version: "1.5.0";
  artifact_version: string;
  geometry_id: string;
  period_spec: string;
  method_id: string;
  policy_id: string;
  data_classification: "production" | "synthetic_dev_fixture";
  fixture_label?: "[SYNTHETIC DEV FIXTURE]" | null;
  sensitivity_status: "stable_across_displayed_settings" | "sensitive_to_assumptions" | "unavailable";
  applicability_status: "applicable" | "failed_applicability" | "missing_required_support" | "out_of_domain";
  inference_status?: "not_established";
  practical_change: PracticalChange;
  headline_direction: "increase" | "decrease" | "within_practical_margin" | "no_change" | "ambiguous" | "unavailable";
  required_variant_ids: string[];
  registered_variants: CalibrationFactorVariant[];
  applicability_checks: ApplicabilityCheck[];
  missing_evidence_reasons?: string[];
  conclusion_eligible: boolean;
  reviewed_summary: ReviewedTemplateSummary;
}

export interface EvaluationSummary {
  contract_version: "1.5.0";
  artifact_version: string;
  geometry_id: string;
  period_spec: string;
  method_id: string;
  policy_id: string;
  data_classification: "production" | "synthetic_dev_fixture";
  fixture_label?: "[SYNTHETIC DEV FIXTURE]" | null;
  eval_protocol_version: "P0-held-out-sensor-switch-v1";
  baseline_a_raw_handover: BenchmarkBaselineMetrics;
  baseline_b_point_a_h: BenchmarkBaselineMetrics;
  baseline_c_uncertainty_aware: BenchmarkBaselineMetrics;
  baseline_d_stage_a_finite_audit: BenchmarkBaselineMetrics;
  landing_headline_metric: LandingHeadlineMetric;
  failures_and_limitations: string[];
}

export interface FirmsHotspotArtifact {
  contract_version: "1.5.0";
  artifact_version: string;
  geometry_id: string;
  period_spec: string;
  method_id: string;
  policy_id: string;
  data_classification: "production" | "synthetic_dev_fixture";
  fixture_label?: "[SYNTHETIC DEV FIXTURE]" | null;
  view_name?: "Reported hotspots";
  measurement_unit?: "reported_detection_points";
  processing_level?: "standard_archive";
  confidence_filter: string;
  firms_link: FirmsHotspotLink;
  points: FirmsHotspotPoint[];
  feeds_grid_math?: false;
  inherits_grid_calibration?: false;
  cross_sensor_trend_allowed?: false;
  isolation_notice?: "FIRMS points are separate from D, O, baselines, factors, and verdicts.";
}

export interface FirmsHotspotLink {
  url: string;
  selected_area: BoundingBox;
  start_date: string;
  end_date: string;
  manual_selection_required: boolean;
  limitation: string;
}

export interface FirmsHotspotPoint {
  point_id: string;
  latitude: number;
  longitude: number;
  acquired_at: string;
  platform: "MODIS" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21";
  confidence_label: string;
  source_product: string;
}

export interface FootprintCertification {
  geometry_id: string;
  status: "complete" | "partial" | "unverified";
  footprint_evidence: "cell_level" | "day_level" | "none";
  certification_ref?: string | null;
  certified_at?: string | null;
  coverage_fraction?: number | null;
}

export interface GeoJsonPolygon {
  type?: "Polygon";
  coordinates: number[][][];
}

export interface IndependentUnits {
  blocks: number;
  regions: number;
  test_years: number;
  dependence_note: string;
}

export interface LandingHeadlineMetric {
  status: "available" | "unavailable";
  description: string;
  registered_case_count?: number | null;
  raw_wrong_way_count?: number | null;
  corrected_wrong_way_count?: number | null;
  flagged_remaining_error_count?: number | null;
  abstained_count?: number | null;
  denominator_statement: string;
  independent_units: IndependentUnits;
  unavailable_reason?: string | null;
}

export interface MonthRecord {
  detected_fire_cell_days?: number | null;
  usable_land_cell_days?: number | null;
  fire_activity_index?: number | null;
  availability: "available" | "unavailable";
  unavailable_reason?: "zero_usable_support" | "source_not_available" | "incomplete_footprint" | "qa_unusable" | "sensor_not_operating" | null;
  sensor: "MODIS_Aqua" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21";
  year: number;
  month: number;
  baseline_median?: number | null;
  baseline_p90?: number | null;
  unusual_status: "unusual" | "not_unusual" | "insufficient_baseline" | "not_applicable" | null;
  is_partial_period?: boolean;
  comparison_eligible: boolean;
  partial_period_reason?: "snpp_record_ended_2026_11_02" | "crosses_sealed_evaluation_boundary" | "outside_sensor_record" | "missing_days_or_tiles" | "low_processed_coverage" | null;
  included_day_count?: number | null;
  days_in_period: number;
  days_with_file: number;
  paired_comparison_eligible: boolean;
  coverage_state: "complete" | "partial" | "unavailable";
  coverage_reasons: Array<"period_clipped" | "sensor_not_operating" | "partition_boundary" | "missing_days_or_tiles" | "low_processed_coverage" | "no_file">;
  processed_coverage?: number | null;
}

export interface MonthlyCalendarSeries {
  sensor: "MODIS_Aqua" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21";
  policy_id: string;
  records: MonthRecord[];
}

export interface PartitionFileRecord {
  file_path: string;
  geometry_id: string;
  period_spec: string;
  method_id: string;
  policy_id: string;
  sensor: "MODIS_Aqua" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21" | null;
  row_count: number;
  file_size_bytes: number;
  cache_key_sha256: string;
  sha256_checksum: string;
  coverage_status: "complete" | "partial" | "unavailable" | "unverified";
}

export interface PracticalChange {
  category: "meaningful_increase" | "meaningful_decrease" | "within_practical_margin" | "inconsistent_across_variants" | "unspecified" | "unavailable";
  magnitude?: number | null;
  effect_units?: string | null;
  practical_margin_tau?: number | null;
  observed_signs?: Array<"increase" | "decrease" | "no_change">;
}

export interface ProvenanceManifest {
  contract_version: "1.5.0";
  artifact_version: string;
  geometry_id: string;
  period_spec: string;
  method_id: string;
  policy_id: string;
  data_classification: "production" | "synthetic_dev_fixture";
  fixture_label?: "[SYNTHETIC DEV FIXTURE]" | null;
  manifest_version: string;
  described_artifact_type: "calendar" | "comparison" | "claim_audit" | "evaluation" | "region_selector" | "firms_hotspots";
  generated_at: string;
  snpp_cessation_date?: "2026-11-02";
  snpp_cutoff_status: "active" | "reserved_inactive";
  canonical_boundary: GeoJsonPolygon;
  boundary_source: string;
  boundary_version: string;
  crs: string;
  grid_inclusion_rule: string;
  source_collections: SourceCollection[];
  total_file_size_bytes: number;
  compressed_bundle_size_bytes: number;
  partitions: PartitionFileRecord[];
}

export interface RegionSelectorArtifact {
  contract_version: "1.5.0";
  artifact_version: string;
  geometry_id: string;
  period_spec: string;
  method_id: string;
  policy_id: string;
  data_classification: "production" | "synthetic_dev_fixture";
  fixture_label?: "[SYNTHETIC DEV FIXTURE]" | null;
  options: RegionSelectorOption[];
}

export interface RegionSelectorOption {
  geometry_id: string;
  display_name: string;
  geometry_role: "primary_region" | "backup_region" | "predeclared_sub_area";
  boundary_source: string;
  boundary_version: string;
  crs: string;
  grid_inclusion_rule: string;
  raw_data_status: "available" | "unavailable";
  comparison_access_status: "raw_only" | "candidate_calibration" | "evaluated_comparison" | "unavailable";
  unavailable_reason?: "no_complete_extract" | "unsupported_geometry" | "incomplete_footprint" | "qa_unusable" | "request_limit" | null;
  evaluated_method_id?: string | null;
  evaluated_policy_id?: string | null;
  evaluated_period_spec?: string | null;
}

export interface ReviewedTemplateSummary {
  template_id: string;
  template_version: string;
  generated_by?: "reviewed_deterministic_template";
  output_category: "consistent_across_tested_corrections" | "depends_on_the_correction" | "not_enough_usable_evidence" | "outside_evaluated_calibration" | "calibration_check_failed" | "calibration_check_failed_and_missing_evidence" | "outside_evaluated_calibration_and_missing_evidence";
  status_label: "Consistent across tested corrections" | "Depends on the correction" | "Not enough usable evidence" | "Outside evaluated calibration" | "Calibration check failed" | "Calibration check failed and required evidence missing" | "Outside evaluated calibration and required evidence missing";
  finding_sentence: string;
  limit_sentence: string;
}

export interface SealedWindow {
  start: string;
  end: string;
  registration_status: "registered" | "proposed_unregistered";
  registration_ref?: string | null;
  decision_date?: string | null;
}

export interface SeasonalBaselineInfo {
  sensor: "MODIS_Aqua" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21";
  policy_id: string;
  status: "available" | "insufficient_baseline" | "unavailable";
  reference_start_year: number;
  reference_end_year: number;
  eligible_prior_years: number[];
  excluded_years: BaselineYearExclusion[];
  unavailable_reason: "required_year_invalid" | null;
  minimum_year_count: number;
  normal_season_start_month?: number | null;
  normal_season_end_month?: number | null;
  peak_median_month?: number | null;
}

export interface SensorCoverage {
  sensor: "MODIS_Aqua" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21";
  status: "active" | "reserved_inactive";
  collection_id?: string | null;
  record_start?: string | null;
  record_end?: string | null;
  scope_ref?: string | null;
}

export interface SourceCollection {
  collection_id: string;
  sensor: "MODIS_Aqua" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21";
  source_version: string;
  record_end_date?: string | null;
}

export interface Week53Baseline {
  target_year: number;
  status: "available" | "insufficient_baseline";
  prior_observations: Week53PriorObservation[];
}

export interface Week53PriorObservation {
  iso_year: number;
  period_complete: boolean;
  support_ok: boolean;
}

export interface Week53Rule {
  registration_status: "registered" | "proposed_unregistered";
  minimum_year_count?: number | null;
  registration_ref?: string | null;
  decision_at?: string | null;
}

export interface WeekRecord {
  detected_fire_cell_days?: number | null;
  usable_land_cell_days?: number | null;
  fire_activity_index?: number | null;
  availability: "available" | "unavailable";
  unavailable_reason?: "zero_usable_support" | "source_not_available" | "incomplete_footprint" | "qa_unusable" | "sensor_not_operating" | null;
  sensor: "MODIS_Aqua" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21";
  year: number;
  week_number: number;
  start_date: string;
  end_date: string;
  critical_status: "critical" | "not_critical" | "insufficient_baseline" | "not_applicable" | null;
  unusual_status: "unusual" | "not_unusual" | "insufficient_baseline" | "not_applicable" | null;
  is_partial_period?: boolean;
  partial_period_reason?: "snpp_record_ended_2026_11_02" | "crosses_sealed_evaluation_boundary" | "outside_sensor_record" | "missing_days_or_tiles" | "low_processed_coverage" | null;
  comparison_eligible: boolean;
  included_day_count?: number | null;
  days_in_period: number;
  days_with_file: number;
  paired_comparison_eligible: boolean;
  coverage_state: "complete" | "partial" | "unavailable";
  coverage_reasons: Array<"period_clipped" | "sensor_not_operating" | "partition_boundary" | "missing_days_or_tiles" | "low_processed_coverage" | "no_file">;
  processed_coverage?: number | null;
}

export interface WeeklyCalendarSeries {
  sensor: "MODIS_Aqua" | "VIIRS_SNPP" | "VIIRS_NOAA20" | "VIIRS_NOAA21";
  policy_id: string;
  week_definition: "utc_iso_week" | "fixed_7_day_bins";
  records: WeekRecord[];
  week_53_baselines: Week53Baseline[];
}
