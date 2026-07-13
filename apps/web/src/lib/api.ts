// Central API client — token storage + fetch wrapper for the FastAPI backend.
export const API_BASE = "http://localhost:8000/api";

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: "admin" | "faculty" | "student";
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("campus_token");
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("campus_user");
  return raw ? (JSON.parse(raw) as AuthUser) : null;
}

export function saveAuth(token: string, user: AuthUser) {
  localStorage.setItem("campus_token", token);
  localStorage.setItem("campus_user", JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem("campus_token");
  localStorage.removeItem("campus_user");
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** fetch wrapper: attaches Bearer token, raises ApiError with backend detail. */
export async function api<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  // Only set JSON content-type when the body isn't FormData (CSV upload).
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}
