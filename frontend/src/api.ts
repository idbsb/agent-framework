export class ApiUnavailableError extends Error {}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(endpoint: string): string {
  return `${apiBaseUrl}${endpoint}`;
}

export async function getJson<T>(endpoint: string, fallback?: string): Promise<{ data: T; fallback: boolean }> {
  try {
    const response = await fetch(apiUrl(endpoint));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return { data: await response.json() as T, fallback: false };
  } catch (error) {
    if (!fallback) throw new ApiUnavailableError("后端服务未启动，请启动FastAPI服务。");
    const response = await fetch(fallback);
    if (!response.ok) throw new ApiUnavailableError("当前模块数据尚未生成。");
    return { data: await response.json() as T, fallback: true };
  }
}

export async function postJson<T>(endpoint: string, payload: unknown): Promise<T> {
  try {
    const response = await fetch(apiUrl(endpoint), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) {
      const value = await response.json().catch(() => null) as { detail?: unknown } | null;
      if (response.status >= 500 && !value?.detail) throw new ApiUnavailableError("后端服务未启动，请启动FastAPI服务。");
      throw new Error(typeof value?.detail === "string" ? value.detail : `请求失败（${response.status}）`);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof TypeError) throw new ApiUnavailableError("后端服务未启动，请启动FastAPI服务。");
    throw error;
  }
}
