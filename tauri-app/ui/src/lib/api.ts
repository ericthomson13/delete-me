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

export type BrokerTier = 'enterprise_aggregator' | 'people_search' | 'long_tail';
export type OptOutMethod = 'email' | 'web_form' | 'postal' | 'drop' | 'phone';

export interface BrokerRow {
  id: string;
  name: string;
  tier: BrokerTier | null;
  accepts_authorized_agent: boolean;
  user_submit_only: boolean;
  methods: OptOutMethod[];
  drop_registered: boolean | null;
}

export async function listBrokers(): Promise<BrokerRow[]> {
  const base = await apiBase();
  const res = await fetch(`${base}/brokers`);
  if (!res.ok) throw new Error(`GET /brokers failed: ${res.status}`);
  return (await res.json()) as BrokerRow[];
}

export interface ProfileRow {
  id: number;
  full_legal_name: string;
  current_address: string;
  email: string | null;
  phone: string | null;
  dob_year: number | null;
  prior_addresses: string[];
  former_names: string[];
}

export interface ProfileInput {
  full_legal_name: string;
  current_address: string;
  email?: string | null;
  phone?: string | null;
  dob_year?: number | null;
  prior_addresses?: string[];
  former_names?: string[];
}

export async function listProfiles(): Promise<ProfileRow[]> {
  const base = await apiBase();
  const res = await fetch(`${base}/profiles`);
  if (!res.ok) throw new Error(`GET /profiles failed: ${res.status}`);
  return (await res.json()) as ProfileRow[];
}

export async function saveProfile(input: ProfileInput): Promise<ProfileRow> {
  const base = await apiBase();
  const res = await fetch(`${base}/profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST /profiles failed: ${res.status} — ${text}`);
  }
  return (await res.json()) as ProfileRow;
}
