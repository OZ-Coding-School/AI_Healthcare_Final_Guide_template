import { saveUser } from "./auth";
import { request } from "./client";

const BASE = "/api/v1/users";

export interface User {
  id: string;
  name: string;
  nickname: string;
  email: string;
  phone_number: string;
  created_at: string;
}

export interface UpdateUserBody {
  nickname?: string;
  phone_number?: string;
}

/** GET /api/v1/users/me */
export function getMyInfo(): Promise<User> {
  return request<User>(`${BASE}/me`);
}

/** PATCH /api/v1/users/me */
export async function updateMyInfo(body: UpdateUserBody): Promise<User> {
  const updated = await request<User>(`${BASE}/me`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  // Update localStorage with new user info
  saveUser({
    email: updated.email,
    nickname: updated.nickname,
    name: updated.name,
  });
  return updated;
}
