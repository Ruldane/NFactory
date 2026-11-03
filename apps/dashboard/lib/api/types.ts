// Mirrors the FastAPI response schemas (apps/api/app/schemas). Keep in sync; a later
// phase generates these from OpenAPI into packages/shared-contracts.

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Items<T> {
  items: T[];
}

export interface StepBrief {
  name: string;
  agent_role: string;
  state: string;
  attempts: number;
}

export interface RecentRun {
  id: string;
  project_id: string;
  project_title: string;
  state: string;
  is_demo: boolean;
  created_at: string;
  finished_at: string | null;
  steps: StepBrief[];
}

export interface RunCounts {
  total: number;
  active: number;
  completed: number;
  partial: number;
  failed: number;
  cancelled: number;
}

export interface DashboardSummary {
  demo_data: boolean;
  projects: number;
  runs: RunCounts;
  success_rate: number | null;
  avg_duration_seconds: number | null;
  cost_estimate_usd: number | null;
  approvals_pending: number;
  recent_runs: RecentRun[];
}

// Project types come from the recipe catalog (GET /recipes), so any string is possible.
export type ProjectType = string;

export interface Project {
  id: string;
  title: string;
  description: string;
  type: ProjectType;
  template_id: string | null;
  status: string;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
}

export interface Recipe {
  kind: string;
  project_type: ProjectType;
  label: string;
  description: string;
  deliverable: "code" | "non-code";
  outputs: string[];
  phase: number;
  available: boolean;
}

export interface RunStep extends StepBrief {
  id: string;
  position: number;
  output: Record<string, unknown>;
  started_at: string | null;
  ended_at: string | null;
  error: string | null;
}

// A run's live preview (task 3.10): `url` is the gateway page, on its own origin.
export interface Preview {
  running: boolean;
  url: string | null;
  expires_in_s: number | null;
}

export interface Engine {
  provider: string;
  model: string;
}

// A decision the run waits for: its engine failed and the routing says to ask.
export interface Approval {
  id: string;
  action_type: string;
  summary: string;
  details: { role?: string; provider?: string; model?: string; kind?: string; message?: string };
  status: string;
  created_at: string;
}

export interface RunDetail {
  id: string;
  project: { id: string; title: string; type: ProjectType };
  recipe: string | null;
  model: string | null;
  engines: Record<string, Engine>;
  pending_approval: Approval | null;
  request: string;
  // Set for a change request on a delivered run (scenario E).
  parent_run_id: string | null;
  state: string;
  error: string | null;
  cost_estimate_usd: number | null;
  budget: Partial<Record<"max_llm_calls" | "max_agent_steps" | "max_repair_attempts", number>>;
  trace_id: string | null;
  is_demo: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  steps: RunStep[];
}

export interface RunEvent {
  seq: number;
  type: string;
  step_id: string | null;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface CheckResult {
  name: string;
  stage: string;
  ok: boolean;
  detail: string;
}

export interface JUnitReport {
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  total: number;
  ok: boolean;
  failures: { name: string; message: string }[];
}

export interface FileList {
  files: string[];
}

export interface FileContent {
  path: string;
  content: string | null;
  binary: boolean;
  size: number;
}

export interface Artifact {
  id: string;
  filename: string;
  mime: string;
  size: number;
  checksum: string;
  created_at: string;
  download_url: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: unknown };
}

export interface RunLimits {
  max_llm_calls: number;
  max_agent_steps: number;
  max_repair_attempts: number;
}

export interface WorkspaceSettings {
  mode: string;
  demo_mode: boolean;
  sandbox: "isolated" | "local";
  run_limits: RunLimits;
  limit_bounds: Record<keyof RunLimits, { min: number; max: number }>;
}

// --- AI providers ("Moteurs IA", spec §6). No field ever carries a key. ---

export interface ProviderView {
  kind: string;
  label: string;
  family: "api" | "local" | "coding_agent";
  phase: number;
  available: boolean;
  status: string;
  needs_key: boolean;
  key_source: "stored" | "env" | null;
  env_key: string | null;
  env_key_available: boolean;
  regions: { id: string; label: string; needs_workspace: boolean }[];
  region: string | null;
  workspace_id: string | null;
  custom_url: boolean;
  base_url: string | null;
  discovery: boolean;
  docs_url: string;
  last_checked_at: string | null;
  last_error: { kind: string; message: string } | null;
}

export interface ProviderConfigInput {
  api_key?: string;
  use_env_key?: boolean;
  region?: string | null;
  workspace_id?: string | null;
  base_url?: string | null;
}

export interface ValidationResult {
  ok: boolean;
  status: string;
  message: string;
  latency_ms: number | null;
  models_found: number | null;
}

export interface Pricing {
  input_per_mtok: number;
  output_per_mtok: number;
  cached_input_per_mtok: number | null;
}

export interface CatalogModel {
  model_id: string;
  source: "manual" | "discovered";
  pricing: Pricing | null;
  context_window: number | null;
}

export type Fallback = "ask_user" | "none";

export interface RoutingConfig {
  default: Engine | null;
  roles: Record<string, Engine>;
  fallback: Fallback;
  local_only: boolean;
}

export interface RoutingView {
  routing: RoutingConfig;
  roles: { id: string; label: string }[];
}

// Knowledge base (phase 3).
export interface SourceCitation {
  id: string;
  document_id: string;
  path: string;
  start_line: number;
  end_line: number;
  section: string | null;
}

export interface KnowledgeDocument {
  id: string;
  path: string;
  project_id: string | null;
  kind: string | null;
  size_bytes: number | null;
  revision: string | null;
  chunks: number;
  embedded: number;
  created_at: string;
}

export interface UploadResult extends KnowledgeDocument {
  duplicate: boolean;
  replaced: boolean;
}

export interface KnowledgeDocumentDetail extends KnowledgeDocument {
  content: string;
}

export interface KnowledgeHit {
  chunk_id: string;
  document_id: string;
  path: string;
  content: string;
  start_line: number;
  end_line: number;
  section: string | null;
  symbol: string | null;
  page: number | null;
  score: number;
  matched: ("text" | "vector")[];
}

export interface KnowledgeSearch {
  hits: KnowledgeHit[];
  engine: { key: string; used: boolean; error: string | null };
}

export interface EmbeddingChoice {
  provider: string;
  model: string;
}

export interface EngineOption {
  provider: string;
  label: string;
  local: boolean;
  available: boolean;
  reason: string | null;
}

export interface KnowledgeSettings {
  embedding: EmbeddingChoice;
  index: { total: number; embedded: number };
  options: EngineOption[];
  index_error: string | null;
}

// Local coding tools seen through the bridge on the user's machine (tasks 4.1, 4.2).
export type BridgeStatus = "unreachable" | "unpaired" | "paired" | "token_rejected";
export type LocalRuntimeStatus = "not_installed" | "installed" | "needs_login" | "connected";

export interface LocalRuntime {
  kind: "codex" | "claude" | "gh";
  label: string;
  status: LocalRuntimeStatus;
  version: string | null;
  login: "chatgpt" | "api_key" | null;
  login_command: string | null;
  modes: Record<string, "available" | "blocked_by_policy">;
  detail: string;
}

export interface LocalRuntimesView {
  bridge: { status: BridgeStatus; message: string; version: string | null };
  runtimes: LocalRuntime[];
}
