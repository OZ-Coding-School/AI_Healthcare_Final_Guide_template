import { request } from "./client";

const BASE = "/api/v1/health-profiles";

export type Gender = "M" | "F";

export interface HealthProfile {
  id: string;
  gender: Gender;
  birth_date: string; // YYYY-MM-DD
  height: number; // 소수점 1자리
  weight: number;
  has_diabetes: boolean;
  has_hypertension: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateHealthProfileBody {
  gender: Gender;
  birth_date: string;
  height: number;
  weight: number;
  has_diabetes: boolean;
  has_hypertension: boolean;
}

export interface UpdateHealthProfileBody {
  height?: number;
  weight?: number;
  has_diabetes?: boolean;
  has_hypertension?: boolean;
}

/** GET /api/v1/health-profiles — null if not yet created */
export function getHealthProfile(): Promise<HealthProfile | null> {
  return request<HealthProfile | null>(BASE);
}

/** POST /api/v1/health-profiles */
export function createHealthProfile(body: CreateHealthProfileBody): Promise<void> {
  return request<void>(BASE, { method: "POST", body: JSON.stringify(body) });
}

/** PATCH /api/v1/health-profiles */
export function updateHealthProfile(body: UpdateHealthProfileBody): Promise<HealthProfile> {
  return request<HealthProfile>(BASE, { method: "PATCH", body: JSON.stringify(body) });
}
