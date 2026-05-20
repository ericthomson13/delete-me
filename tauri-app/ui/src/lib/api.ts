// Resolves the FastAPI sidecar base URL.
//
// In a Tauri runtime we call the `get_api_base` Rust command, which returns
// the loopback address the sidecar advertised on stdout (LISTENING_ON ...).
// In a plain browser (`pnpm dev`), we fall back to a vite env override so a
// developer can point at a manually-launched FastAPI service.

let cached: string | null = null;

function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

export async function apiBase(): Promise<string> {
  if (cached) return cached;
  if (isTauri()) {
    const { invoke } = await import('@tauri-apps/api/core');
    cached = await invoke<string>('get_api_base');
    return cached;
  }
  cached = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';
  return cached;
}

export interface CaseRow {
  id: number;
  profile_id: number;
  broker_id: string;
  status: string;
  created_at: string | null;
  sent_at: string | null;
  audit_due_at: string | null;
  transport_message_id: string | null;
  agent_designation_sha256: string | null;
  last_error: string | null;
}

export async function listCases(): Promise<CaseRow[]> {
  const base = await apiBase();
  const res = await fetch(`${base}/cases`);
  if (!res.ok) throw new Error(`GET /cases failed: ${res.status}`);
  return (await res.json()) as CaseRow[];
}
