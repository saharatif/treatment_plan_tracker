import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const TOKEN_KEY = "orbs.jwt";

export type DashboardPlan = {
  patient_id: string;
  plan_id: string;
  status: string;
  completed: number;
  days_remaining?: number;
  days_left?: number;
  plan_status: string;
};

export type PatientDetail = {
  plan: Record<string, string>;
  orbs: Array<Record<string, string | number | null>>;
};

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (response.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("auth-expired"));
  }
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export function useLogin() {
  return useMutation({
    mutationFn: (payload: { username: string; password: string; patient_id?: string }) =>
      request<{ access_token: string; user: { role: string } }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(payload)
      })
  });
}

export function useDashboard() {
  return useQuery({ queryKey: ["dashboard"], queryFn: () => request<DashboardPlan[]>("/api/dashboard"), refetchInterval: 30000 });
}

export function useAtRisk() {
  return useQuery({ queryKey: ["at-risk"], queryFn: () => request<DashboardPlan[]>("/api/at-risk"), refetchInterval: 30000 });
}

export function usePatientDetail(patientId: string | null) {
  return useQuery({
    queryKey: ["patient", patientId],
    queryFn: () => request<PatientDetail>(`/api/patients/${patientId}`),
    enabled: Boolean(patientId)
  });
}

export function useCompleteOrb() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ orbRef, notes }: { orbRef: string; notes?: string }) =>
      request(`/api/orbs/${orbRef}/complete`, { method: "POST", body: JSON.stringify({ notes }) }),
    onSuccess: () => client.invalidateQueries()
  });
}

export function useSetOrbStatus() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ orbRef, status, notes }: { orbRef: string; status: string; notes?: string }) =>
      request(`/api/orbs/${orbRef}/status`, { method: "POST", body: JSON.stringify({ status, notes }) }),
    onSuccess: () => client.invalidateQueries()
  });
}

export function useUploadPlan() {
  return useMutation({
    mutationFn: (payload: { file: File; piiJson?: string }) => {
      const form = new FormData();
      form.set("file", payload.file);
      if (payload.piiJson) form.set("pii_json", payload.piiJson);
      return request<Record<string, unknown>>("/api/ingest", { method: "POST", body: form });
    }
  });
}

export function useConfirmBilling() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => request(`/api/plans/${planId}/confirm-billing`, { method: "POST" }),
    onSuccess: () => client.invalidateQueries()
  });
}

export function useQuotations() {
  return useQuery({ queryKey: ["quotations"], queryFn: () => request<Array<Record<string, unknown>>>("/api/quotations") });
}

export function reportUrl(planId: string) {
  return `${API_BASE}/api/plans/${planId}/report`;
}

export async function downloadReport(planId: string) {
  const token = getToken();
  const response = await fetch(reportUrl(planId), {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  if (!response.ok) throw new Error(await response.text());
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener,noreferrer");
}
