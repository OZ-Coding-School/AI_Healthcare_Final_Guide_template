import { request } from "./client";

const BASE = "/api/v1/blood-sugar-measurements";

export type BloodSugarMeasureType =
  | "FASTING"
  | "BEFORE_BREAKFAST"
  | "AFTER_BREAKFAST"
  | "BEFORE_LUNCH"
  | "AFTER_LUNCH"
  | "BEFORE_DINNER"
  | "AFTER_DINNER"
  | "BEFORE_SLEEP"
  | "RANDOM";

export type ExerciseType = "CARDIO" | "STRENGTH" | "BOTH" | "NOT_APPLICABLE";

export interface BloodSugarMeasurement {
  id: string;
  measure_type: string;
  measured_at: string;
  created_at: string;
}

export interface BloodSugarMeasurementDetail extends BloodSugarMeasurement {
  blood_glucose: number;
  minutes_since_meal?: number;
  has_exercised: boolean;
  exercise_type?: string;
  exercise_minutes?: number;
  minutes_since_exercise?: number;
  has_medicated: boolean;
  medicine_name?: string;
  minutes_since_medication?: number;
  memo?: string;
}

export interface CreateBloodSugarMeasurementBody {
  measure_type: BloodSugarMeasureType;
  blood_glucose: number;
  minutes_since_meal?: number;
  has_exercised: boolean;
  exercise_type?: ExerciseType;
  exercise_minutes?: number;
  minutes_since_exercise?: number;
  has_medicated: boolean;
  medicine_name?: string;
  minutes_since_medication?: number;
  memo?: string;
  measured_at: string;
}

export function measureTypeToKorean(type: BloodSugarMeasureType): string {
  switch (type) {
    case "FASTING":
      return "공복";
    case "BEFORE_BREAKFAST":
      return "아침 식전";
    case "AFTER_BREAKFAST":
      return "아침 식후";
    case "BEFORE_LUNCH":
      return "점심 식전";
    case "AFTER_LUNCH":
      return "점심 식후";
    case "BEFORE_DINNER":
      return "저녁 식전";
    case "AFTER_DINNER":
      return "저녁 식후";
    case "BEFORE_SLEEP":
      return "취침전";
    case "RANDOM":
      return "임의측정";
    default:
      return type;
  }
}

export function exerciseTypeToKorean(type: ExerciseType): string {
  switch (type) {
    case "CARDIO":
      return "유산소";
    case "STRENGTH":
      return "근력";
    case "BOTH":
      return "유산소, 근력";
    case "NOT_APPLICABLE":
      return "해당사항 없음";
    default:
      return type;
  }
}

/** GET /api/v1/blood-sugar-measurements */
export function getBloodSugarMeasurements(params?: {
  start_date?: string;
  end_date?: string;
}): Promise<BloodSugarMeasurement[]> {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  const url = query.toString() ? `${BASE}?${query}` : BASE;
  return request<BloodSugarMeasurement[]>(url);
}

/** GET /api/v1/blood-sugar-measurements/{measurement_id} */
export function getBloodSugarMeasurementDetail(
  measurementId: string
): Promise<BloodSugarMeasurementDetail> {
  return request<BloodSugarMeasurementDetail>(`${BASE}/${measurementId}`);
}

/** POST /api/v1/blood-sugar-measurements */
export function createBloodSugarMeasurement(
  body: CreateBloodSugarMeasurementBody
): Promise<BloodSugarMeasurement> {
  return request<BloodSugarMeasurement>(BASE, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** DELETE /api/v1/blood-sugar-measurements/{measurement_id} */
export function deleteBloodSugarMeasurement(measurementId: string): Promise<void> {
  return request<void>(`${BASE}/${measurementId}`, {
    method: "DELETE",
  });
}
