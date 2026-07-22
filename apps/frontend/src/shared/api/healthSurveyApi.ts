import { request } from "./client";

const BASE = "/api/v1/health-surveys";

export type HabitStatus = "NEVER" | "FORMER" | "CURRENT";

export type DrinkingFrequency =
  | "LESS_THAN_MONTHLY"
  | "MONTHLY"
  | "MONTHLY_2_TO_4"
  | "WEEKLY_2_TO_3"
  | "WEEKLY_4_OR_MORE"
  | "NOT_APPLICABLE";

export const DRINKING_FREQUENCY_LABELS: Record<DrinkingFrequency, string> = {
  LESS_THAN_MONTHLY: "월 1회 미만",
  MONTHLY: "월 1회 정도",
  MONTHLY_2_TO_4: "월 2~4회",
  WEEKLY_2_TO_3: "주 2~3회",
  WEEKLY_4_OR_MORE: "주 4회 이상",
  NOT_APPLICABLE: "해당없음",
};

export interface HealthSurvey {
  id: string;
  title: string;
  created_at: string;
}

export interface HealthSurveyDetail extends HealthSurvey {
  smoking_status: string;
  smoking_fr_per_day?: number;
  drinking_status: string;
  drinking_frequency?: DrinkingFrequency;
  drinking_amount_per_session?: number;
  systolic_bp: number;
  diastolic_bp: number;
}

export interface CreateHealthSurveyBody {
  smoking_status: HabitStatus;
  smoking_fr_per_day?: number;
  drinking_status: HabitStatus;
  drinking_frequency?: DrinkingFrequency;
  drinking_amount_per_session?: number;
  systolic_bp: number;
  diastolic_bp: number;
}

/** GET /api/v1/health-surveys */
export function getHealthSurveys(params?: {
  start_year?: number;
  end_year?: number;
}): Promise<HealthSurvey[]> {
  const query = new URLSearchParams();
  if (params?.start_year) query.set("start_year", String(params.start_year));
  if (params?.end_year) query.set("end_year", String(params.end_year));
  const url = query.toString() ? `${BASE}?${query}` : BASE;
  return request<HealthSurvey[]>(url);
}

/** GET /api/v1/health-surveys/{survey_id} */
export function getHealthSurveyDetail(surveyId: string): Promise<HealthSurveyDetail> {
  return request<HealthSurveyDetail>(`${BASE}/${surveyId}`);
}

/** POST /api/v1/health-surveys */
export function createHealthSurvey(body: CreateHealthSurveyBody): Promise<HealthSurvey> {
  return request<HealthSurvey>(BASE, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
