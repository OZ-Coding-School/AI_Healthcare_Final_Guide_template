const TOKEN_KEY = "vitalai_token";
const USER_KEY  = "vitalai_user";

export interface AuthUser {
  email: string;
  nickname: string;
  name: string;
}

/* ── Token storage ── */
export function saveToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveUser(user: AuthUser) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw) as AuthUser; }
  catch { return null; }
}

export function saveAuth(token: string, user: AuthUser) {
  saveToken(token);
  saveUser(user);
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/** Alias kept for compatibility */
export const logout = clearAuth;

/* ── Auth check ── */
export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;
  try {
    // JWT payload is the second segment (base64url encoded)
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(decodeURIComponent(
      atob(b64).split("").map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
    ));
    return typeof payload.exp === "number" ? payload.exp > Date.now() / 1000 : true;
  } catch {
    // If we can't decode (e.g. opaque token from real server), trust its presence
    return true;
  }
}
