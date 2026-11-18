import { request } from "./client";
import { delay, type PredictionModelType } from "./diseasePredictionApi";

export type ChallengeType = "DAILY" | "WEEKLY" | "MONTHLY" | "COUNT_BASED";
export type ChallengeStatus = "PENDING" | "IN_PROGRESS" | "COMPLETED" | "FAILED" | "ABANDONED";
export type ChallengeRecommendationStatus = "PROCESSING" | "COMPLETED" | "FAILED";

export interface PersonalChallenge {
  id: number;
  prediction_id: string | null;
  title: string;
  description: string;
  challenge_type: ChallengeType;
  challenge_type_label: string;
  total_rounds: number | null;
  expected_effect: string;
  target_diseases: { model_type: PredictionModelType; disease_name: string }[];
  /** 추천 근거가 된 위험 요인. 화면에는 display_name을 표시 */
  basis: { model_type: PredictionModelType; feature: string; display_name: string }[];
  status: ChallengeStatus;
  status_label: string;
  expired_at: string;
  joined_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ChallengeRecommendation {
  prediction_id: string;
  /** 예측 완료 직후 아주 짧은 순간에는 null (조회하면 바로 시작) */
  status: ChallengeRecommendationStatus | null;
  status_label: string | null;
  error_code: string | null;
  model_name: string | null;
  started_at: string | null;
  completed_at: string | null;
  challenges: PersonalChallenge[];
}

/** GET /api/v1/disease-predictions/{prediction_id}/challenges */
export function getChallengeRecommendation(predictionId: string): Promise<ChallengeRecommendation> {
  return request<ChallengeRecommendation>(`/api/v1/disease-predictions/${predictionId}/challenges`);
}

/** POST /api/v1/disease-predictions/{prediction_id}/challenges/retry — FAILED일 때만 */
export function retryChallengeRecommendation(
  predictionId: string
): Promise<ChallengeRecommendation> {
  return request<ChallengeRecommendation>(
    `/api/v1/disease-predictions/${predictionId}/challenges/retry`,
    { method: "POST" }
  );
}

/** GET /api/v1/challenges — 최근 추천 순 */
export function getChallenges(status?: ChallengeStatus): Promise<PersonalChallenge[]> {
  const query = status ? `?${new URLSearchParams({ status })}` : "";
  return request<PersonalChallenge[]>(`/api/v1/challenges${query}`);
}

export function isRecommendationSettled(recommendation: ChallengeRecommendation): boolean {
  return recommendation.status === "COMPLETED" || recommendation.status === "FAILED";
}

/** 명세: PROCESSING이면 2~3초 간격으로 다시 조회 */
const POLL_INTERVAL_MS = 2500;
/** LLM 시간 제한 30초 × 최대 2회 호출을 넘기는 약 100초 동안 기다립니다. */
const MAX_POLLS = 40;

/**
 * 추천이 COMPLETED·FAILED가 될 때까지 조회합니다.
 * 시간 안에 끝나지 않으면 마지막 응답(PROCESSING)을 그대로 반환합니다.
 */
export async function waitForChallengeRecommendation(
  predictionId: string,
  options: {
    onUpdate?: (recommendation: ChallengeRecommendation) => void;
    signal?: AbortSignal;
  } = {}
): Promise<ChallengeRecommendation> {
  const { onUpdate, signal } = options;
  let recommendation = await getChallengeRecommendation(predictionId);

  for (let poll = 0; poll < MAX_POLLS && !isRecommendationSettled(recommendation); poll++) {
    onUpdate?.(recommendation);
    await delay(POLL_INTERVAL_MS, signal);
    recommendation = await getChallengeRecommendation(predictionId);
  }
  return recommendation;
}

/** retry API로 다시 생성할 수 있는 실패인지 (명세의 재시도 열) */
const RETRYABLE_ERRORS = new Set([
  "LLM_UNAVAILABLE",
  "LLM_INVALID_RESPONSE",
  "INTERNAL_ERROR",
  "LLM_REQUEST_FAILED",
]);

export function canRetryRecommendation(errorCode: string | null): boolean {
  return errorCode !== null && RETRYABLE_ERRORS.has(errorCode);
}

const RECOMMENDATION_ERROR_MESSAGES: Record<string, string> = {
  LLM_NOT_CONFIGURED:
    "챌린지 추천 기능이 아직 설정되지 않았습니다. 설정이 완료되면 다시 조회할 때 자동으로 추천됩니다.",
  LLM_UNAVAILABLE: "추천 서비스가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해주세요.",
  LLM_REQUEST_FAILED:
    "추천 서비스 설정에 문제가 있습니다. 문제가 계속되면 관리자에게 문의해주세요.",
  LLM_INVALID_RESPONSE: "추천 결과를 만들지 못했습니다. 다시 시도해주세요.",
  NO_PREDICTION_RESULT: "추천에 사용할 위험도 분석 결과가 없습니다.",
  INTERNAL_ERROR: "추천 중 서버 오류가 발생했습니다. 다시 시도해주세요.",
};

export function recommendationErrorMessage(errorCode: string | null): string {
  return (errorCode && RECOMMENDATION_ERROR_MESSAGES[errorCode]) || "챌린지 추천에 실패했습니다.";
}

/** 목표 회차 단위. 일일=일, 주간=주, 월간=개월, 횟수형=회 */
const ROUND_UNITS: Record<ChallengeType, string> = {
  DAILY: "일",
  WEEKLY: "주",
  MONTHLY: "개월",
  COUNT_BASED: "회",
};

export function formatRounds(
  challenge: Pick<PersonalChallenge, "challenge_type" | "total_rounds">
) {
  if (!challenge.total_rounds) return null;
  return `${challenge.total_rounds}${ROUND_UNITS[challenge.challenge_type] ?? "회"}`;
}

export function isExpired(challenge: Pick<PersonalChallenge, "expired_at">, now = Date.now()) {
  const expiredAt = new Date(challenge.expired_at).getTime();
  return !Number.isNaN(expiredAt) && expiredAt <= now;
}
