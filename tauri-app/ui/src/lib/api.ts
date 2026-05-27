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
  let resolved: string;
  if (isTauri()) {
    const { invoke } = await import('@tauri-apps/api/core');
    resolved = await invoke<string>('get_api_base');
  } else {
    resolved = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';
  }
  cached = resolved;
  return resolved;
}

export type CaseStatus =
  | 'draft'
  | 'sent_dry_run'
  | 'sent'
  | 'sent_via_drop'
  | 'acknowledged'
  | 'deleted_confirmed'
  | 'audit_inconclusive'
  | 'noncompliant'
  | 'failed';

export interface CaseRow {
  id: number;
  profile_id: number;
  broker_id: string;
  status: CaseStatus;
  created_at: string | null;
  sent_at: string | null;
  audit_due_at: string | null;
  last_audited_at: string | null;
  transport_message_id: string | null;
  agent_designation_sha256: string | null;
  last_error: string | null;
  evidence_path: string | null;
}

export interface CaseDetail extends CaseRow {
  letter_markdown: string;
}

export interface AuditRow {
  id: number;
  source: string;
  found: boolean;
  inconclusive: boolean;
  listings_url: string | null;
  notes: string | null;
  checked_at: string;
}

export interface EvidenceBuildResult {
  case_id: number;
  directory: string;
  zip: string;
  manifest: string;
  file_count: number;
}

export async function listCases(): Promise<CaseRow[]> {
  const base = await apiBase();
  const res = await fetch(`${base}/cases`);
  if (!res.ok) throw new Error(`GET /cases failed: ${res.status}`);
  return (await res.json()) as CaseRow[];
}

export async function getCase(id: number): Promise<CaseDetail> {
  const base = await apiBase();
  const res = await fetch(`${base}/cases/${id}`);
  if (!res.ok) throw new Error(`GET /cases/${id} failed: ${res.status}`);
  return (await res.json()) as CaseDetail;
}

export async function listCaseAudits(id: number): Promise<AuditRow[]> {
  const base = await apiBase();
  const res = await fetch(`${base}/cases/${id}/audits`);
  if (!res.ok) throw new Error(`GET /cases/${id}/audits failed: ${res.status}`);
  return (await res.json()) as AuditRow[];
}

export interface AggregateAuditRow extends AuditRow {
  case_id: number;
  broker_id: string;
  case_status: CaseStatus;
}

export async function listAllAudits(limit = 200): Promise<AggregateAuditRow[]> {
  const base = await apiBase();
  const res = await fetch(`${base}/audits?limit=${limit}`);
  if (!res.ok) throw new Error(`GET /audits failed: ${res.status}`);
  return (await res.json()) as AggregateAuditRow[];
}

export interface EvidencePackageRow {
  case_id: number;
  broker_id: string;
  case_status: CaseStatus;
  evidence_path: string | null;
  on_disk: boolean;
  last_audited_at: string | null;
}

export async function listEvidencePackages(): Promise<EvidencePackageRow[]> {
  const base = await apiBase();
  const res = await fetch(`${base}/evidence`);
  if (!res.ok) throw new Error(`GET /evidence failed: ${res.status}`);
  return (await res.json()) as EvidencePackageRow[];
}

export async function runAudit(id: number): Promise<{ results: AuditRow[] }> {
  const base = await apiBase();
  const res = await fetch(`${base}/cases/${id}/audit`, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST /cases/${id}/audit failed: ${res.status} — ${text}`);
  }
  return (await res.json()) as { results: AuditRow[] };
}

export async function buildEvidence(id: number): Promise<EvidenceBuildResult> {
  const base = await apiBase();
  const res = await fetch(`${base}/cases/${id}/evidence`, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST /cases/${id}/evidence failed: ${res.status} — ${text}`);
  }
  return (await res.json()) as EvidenceBuildResult;
}

export async function evidenceDownloadUrl(id: number): Promise<string> {
  const base = await apiBase();
  return `${base}/cases/${id}/evidence/download`;
}

export type AutomationTier = 'auto' | 'semi' | 'manual';
export type AutomationStatus = 'submitted' | 'needs_human' | 'failed';

export interface AutomationResult {
  status: AutomationStatus;
  broker_id: string;
  dry_run: boolean;
  screenshot_path: string | null;
  evidence_payload: Record<string, unknown>;
  fallback_reason: string | null;
}

export async function runAutomation(caseId: number, dryRun: boolean): Promise<AutomationResult> {
  const base = await apiBase();
  const res = await fetch(`${base}/cases/${caseId}/automation-run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dry_run: dryRun }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST /cases/${caseId}/automation-run failed: ${res.status} — ${text}`);
  }
  return (await res.json()) as AutomationResult;
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
  automation_tier: AutomationTier | null;
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

// ============================================================ Discovery surface

export type PresenceStatus = 'found' | 'not_found' | 'inconclusive';

export interface PresenceResult {
  id: number;
  broker_id: string;
  source: string;
  status: PresenceStatus;
  found: boolean;
  inconclusive: boolean;
  listings_url: string | null;
  notes: string | null;
  checked_at: string | null;
}

export interface PresenceCheckResponse {
  results: PresenceResult[];
  summary: {
    found: number;
    not_found: number;
    inconclusive: number;
    no_audit_source_configured: number;
    brokers_checked: number;
  };
}

export async function runPresenceCheck(
  profileId: number,
  options: { brokerIds?: string[]; freshDays?: number } = {},
): Promise<PresenceCheckResponse> {
  const base = await apiBase();
  const body: Record<string, unknown> = {};
  if (options.brokerIds !== undefined) body.broker_ids = options.brokerIds;
  if (options.freshDays !== undefined) body.fresh_days = options.freshDays;
  const res = await fetch(`${base}/profiles/${profileId}/presence-check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST /profiles/${profileId}/presence-check failed: ${res.status} — ${text}`);
  }
  return (await res.json()) as PresenceCheckResponse;
}

export async function listPresenceResults(
  profileId: number,
  brokerId?: string,
): Promise<PresenceResult[]> {
  const base = await apiBase();
  const url = brokerId
    ? `${base}/profiles/${profileId}/presence-results?broker_id=${encodeURIComponent(brokerId)}`
    : `${base}/profiles/${profileId}/presence-results`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET presence-results failed: ${res.status}`);
  return (await res.json()) as PresenceResult[];
}

export type BreachProviderId = 'hibp' | 'intelx' | 'dehashed';

export interface BreachProviderStatus {
  source_id: BreachProviderId | string;
  available: boolean;
  detail: string;
}

export interface BreachProvidersResponse {
  active: string[];
  providers: BreachProviderStatus[];
}

export interface BreachExposure {
  id: number;
  source: string;
  email: string;
  breach_name: string;
  breach_date: string | null;
  data_classes: string[];
  description_excerpt: string | null;
  checked_at: string | null;
}

export interface BreachCheckResponse {
  results: Record<string, BreachExposure[]>;
  providers: {
    active: string[];
    skipped_at_startup: Array<{ source_id: string; detail: string }>;
    disabled_mid_run: Array<{ source_id: string; detail: string }>;
  };
}

export async function listBreachProviders(): Promise<BreachProvidersResponse> {
  const base = await apiBase();
  const res = await fetch(`${base}/breaches/providers`);
  if (!res.ok) throw new Error(`GET /breaches/providers failed: ${res.status}`);
  return (await res.json()) as BreachProvidersResponse;
}

export async function runBreachCheck(
  profileId: number,
  emails?: string[],
): Promise<BreachCheckResponse> {
  const base = await apiBase();
  const body: Record<string, unknown> = {};
  if (emails !== undefined) body.emails = emails;
  const res = await fetch(`${base}/profiles/${profileId}/breach-check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 503) {
    const detail = (await res.json()).detail;
    const err = new Error('no breach providers configured');
    (err as Error & { providers?: unknown }).providers = detail.providers;
    throw err;
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST /profiles/${profileId}/breach-check failed: ${res.status} — ${text}`);
  }
  return (await res.json()) as BreachCheckResponse;
}

export interface PasswordCheckResponse {
  breach_count: number;
  found: boolean;
}

export async function checkPassword(password: string): Promise<PasswordCheckResponse> {
  const base = await apiBase();
  const res = await fetch(`${base}/passwords/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST /passwords/check failed: ${res.status} — ${text}`);
  }
  return (await res.json()) as PasswordCheckResponse;
}
