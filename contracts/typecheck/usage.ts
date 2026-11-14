import type {
  ComparisonResult,
  FirmsHotspotArtifact,
  MonthRecord,
} from "../generated/types";

// Status dimensions are separate unions; no combined UNRESOLVED value exists.
type Sensitivity = ComparisonResult["sensitivity_status"];
type Applicability = ComparisonResult["applicability_status"];
type Inference = ComparisonResult["inference_status"];

export const sensitivity: Sensitivity = "sensitive_to_assumptions";
export const applicability: Applicability = "failed_applicability";
export const inference: Inference = "not_established";

// @ts-expect-error legacy combined enum must not type-check
export const legacy: Sensitivity = "UNRESOLVED";

// @ts-expect-error inference cannot be upgraded by a consumer
export const supported: Inference = "statistically_supported";

// Missing support is null, never a fabricated zero-rate type.
export const rate: MonthRecord["fire_activity_index"] = null;

// FIRMS isolation flags are literal false.
export const isolated: FirmsHotspotArtifact["feeds_grid_math"] = false;
// @ts-expect-error FIRMS points can never feed grid math
export const leaking: FirmsHotspotArtifact["feeds_grid_math"] = true;
