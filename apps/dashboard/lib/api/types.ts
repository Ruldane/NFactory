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

export interface OverviewFilters {
  days: number | null;
  project_type: string | null;
}

// Metrics of spec §14.1; null means "nothing to measure", never a fake zero.
export interface FactoryMetrics {
  end_to_end_delivery_rate: number | null;
  first_pass_test_rate: number | null;
  repair_success_rate: number | null;
  time_to_preview_seconds: number | null;
  time_to_draft_pr_seconds: number | null;
  human_intervention_count: number;
  cost_per_successful_delivery: number | null;
  critical_policy_violation_count: number;
}

export interface CallMetrics {
  calls: number;
  failures: number;
  latency_p50_s: number | null;
  latency_p95_s: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  cost_complete: boolean;
}

export interface ProviderMetric extends CallMetrics {
  provider: string;
  model: string;
}

export interface AgentMetric extends CallMetrics {
  agent: string;
}

export interface DashboardSummary {
  filters: OverviewFilters;
  demo_data: boolean;
  projects: number;
  runs: RunCounts;
  success_rate: number | null;
  avg_duration_seconds: number | null;
  cost_estimate_usd: number | null;
  approvals_pending: number;
  recent_runs: RecentRun[];
  metrics: FactoryMetrics;
  providers: ProviderMetric[];
  agents: AgentMetric[];
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
  details: {
    role?: string;
    provider?: string;
    model?: string;
    kind?: string;
    message?: string;
  };
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
  budget: Partial<
    Record<"max_llm_calls" | "max_agent_steps" | "max_repair_attempts", number>
  >;
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
  retention: RetentionPolicy;
  retention_bounds: Record<keyof RetentionPolicy, { min: number; max: number }>;
}

// ADR-0015: null keeps forever.
export interface RetentionPolicy {
  runs_days: number | null;
  audit_days: number | null;
}

export interface Member {
  user_id: string;
  display_name: string;
  email: string | null;
  role: string;
  role_label: string;
  is_owner: boolean;
  created_at: string;
}

export interface Erasure {
  user_id: string;
  anonymised: boolean;
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
  regions: { id: string; label: string; needs_workspace: boolean; zone: Zone; country: string }[];
  region: string | null;
  residency: Residency;
  workspace_id: string | null;
  custom_url: boolean;
  base_url: string | null;
  discovery: boolean;
  docs_url: string;
  last_checked_at: string | null;
  last_error: { kind: string; message: string } | null;
}

// Where an engine processes data (ADR-0016).
export type Zone = "local" | "eu" | "outside_eu" | "unknown";

export interface Residency {
  zone: Zone;
  country: string;
  source: string;
  note: string;
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
  eu_only: boolean;
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
export type BridgeStatus =
  "unreachable" | "unpaired" | "paired" | "token_rejected";
export type LocalRuntimeStatus =
  "not_installed" | "installed" | "needs_login" | "connected";

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

// Coding-agent tasks on an authorized repository of the user's machine (tasks 4.3, 4.4):
// the user's Codex, or a handoff they run in their own Claude Code.
export type AgentRuntime = "codex" | "claude";

export interface LocalRepo {
  id: string;
  name: string;
  github?: string | null; // the GitHub repository the user allowed pushes to
}

// Publication facts, each read back from git and GitHub by the bridge (task 4.6).
export type PublicationState =
  "local_commit_created" | "pushed" | "pr_created" | "merged";

export interface Publication {
  repo: string;
  commit: string;
  state: PublicationState | null;
  pushed: boolean;
  pr: {
    number: number;
    url: string;
    state: string;
    draft: boolean;
    head: string;
    merged: boolean;
  } | null;
  verified_at: number;
}

export type AgentTaskStatus =
  | "preparing"
  | "running"
  | "awaiting_user"
  | "succeeded"
  | "no_changes"
  | "failed"
  | "cancelled"
  | "discarded";

export interface AgentEvent {
  type:
    | "started"
    | "message"
    | "command"
    | "file_change"
    | "completed"
    | "failed"
    | "error"
    | "warning";
  text?: string;
  message?: string;
  command?: string;
  status?: string;
  exit_code?: number | null;
  changes?: { path: string; kind: string }[];
  usage?: Record<string, number>;
}

export interface AgentTask {
  id: string;
  runtime: AgentRuntime;
  repo_id: string;
  branch: string;
  base: string;
  status: AgentTaskStatus;
  events: AgentEvent[];
  manifest: { path: string; change: "added" | "modified" | "deleted" }[];
  diff: string;
  diff_truncated: boolean;
  error: string;
  created_at: number;
  publication?: Publication | null;
}

// A sandbox check of a task's change (task 4.4): the verdict comes from the JUnit report.
export type AgentCheckStatus =
  "queued" | "running" | "passed" | "failed" | "not_tested" | "error";

export interface AgentCheckReport {
  command: string;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  failures: { name: string; message: string }[];
  output_tail: string;
}

export interface AgentCheck {
  id: string;
  task_id: string;
  repo_id: string;
  runtime: string;
  status: AgentCheckStatus;
  report: AgentCheckReport | null;
  error: string;
  created_at: string;
  finished_at: string | null;
}

// A run's trace (task 5.2): the run, its stored steps, then each call under its step.
export interface TraceSpan {
  id: string;
  parent_id: string | null;
  kind: "run" | "step" | "agent" | "check";
  name: string;
  start: string | null;
  end: string | null;
  duration_s: number | null;
  status: "ok" | "error" | "running" | "pending" | "skipped";
  agent_role?: string | null;
  provider?: string | null;
  model?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  cost_usd?: number | null;
  calls?: number | null;
  exit_code?: number | null;
}

export interface RunTrace {
  run_id: string;
  trace_id: string | null;
  cost_usd: number | null;
  spans: TraceSpan[];
}

// RBAC, approval center and audit log (task 5.4, apps/api/app/schemas/access.py).
export type Permission = "read" | "approve" | "audit" | "build" | "configure";

export interface WorkspaceAccess {
  id: string;
  name: string;
  role: string;
  role_label: string;
  permissions: Permission[];
}

export interface Me {
  user_id: string;
  display_name: string;
  workspaces: WorkspaceAccess[];
}

export interface ApprovalItem {
  id: string;
  status: string;
  action_type: string;
  action_label: string;
  summary: string;
  run_id: string;
  run_state: string;
  project_id: string;
  project_title: string;
  created_at: string;
  decided_at: string | null;
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  target: string;
  decision: string | null;
  details: Record<string, unknown>;
}

export interface AuditPage {
  items: AuditEntry[];
  next_before: number | null;
}

// Reusable factory recipes (task 5.5, apps/api/app/schemas/saved_recipes.py).
export interface SavedRecipe {
  id: string;
  name: string;
  description: string;
  project_type: ProjectType;
  template_id: string | null;
  request: string;
  source_run_id: string | null;
  created_by: string | null;
  created_at: string;
  uses: number;
  last_used_at: string | null;
}
