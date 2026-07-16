import { request } from "./client";

const BASE = "/api/v1/annual-health-screenings";

export type UrineProteinStatus = "NEGATIVE" | "TRACE" | "POSITIVE_1" | "POSITIVE_2" | "POSITIVE_3" | "POSITIVE_4";
export type UrineGlucoseStatus = "NEGATIVE" | "TRACE" | "POSITIVE_1" | "POSITIVE_2" | "POSITIVE_3" | "POSITIVE_4";

export interface AnnualHealthScreening {
  id: string;
  title: string;
  screening_at: string;
  created_at: string;
}

export interface AnnualHealthScreeningDetail extends AnnualHealthScreening {
  height: number;
  weight: number;
  bmi: number;
  waist_circumference: number;
  sbp: number;
  dbp: number;
  pulse: number;
  fbs: number;
  hba1c: number;
  triglyceride: number;
  ldl: number;
  hdl: number;
  total_cholesterol: number;
  ast: number;
  alt: number;
  gamma_gtp: number;
  egfr: number;
  creatinine: number;
  urine_protein: string;
  urine_glucose: string;
  family_history_diabetes: boolean;
  family_history_hypertension: boolean;
  is_fasting: boolean;
}

export interface CreateAnnualHealthScreeningBody {
  height: number;
  weight: number;
  bmi: number;
  waist_circumference: number;
  sbp: number;
  dbp: number;
  pulse: number;
  fbs: number;
  hba1c: number;
  triglyceride: number;
  ldl: number;
  hdl: number;
  total_cholesterol: number;
  ast: number;
  alt: number;
  gamma_gtp: number;
  egfr: number;
  creatinine: number;
  urine_protein: UrineProteinStatus;
  urine_glucose: UrineGlucoseStatus;
  family_history_diabetes: boolean;
  family_history_hypertension: boolean;
  screening_at: string;
  is_fasting: boolean;
}

function urineStatusToKorean(status: UrineProteinStatus | UrineGlucoseStatus): string {
  switch (status) {
    case "NEGATIVE": return "음성 (-)";
    case "TRACE": return "미량 (±)";
    case "POSITIVE_1": return "양성 1+ (+)";
    case "POSITIVE_2": return "양성 2+ (++)";
    case "POSITIVE_3": return "양성 3+ (+++)";
    case "POSITIVE_4": return "양성 4+ (++++)";
    default: return status;
  }
}

/** GET /api/v1/annual-health-screenings */
export function getAnnualHealthScreenings(): Promise<AnnualHealthScreening[]> {
  return request<AnnualHealthScreening[]>(BASE);
}

/** GET /api/v1/annual-health-screenings/{screening_id} */
export function getAnnualHealthScreeningDetail(screeningId: string): Promise<AnnualHealthScreeningDetail> {
  return request<AnnualHealthScreeningDetail>(`${BASE}/${screeningId}`);
}

/** POST /api/v1/annual-health-screenings */
export function createAnnualHealthScreening(body: CreateAnnualHealthScreeningBody): Promise<AnnualHealthScreening> {
  return request<AnnualHealthScreening>(BASE, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
