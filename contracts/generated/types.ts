/**
 * THE THIRD EYE — Auto-Generated TypeScript Contract Interfaces
 * NASA Space Apps Challenge 2026
 * DO NOT EDIT DIRECTLY. Generated from contracts/schemas/*.py
 */

export type SensorType = 'MODIS_Aqua' | 'VIIRS_SNPP' | 'VIIRS_NOAA20';

export interface MonthRecord {
  year: number;
  month: number;
  detected_fire_cell_days: number;
  usable_land_cell_days: number;
  fire_activity_index: number | null;
  baseline_median: number | null;
  baseline_p90: number | null;
  is_unusual_month: boolean;
  is_partial_month: boolean;
  is_unavailable: boolean;
  sensor: SensorType;
}

export interface WeekRecord {
  year: number;
  week_number: number;
  start_date: string;
  end_date: string;
  detected_fire_cell_days: number;
  usable_land_cell_days: number;
  fire_activity_index: number | null;
  is_critical_week: boolean;
  is_unusual_week: boolean;
  sensor: SensorType;
}

export interface SeasonalBaselineInfo {
  reference_start_year: number;
  reference_end_year: number;
  eligible_prior_years_count: number;
  normal_season_start_month: number;
  normal_season_end_month: number;
  peak_median_month: number;
}

export interface CalendarArtifact {
  artifact_version: string;
  geometry_id: string;
  region_name: string;
  start_year: number;
  end_year: number;
  snpp_cessation_date: string;
  seasonal_baseline: SeasonalBaselineInfo;
  monthly_records: MonthRecord[];
  weekly_records?: WeekRecord[];
}

export interface CalibrationFactorVariant {
  variant_id: string;
  factor_value: number;
  factor_type: 'own_support_a_H' | 'common_support_a_C';
  training_years: number[];
  delta_relative_to_reference: number;
}

export interface ComparisonResult {
  artifact_version: string;
  geometry_id: string;
  target_period: string;
  baseline_period: string;
  method_id: 'stage_a_finite_factors' | 'stage_b_joint_constraints';
  policy_id: 'own_support_eligible' | 'common_support_paired';
  sensitivity_status: 'stable_across_displayed_settings' | 'sensitive' | 'unresolved';
  applicability_status: 'evaluated_for_conditions' | 'outside_evaluated_conditions' | 'insufficient_evidence';
  inference_status: 'not_established' | 'statistically_supported';
  practical_change: 'meaningful_increase' | 'meaningful_decrease' | 'within_practical_margin' | 'unspecified';
  practical_margin_tau?: number;
  headline_direction: 'increase' | 'decrease' | 'no_change' | 'ambiguous' | 'unresolved';
  registered_variants: CalibrationFactorVariant[];
  reasons_and_limits: string[];
  plain_language_summary: string;
}

export interface ClaimAuditRecord {
  record_id: string;
  statement: string;
  analyst_entity?: string;
  target_region: string;
  geometry_id: string;
  date_range_tested: string;
  dataset_versions: string[];
  snpp_cessation_verified: boolean;
  formulas_applied: string[];
  sensitivity_status: string;
  applicability_status: string;
  inference_status: string;
  practical_margin_applied?: number;
  counterexample_interpretations?: Array<Record<string, unknown>>;
  reproducibility_hash: string;
  verification_steps: string[];
}
