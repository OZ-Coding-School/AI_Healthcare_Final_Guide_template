import { saveToken } from "./auth";
import { request } from "./client";

const BASE = "/api/v1/auth";

export type WithdrawalReason =
  "NOT_USEFUL" | "INCONVENIENT" | "PRIVACY" | "TOO_FREQUENT" | "SWITCH_SERVICE" | "OTHER";

export const WITHDRAWAL_REASON_LABELS: Record<WithdrawalReason, string> = {
  NOT_USEFUL: "서비스가 도움이 되지 않아요",
  INCONVENIENT: "사용이 불편해요",
  PRIVACY: "개인정보가 걱정돼요",
  TOO_FREQUENT: "알림이 너무 많아요",
  SWITCH_SERVICE: "다른 서비스를 이용할게요",
  OTHER: "기타",
};

/* ── Auth API calls ── */

/** 1. 회원가입 */
export function signup(body: {
  email: string;
  password: string;
  name: string;
  nickname: string;
  phone_number: string;
}) {
  return request<void>(`${BASE}/signup`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** 2. 회원가입 인증 메일 발송 */
export function sendSignupVerificationMail(email: string) {
  return request<void>(`${BASE}/signup/send-verification-mail`, {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

/** 3. 회원가입 이메일 인증 확인 */
export function verifySignupEmail(email: string, code: string) {
  return request<void>(`${BASE}/signup/verify-email`, {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

/** 4. 로그인 */
export async function login(email: string, password: string): Promise<string> {
  const { access_token } = await request<{ access_token: string }>(`${BASE}/login`, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  saveToken(access_token);
  return access_token;
}

/** 5. 회원 탈퇴 */
export function withdraw(body: {
  reason: WithdrawalReason;
  reason_detail?: string;
  feedback?: string;
}) {
  return request<void>(`${BASE}/withdraw`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** 6. 계정 복구 인증 메일 발송 */
export function sendRecoveryMail(email: string) {
  return request<void>(`${BASE}/auth/recovery/send-mail`, {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

/** 7. 계정 복구 이메일 인증 확인 */
export function verifyRecoveryMail(email: string, code: string) {
  return request<void>(`${BASE}/auth/recovery/verify-mail`, {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

/** 8. 토큰 갱신 */
export function refreshToken() {
  return request<{ access_token: string }>(`${BASE}/token/refresh`);
}
