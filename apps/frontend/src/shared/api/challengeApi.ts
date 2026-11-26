import { ApiError, request } from "./client";
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
  /** 수락한 챌린지의 진행 상황. 수락 전(PENDING)이거나 예측별 추천 조회에서는 null */
  progress: ChallengeProgress | null;
}

export interface ChallengeProgress {
  total_rounds: number;
  /** 완료에 필요한 성공 회차 (주기형: 목표의 80% 올림, 횟수형: 목표 전부) */
  required_success: number;
  success_count: number;
  recorded_count: number;
  /** 기록할 수 있는 마지막 날짜 (YYYY-MM-DD) */
  ends_on: string;
  /** 지금 기록할 수 있는 회차. 기록할 수 없으면 null */
  current_round: number | null;
  can_record: boolean;
}

export interface ChallengeHistory {
  id: number;
  current_round: number;
  is_success: boolean;
  memo: string | null;
  created_at: string;
}

export interface PersonalChallengeDetail extends PersonalChallenge {
  histories: ChallengeHistory[];
}

/** 회차 기록 메모 최대 길이 (백엔드 검증과 같음) */
export const HISTORY_MEMO_MAX_LENGTH = 300;

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

/** GET /api/v1/challenges/{challenge_id} — 진행 상황·회차 기록 포함 */
export function getChallenge(challengeId: number): Promise<PersonalChallengeDetail> {
  return request<PersonalChallengeDetail>(`/api/v1/challenges/${challengeId}`);
}

/** POST /api/v1/challenges/{challenge_id}/accept — 수락 기한 안의 PENDING만 */
export function acceptChallenge(challengeId: number): Promise<PersonalChallengeDetail> {
  return request<PersonalChallengeDetail>(`/api/v1/challenges/${challengeId}/accept`, {
    method: "POST",
  });
}

/** POST /api/v1/challenges/{challenge_id}/histories — 현재 회차만, 회차당 1건 */
export function recordChallengeHistory(
  challengeId: number,
  body: { is_success: boolean; memo?: string | null }
): Promise<PersonalChallengeDetail> {
  return request<PersonalChallengeDetail>(`/api/v1/challenges/${challengeId}/histories`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** 수락·기록 실패 시 화면에 보여줄 문구 (409는 상태가 바뀐 경우라 목록을 다시 불러옵니다) */
export function challengeActionErrorMessage(action: "accept" | "record", error: unknown): string {
  const status = error instanceof ApiError ? error.status : undefined;
  if (status === 404) return "챌린지를 찾을 수 없습니다. 목록을 새로고침해주세요.";
  if (status === 409) {
    return action === "accept"
      ? "이미 수락했거나 수락 기한이 지난 챌린지입니다."
      : "이번 회차는 이미 기록했거나 종료된 챌린지입니다.";
  }
  if (status === 422 && error instanceof ApiError) return error.message;
  return action === "accept"
    ? "챌린지를 수락하지 못했습니다. 잠시 후 다시 시도해주세요."
    : "기록을 저장하지 못했습니다. 잠시 후 다시 시도해주세요.";
}

/** 현재 회차를 부르는 말. 일간·횟수형은 오늘, 주간은 이번 주, 월간은 이번 달 */
const ROUND_PERIOD_LABELS: Record<ChallengeType, string> = {
  DAILY: "오늘",
  WEEKLY: "이번 주",
  MONTHLY: "이번 달",
  COUNT_BASED: "오늘",
};

export function roundPeriodLabel(challengeType: ChallengeType): string {
  return ROUND_PERIOD_LABELS[challengeType] ?? "이번 회차";
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
