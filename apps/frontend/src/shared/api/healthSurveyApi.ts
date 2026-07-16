import { request } from "./client";

const BASE = "/api/v1/health-surveys";

export type HabitStatus = "NEVER" | "FORMER" | "CURRENT";

export interface HealthSurvey {
  id: string;
  title: string;
  created_at: string;
}

export interface HealthSurveyDetail extends HealthSurvey {
  smoking_status: string;
  smoking_fr_per_day?: number;
  drinking_status: string;
  drinking_fr_per_week?: number;
  drinking_amount_per_session?: number;
  systolic_bp: number;
  diastolic_bp: number;
  pulse?: number;
}

export interface CreateHealthSurveyBody {
  smoking_status: HabitStatus;
  smoking_fr_per_day?: number;
  drinking_status: HabitStatus;
  drinking_fr_per_week?: number;
  drinking_amount_per_session?: number;
  systolic_bp: number;
  diastolic_bp: number;
  pulse?: number;
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
