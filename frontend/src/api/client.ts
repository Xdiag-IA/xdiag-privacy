import axios, { AxiosInstance } from "axios";
import type { HealthResponse, LabelsResponse, RedactResponse } from "./types";

const baseURL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

const http: AxiosInstance = axios.create({
  baseURL,
  timeout: 60_000,
});

export async function getHealth(): Promise<HealthResponse> {
  const res = await http.get<HealthResponse>("/api/health");
  return res.data;
}

export async function getLabels(): Promise<LabelsResponse> {
  const res = await http.get<LabelsResponse>("/api/labels");
  return res.data;
}

export interface RedactOptions {
  reveal?: boolean;
  threshold?: number;
  isSynthetic?: boolean;
  signal?: AbortSignal;
}

export async function postRedact(
  file: File,
  opts: RedactOptions = {},
): Promise<RedactResponse> {
  const form = new FormData();
  form.append("file", file);

  const params: Record<string, string> = {};
  if (opts.reveal != null) params.reveal = String(opts.reveal);
  if (opts.threshold != null) params.threshold = String(opts.threshold);
  if (opts.isSynthetic != null) params.is_synthetic = String(opts.isSynthetic);

  const res = await http.post<RedactResponse>("/api/redact", form, {
    params,
    headers: { "Content-Type": "multipart/form-data" },
    signal: opts.signal,
  });
  return res.data;
}
