import { ApiError, request, requestStream, type ValidationErrorItem } from "./client";

const BASE = "/api/v1/disease-predictions";

export type DiseasePredictionStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
export type PredictionModelType = "diabetes_risk" | "hypertension_risk";
export type DiseaseRiskLevel = "LOW" | "MODERATE" | "HIGH";

export interface RiskFactor {
  feature: string;
  display_name: string;
  value: unknown;
  shap_value: number;
  direction: "increase" | "decrease" | string;
  /** false면 생활습관으로 바꿀 수 없거나(나이·가족력 등) 역인과가 의심되는 요인 */
  actionable: boolean;
  reverse_causation_suspected: boolean;
}

export interface DiseasePredictionResult {
  model_type: PredictionModelType;
  disease_name: string;
  model_version: string;
  risk_probability: number;
  /** 위험 확률 × 100 (%) */
  risk_score: number;
  risk_level: DiseaseRiskLevel;
  risk_level_label: string;
  risk_thresholds: { moderate: number; high: number };
  shap_output_space: string;
  base_value: number;
  risk_factors: RiskFactor[];
  out_of_training_range: string[];
}

export interface DiseasePrediction {
  id: string;
  status: DiseasePredictionStatus;
  status_label: string;
  annual_health_screening_id: string | null;
  monthly_health_survey_id: string | null;
  error_code: string | null;
  errors: { field: string; reason: string }[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  results: DiseasePredictionResult[];
}

export interface DiseasePredictionSummary {
  id: string;
  status: DiseasePredictionStatus;
  created_at: string;
  completed_at: string | null;
  results: {
    model_type: PredictionModelType;
    disease_name: string;
    risk_score: number;
    risk_level: DiseaseRiskLevel;
    risk_level_label: string;
  }[];
}

export interface CreateDiseasePredictionBody {
  annual_health_screening_id?: string;
  monthly_health_survey_id?: string;
}

export interface CreateDiseasePredictionResponse {
  id: string;
  status: DiseasePredictionStatus;
  events_url: string;
  created_at: string;
}

/* ── REST ── */

/** POST /api/v1/disease-predictions — 비워 두면 가장 최근 건강검진·월간 설문을 사용 */
export function createDiseasePrediction(
  body: CreateDiseasePredictionBody = {}
): Promise<CreateDiseasePredictionResponse> {
  return request<CreateDiseasePredictionResponse>(BASE, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** GET /api/v1/disease-predictions — 최신순 */
export function getDiseasePredictions(): Promise<DiseasePredictionSummary[]> {
  return request<DiseasePredictionSummary[]>(BASE);
}

/** GET /api/v1/disease-predictions/{prediction_id} */
export function getDiseasePrediction(predictionId: string): Promise<DiseasePrediction> {
  return request<DiseasePrediction>(`${BASE}/${predictionId}`);
}

export function eventsUrlOf(predictionId: string): string {
  return `${BASE}/${predictionId}/events`;
}

export function isFinalStatus(status: DiseasePredictionStatus): boolean {
  return status === "COMPLETED" || status === "FAILED";
}

/* ── SSE ── */

interface SseMessage {
  event: string;
  data: string;
}

/** text/event-stream 본문을 이벤트 단위로 읽습니다. 주석(`: heartbeat`)은 건너뜁니다. */
export async function* readSseMessages(
  body: ReadableStream<Uint8Array>
): AsyncGenerator<SseMessage> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const parse = (block: string): SseMessage | null => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (!line || line.startsWith(":")) continue;
      const sep = line.indexOf(":");
      const field = sep === -1 ? line : line.slice(0, sep);
      const value = sep === -1 ? "" : line.slice(sep + 1).replace(/^ /, "");
      if (field === "event") event = value;
      else if (field === "data") data.push(value);
    }
    return data.length ? { event, data: data.join("\n") } : null;
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const message = parse(block);
        if (message) yield message;
      }
    }
    buffer += decoder.decode();
    const last = parse(buffer);
    if (last) yield last;
  } finally {
    reader.releaseLock();
  }
}

/**
 * 예측 SSE에 한 번 연결해 결과를 기다립니다.
 * - `result`·`failed`: 확정된 예측을 반환
 * - `timeout`·`error`·연결 종료: null 반환 (호출 측에서 상세 조회로 확인)
 */
async function readPredictionEvents(
  eventsUrl: string,
  onStatus: ((status: DiseasePredictionStatus) => void) | undefined,
  signal: AbortSignal | undefined
): Promise<DiseasePrediction | null> {
  let res: Response;
  try {
    res = await requestStream(eventsUrl, signal);
  } catch (err) {
    // 404 등 응답 오류와 사용자 취소는 그대로 전달하고, 네트워크 오류는 상세 조회로 넘깁니다.
    if (err instanceof ApiError || isAbortError(err)) throw err;
    return null;
  }
  if (!res.body) return null;

  try {
    for await (const { event, data } of readSseMessages(res.body)) {
      if (event === "status") {
        const parsed = JSON.parse(data) as { status: DiseasePredictionStatus };
        onStatus?.(parsed.status);
      } else if (event === "result" || event === "failed") {
        return JSON.parse(data) as DiseasePrediction;
      } else if (event === "timeout" || event === "error") {
        return null;
      }
    }
  } catch (err) {
    if (isAbortError(err)) throw err;
    return null;
  }
  return null;
}

export class PredictionWaitTimeoutError extends Error {
  constructor(public predictionId: string) {
    super("예측 결과를 기다리는 시간이 초과되었습니다.");
  }
}

/** SSE 1회 최대 30초 × 4회 ≈ 2분. 그 뒤에도 확정되지 않으면 사용자가 다시 확인합니다. */
const MAX_STREAM_ATTEMPTS = 4;
const RECONNECT_DELAY_MS = 2000;

/**
 * 예측이 COMPLETED·FAILED로 확정될 때까지 기다립니다.
 * SSE를 받지 못하면(시간 초과·서버 오류·연결 끊김) 상세 조회로 확인한 뒤 다시 연결합니다.
 */
export async function waitForPredictionResult(
  predictionId: string,
  options: {
    eventsUrl?: string;
    onStatus?: (status: DiseasePredictionStatus) => void;
    signal?: AbortSignal;
  } = {}
): Promise<DiseasePrediction> {
  const { onStatus, signal } = options;
  const eventsUrl = options.eventsUrl ?? eventsUrlOf(predictionId);

  for (let attempt = 0; attempt < MAX_STREAM_ATTEMPTS; attempt++) {
    const result = await readPredictionEvents(eventsUrl, onStatus, signal);
    if (result) return result;

    const detail = await getDiseasePrediction(predictionId);
    if (isFinalStatus(detail.status)) return detail;
    onStatus?.(detail.status);

    await delay(RECONNECT_DELAY_MS, signal);
  }
  throw new PredictionWaitTimeoutError(predictionId);
}

/* ── Helpers ── */

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

export function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export const RISK_LEVEL_COLORS: Record<DiseaseRiskLevel, string> = {
  LOW: "#10B981",
  MODERATE: "#F59E0B",
  HIGH: "#EF4444",
};

export function riskLevelColor(level: DiseaseRiskLevel | string): string {
  return RISK_LEVEL_COLORS[level as DiseaseRiskLevel] ?? "#64748B";
}

const PREDICTION_STATUS_LABELS: Record<DiseasePredictionStatus, string> = {
  PENDING: "대기 중",
  PROCESSING: "분석 중",
  COMPLETED: "분석 완료",
  FAILED: "분석 실패",
};

export function predictionStatusLabel(status: DiseasePredictionStatus): string {
  return PREDICTION_STATUS_LABELS[status] ?? status;
}

const PREDICTION_ERROR_MESSAGES: Record<string, string> = {
  INVALID_INPUT: "입력한 건강 기록 값이 예측 기준에 맞지 않습니다.",
  MODEL_ERROR: "예측 모델 처리 중 오류가 발생했습니다.",
  INTERNAL_ERROR: "분석 중 서버 오류가 발생했습니다.",
  INVALID_MESSAGE: "분석 요청 형식에 문제가 있었습니다.",
  INVALID_RESULT: "분석 결과 형식에 문제가 있었습니다.",
  PUBLISH_FAILED: "분석 요청을 전달하지 못했습니다.",
  RESULT_EXPIRED: "분석 결과를 제시간에 받지 못했습니다.",
};

export function predictionErrorMessage(code: string | null): string {
  return (code && PREDICTION_ERROR_MESSAGES[code]) || "분석에 실패했습니다.";
}

/** 422 오류의 `loc`·예측 실패의 `field`를 화면 표시용 이름으로 바꿉니다. */
const SOURCE_LABELS: Record<string, { label: string; path: string }> = {
  health_profile: { label: "건강 프로필", path: "/app/health/profile" },
  annual_health_screening: { label: "건강검진", path: "/app/health/checkup" },
  monthly_health_survey: { label: "월별 건강기록", path: "/app/health/monthly" },
};

const FIELD_LABELS: Record<string, string> = {
  gender: "성별",
  birth_date: "생년월일",
  has_diabetes: "당뇨 진단 여부",
  has_hypertension: "고혈압 진단 여부",
  screening_at: "검진 일자",
  height: "키",
  weight: "체중",
  waist_circumference: "허리둘레",
  sbp: "수축기 혈압",
  dbp: "이완기 혈압",
  fbs: "공복혈당",
  hba1c: "당화혈색소",
  triglyceride: "중성지방",
  total_cholesterol: "총콜레스테롤",
  hdl: "HDL 콜레스테롤",
  ast: "AST",
  alt: "ALT",
  creatinine: "크레아티닌",
  diabetes_family_history: "당뇨 가족력",
  hypertension_family_history: "고혈압 가족력",
  smoking_status: "흡연 상태",
  smoking_fr_per_day: "하루 흡연량",
  drinking_status: "음주 상태",
  drinking_frequency: "음주 빈도",
  drinking_amount_per_session: "1회 음주량",
};

export interface InputIssue {
  source: string;
  sourcePath: string | null;
  field: string;
  reason: string;
}

function toInputIssue(parts: (string | number)[], reason: string): InputIssue {
  const [sourceKey, ...rest] = parts.map(String);
  const source = SOURCE_LABELS[sourceKey];
  const fieldKey = rest.join(".");
  return {
    source: source?.label ?? sourceKey,
    sourcePath: source?.path ?? null,
    field: FIELD_LABELS[fieldKey] ?? fieldKey,
    reason,
  };
}

export function inputIssuesFromValidation(errors: ValidationErrorItem[] = []): InputIssue[] {
  return errors.map((item) => toInputIssue(item.loc, item.msg));
}

export function inputIssuesFromPrediction(prediction: DiseasePrediction): InputIssue[] {
  return prediction.errors.map((item) => toInputIssue(item.field.split("."), item.reason));
}

/** 예측 요청 404 메시지 → 먼저 입력해야 할 기록 */
const MISSING_RECORD_MESSAGES: Record<string, keyof typeof SOURCE_LABELS> = {
  "Health Profile Not Found.": "health_profile",
  "Annual Health Screening Not Found.": "annual_health_screening",
  "Monthly Health Survey Not Found.": "monthly_health_survey",
};

export function missingRecordOf(err: ApiError): { label: string; path: string } | null {
  const key = MISSING_RECORD_MESSAGES[err.message];
  return key ? SOURCE_LABELS[key] : null;
}

export function formatFactorValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "boolean") return value ? "예" : "아니오";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);
  }
  return String(value);
}
