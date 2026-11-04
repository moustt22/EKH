const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, options: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : "Request failed";
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

export async function downloadDocument(id: string, filename: string, token: string): Promise<void> {
  const response = await fetch(`${API_URL}/documents/${id}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const text = await response.text();
    let message = "Download failed";
    try {
      const data = JSON.parse(text);
      if (typeof data.detail === "string") {
        message = data.detail;
      }
    } catch {
      message = text || message;
    }
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
