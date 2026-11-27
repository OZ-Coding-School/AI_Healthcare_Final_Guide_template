import { request } from "./client";

const BASE = "/api/v1/annual-health-screenings";

export type UrineProteinStatus = "-" | "±" | "1+" | "2+" | "3+" | "4+";
export type UrineGlucoseStatus = "-" | "±" | "1+" | "2+" | "3+" | "4+";

export type FamilyHistoryAnswer = "YES" | "NO" | "UNKNOWN" | "NO_SIBLINGS";
export type FamilyHistoryRelation = "father" | "mother" | "siblings";
export type FamilyHistoryDisease = "diabetes" | "hypertension";

export const FAMILY_HISTORY_ANSWER_LABELS: Record<FamilyHistoryAnswer, string> = {
  YES: "있음",
  NO: "없음",
  UNKNOWN: "모름",
  NO_SIBLINGS: "형제자매 없음",
};

export const FAMILY_HISTORY_RELATIONS: { key: FamilyHistoryRelation; label: string }[] = [
  { key: "father", label: "아버지" },
  { key: "mother", label: "어머니" },
  { key: "siblings", label: "형제자매" },
];

export interface FamilyHistoryDetail {
  diabetes_family_history_father?: FamilyHistoryAnswer | null;
  diabetes_family_history_mother?: FamilyHistoryAnswer | null;
  diabetes_family_history_siblings?: FamilyHistoryAnswer | null;
  hypertension_family_history_father?: FamilyHistoryAnswer | null;
  hypertension_family_history_mother?: FamilyHistoryAnswer | null;
  hypertension_family_history_siblings?: FamilyHistoryAnswer | null;
}

export function familyHistoryDetailKey(
  disease: FamilyHistoryDisease,
  relation: FamilyHistoryRelation
): keyof FamilyHistoryDetail {
  return `${disease}_family_history_${relation}`;
}

export interface AnnualHealthScreening {
  id: string;
  title: string;
  screening_at: string;
  created_at: string;
}

export interface AnnualHealthScreeningDetail extends AnnualHealthScreening, FamilyHistoryDetail {
  height: number;
  weight: number;
  bmi: number;
  waist_circumference: number;
  sbp: number;
  dbp: number;
  fbs: number;
  hba1c: number;
  triglyceride: number;
  ldl: number;
  hdl: number;
  total_cholesterol: number;
  ast: number;
  alt: number;
  creatinine: number;
  urine_protein: string;
  urine_glucose: string;
  family_history_diabetes: boolean;
  family_history_hypertension: boolean;
  is_fasting: boolean;
}

export interface CreateAnnualHealthScreeningBody extends FamilyHistoryDetail {
  height: number;
  weight: number;
  bmi: number;
  waist_circumference: number;
  sbp: number;
  dbp: number;
  fbs: number;
  hba1c: number;
  triglyceride: number;
  ldl: number;
  hdl: number;
  total_cholesterol: number;
  ast: number;
  alt: number;
  creatinine: number;
  urine_protein: UrineProteinStatus;
  urine_glucose: UrineGlucoseStatus;
  family_history_diabetes: boolean;
  family_history_hypertension: boolean;
  screening_at: string;
  is_fasting: boolean;
}

export function urineStatusToKorean(status: UrineProteinStatus | UrineGlucoseStatus): string {
  switch (status) {
    case "-":
      return "음성 (-)";
    case "±":
      return "미량 (±)";
    case "1+":
      return "양성 1+ (+)";
    case "2+":
      return "양성 2+ (++)";
    case "3+":
      return "양성 3+ (+++)";
    case "4+":
      return "양성 4+ (++++)";
    default:
      return status;
  }
}

/** GET /api/v1/annual-health-screenings */
export function getAnnualHealthScreenings(): Promise<AnnualHealthScreening[]> {
  return request<AnnualHealthScreening[]>(BASE);
}

/** GET /api/v1/annual-health-screenings/{screening_id} */
export function getAnnualHealthScreeningDetail(
  screeningId: string
): Promise<AnnualHealthScreeningDetail> {
  return request<AnnualHealthScreeningDetail>(`${BASE}/${screeningId}`);
}

/** POST /api/v1/annual-health-screenings */
export function createAnnualHealthScreening(
  body: CreateAnnualHealthScreeningBody
): Promise<AnnualHealthScreening> {
  return request<AnnualHealthScreening>(BASE, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
