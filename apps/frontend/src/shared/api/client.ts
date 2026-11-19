import { getToken, saveToken, clearAuth } from "./auth";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "";
if (!BACKEND_URL) {
  throw new Error("BACKEND_URL is not defined in environment variables");
}

/** FastAPI 422 검증 오류의 항목. `loc`은 고칠 위치(기록, 필드)입니다. */
export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type?: string;
}

/**
 * 백엔드 오류 응답 본문.
 * - 명세 형식: HTTPException은 `message`, 검증 오류는 `code`·`message`·`errors`
 * - FastAPI 기본 형식: HTTPException은 `detail`(문자열), 검증 오류는 `detail`(항목 배열)
 * 현재 백엔드는 예외 핸들러가 적용되지 않아 기본 형식으로 응답하므로 두 형식을 모두 읽습니다.
 * 읽은 결과는 `message`·`errors`로 맞춰 둡니다.
 */
export interface ApiErrorBody {
  code?: string;
  message?: unknown;
  errors?: ValidationErrorItem[];
  detail?: unknown;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body: ApiErrorBody = {}
  ) {
    super(message);
  }
}

function toUrl(path: string): string {
  return path.startsWith("http") ? path : `${BACKEND_URL}${path}`;
}

function isValidationErrorList(value: unknown): value is ValidationErrorItem[] {
  return (
    Array.isArray(value) &&
    value.every((item) => item && Array.isArray(item.loc) && typeof item.msg === "string")
  );
}

/** 검증 오류 항목을 "필드: 사유" 형태로 요약합니다. `body` 같은 위치 접두사는 생략합니다. */
function summarizeValidationErrors(errors: ValidationErrorItem[]): string {
  const items = errors.map((item) => {
    const field = item.loc.filter((part) => part !== "body").join(".");
    return field ? `${field}: ${item.msg}` : item.msg;
  });
  return `입력값을 확인해주세요. (${items.join(", ")})`;
}

async function toApiError(res: Response): Promise<ApiError> {
  const raw: ApiErrorBody = (await res.json().catch(() => ({}))) ?? {};
  const errors = raw.errors ?? (isValidationErrorList(raw.detail) ? raw.detail : undefined);

  let message: string;
  if (typeof raw.message === "string" && !errors?.length) message = raw.message;
  else if (typeof raw.detail === "string") message = raw.detail;
  else if (errors?.length) message = summarizeValidationErrors(errors);
  else if (typeof raw.message === "string") message = raw.message;
  else message = res.statusText;

  return new ApiError(res.status, message, { ...raw, message, errors });
}

function redirectToLogin(): never {
  clearAuth();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
  throw new ApiError(401, "Unauthorized");
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/auth/token/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return false;
    const { access_token } = await res.json();
    saveToken(access_token);
    return true;
  } catch {
    return false;
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const token = getToken();

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers ?? {}),
  };

  const res = await fetch(toUrl(path), {
    ...options,
    headers,
    credentials: "include",
  });

  if (res.status === 401 && retry) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, options, false);
    redirectToLogin();
  }

  if (res.status === 204) {
    return undefined as T;
  }

  if (!res.ok) {
    throw await toApiError(res);
  }

  return res.json() as Promise<T>;
}

/**
 * SSE처럼 응답 본문을 직접 읽어야 하는 요청입니다.
 * 브라우저 EventSource는 Authorization 헤더를 보낼 수 없어 fetch 스트리밍을 사용합니다.
 * 인증·토큰 갱신·오류 처리는 request와 같습니다.
 */
export async function requestStream(
  path: string,
  signal?: AbortSignal,
  retry = true
): Promise<Response> {
  const token = getToken();

  const res = await fetch(toUrl(path), {
    headers: {
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "include",
    cache: "no-store",
    signal,
  });

  if (res.status === 401 && retry) {
    const refreshed = await tryRefresh();
    if (refreshed) return requestStream(path, signal, false);
    redirectToLogin();
  }

  if (!res.ok) {
    throw await toApiError(res);
  }

  return res;
}
