import { closureHeaders } from "./closureAccess";

export class ApiUnavailableError extends Error {}

const retryableAnalysisEndpoints = new Set(["/api/jd/parse", "/api/resume/parse", "/api/match"]);
const retryDelayMs = 500;
const liveGetAttempts = 4;

function wait(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export function apiUrl(endpoint: string, baseUrl = apiBaseUrl): string {
  // Bundled static evidence belongs to the frontend, not the separate FastAPI host.
  return endpoint.startsWith("/data/") ? endpoint : `${baseUrl}${endpoint}`;
}

function responseError(status: number, detail?: unknown): Error {
  const message = typeof detail === "string" ? detail : "";
  if (status === 401) return new Error("缺少管理员授权，请输入管理员 Token 后重试。");
  if (status === 403 && message === "P1 writes are disabled") return new Error("后端已关闭写入功能；当前只能读取已发布数据。");
  if (status === 403 && message === "Administrator credential rejected") return new Error("管理员 Token 错误或已失效。");
  if (status === 403 && message === "untrusted origin") return new Error("当前页面来源未获后端写入授权。");
  if (status === 409) return new Error(message || "版本冲突，请重新读取最新版本后再操作。");
  if (status === 503) return new Error("后端存储不可用或数据库不可写；本次操作未成功。");
  return new Error(message || `请求失败（${status}）`);
}

export async function getJson<T>(endpoint: string, fallback?: string): Promise<{ data: T; fallback: boolean }> {
  for (let attempt = 0; attempt < liveGetAttempts; attempt += 1) {
    try {
      const response = await fetch(apiUrl(endpoint), { cache: "no-store" });
      if (response.ok) return { data: await response.json() as T, fallback: false };
      if (![502, 503, 504].includes(response.status) || attempt + 1 >= liveGetAttempts) break;
    } catch (error) {
      if (!(error instanceof TypeError) || attempt + 1 >= liveGetAttempts) break;
    }
    await wait(retryDelayMs * (attempt + 1));
  }
  if (!fallback) throw new ApiUnavailableError("暂时无法连接数据服务，请稍后重试。");
  const response = await fetch(fallback, { cache: "no-store" });
  if (!response.ok) throw new ApiUnavailableError("当前模块数据尚未生成。");
  return { data: await response.json() as T, fallback: true };
}

export async function postJson<T>(endpoint: string, payload: unknown): Promise<T> {
  const attempts = retryableAnalysisEndpoints.has(endpoint) ? 2 : 1;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(apiUrl(endpoint), { method: "POST", headers: { "Content-Type": "application/json", ...closureHeaders(endpoint) }, body: JSON.stringify(payload) });
      if (!response.ok) {
        const value = await response.json().catch(() => null) as { detail?: unknown } | null;
        const transient = [502, 503, 504].includes(response.status) && !value?.detail;
        if (transient && attempt + 1 < attempts) { await wait(retryDelayMs); continue; }
        if (response.status >= 500 && !value?.detail) throw new ApiUnavailableError("服务正在唤醒，请点击重试。");
        throw responseError(response.status, value?.detail);
      }
      return await response.json() as T;
    } catch (error) {
      if (error instanceof TypeError && attempt + 1 < attempts) { await wait(retryDelayMs); continue; }
      if (error instanceof TypeError) throw new ApiUnavailableError("网络连接中断，请检查网络后重试。");
      throw error;
    }
  }
  throw new ApiUnavailableError("网络连接中断，请检查网络后重试。");
}

export async function postFile<T>(endpoint: string, file: File): Promise<T> {
  try {
    const body = new FormData();
    body.append("file", file, file.name);
    const response = await fetch(apiUrl(endpoint), { method: "POST", body });
    if (!response.ok) {
      const value = await response.json().catch(() => null) as { detail?: unknown } | null;
      throw responseError(response.status, value?.detail);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof TypeError) throw new ApiUnavailableError("后端服务不可用，请稍后重试。");
    throw error;
  }
}

export async function postThenGet<Written, Authoritative>(
  endpoint: string,
  payload: unknown,
  authoritativeEndpoint: (written: Written) => string,
): Promise<Authoritative> {
  const written = await postJson<Written>(endpoint, payload);
  return (await getJson<Authoritative>(authoritativeEndpoint(written))).data;
}
