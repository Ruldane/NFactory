"use client";

// Coding-agent tasks on the user's own machine (tasks 4.3, 4.4, spec §6.4, §6.5). The user
// picks a repository they authorized on the bridge, describes a small change and agrees,
// each time, to work in a separate copy (git worktree): either their Codex runs there, or
// NFactory prepares a handoff they run in their own Claude Code, then imports the changes.
// NFactory shows the events, changed files and diff, and tests the change in its sandbox.
// Nothing is committed or pushed here.

import { cn } from "cn";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { AgentCheckPanel } from "@/components/agents/agent-check";
import { DiffView } from "@/components/agents/diff-view";
import { TONE_CLASSES } from "@/components/runs/tone";
import {
  ALERT,
  DANGER,
  FIELD,
  KICKER,
  PRIMARY,
  SECONDARY,
} from "@/components/ui/form-styles";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAgentTask,
  useAgentTaskAction,
  useLocalRepos,
  useStartAgentTask,
} from "@/lib/api/agent-tasks";
import { ApiError } from "@/lib/api/client";
import type { AgentRuntime, AgentTask, LocalRepo } from "@/lib/api/types";
import {
  CHANGE_LABELS,
  describeAgentEvent,
  describeTaskStatus,
  isTaskActive,
  isTaskCheckable,
  visibleEvents,
} from "@/lib/agent-task-status";

const MAX_TASK = 4000;

const AGENTS: Record<
  AgentRuntime,
  { label: string; consent: string; action: string; title: string }
> = {
  codex: {
    label: "Codex — piloté par NFactory",
    consent:
      "J'autorise Codex, installé sur ce poste, à modifier une copie de travail séparée de ce dépôt. " +
      "Il utilise ma connexion Codex et consomme mon quota ChatGPT. Rien n'est commité ni poussé.",
    action: "Lancer Codex",
    title: "Tâche Codex",
  },
  claude: {
    label: "Claude Code — vous le lancez vous-même",
    consent:
      "J'autorise NFactory à préparer une copie de travail séparée de ce dépôt et un brief. " +
      "Je lancerai Claude Code moi-même, avec mon compte. Rien n'est commité ni poussé.",
    action: "Préparer le relais",
    title: "Relais Claude Code",
  },
};

function TaskForm({
  repos,
  onStarted,
}: {
  repos: LocalRepo[];
  onStarted: (id: string) => void;
}) {
  const [runtime, setRuntime] = useState<AgentRuntime>("codex");
  const [repoId, setRepoId] = useState(repos[0]?.id ?? "");
  const [task, setTask] = useState("");
  const [consent, setConsent] = useState(false);
  const start = useStartAgentTask();

  function submit(event: FormEvent) {
    event.preventDefault();
    start.mutate(
      { runtime, repoId, task: task.trim() },
      { onSuccess: (created) => onStarted(created.id) },
    );
  }

  const ready =
    consent && repoId !== "" && task.trim() !== "" && !start.isPending;
  return (
    <form
      onSubmit={submit}
      className="space-y-4 border border-navy/15 bg-cream/60 p-5"
    >
      <fieldset className="space-y-2">
        <legend className={KICKER}>Agent</legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {(Object.keys(AGENTS) as AgentRuntime[]).map((kind) => (
            <label
              key={kind}
              className="flex items-center gap-2 text-sm text-navy"
            >
              <input
                type="radio"
                name="agent"
                className="size-4 accent-eggplant"
                checked={runtime === kind}
                onChange={() => {
                  setRuntime(kind);
                  setConsent(false); // consent is given for one agent, not carried over
                }}
              />
              {AGENTS[kind].label}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="block space-y-1">
        <span className={KICKER}>Dépôt</span>
        <select
          className={FIELD}
          value={repoId}
          onChange={(event) => setRepoId(event.target.value)}
        >
          {repos.map((repo) => (
            <option key={repo.id} value={repo.id}>
              {repo.name}
            </option>
          ))}
        </select>
      </label>
      <label className="block space-y-1">
        <span className={KICKER}>Tâche pour l&apos;agent</span>
        <textarea
          className={cn(FIELD, "min-h-28 font-sans")}
          value={task}
          maxLength={MAX_TASK}
          onChange={(event) => setTask(event.target.value)}
          placeholder="Ex. : Ajoute une fonction multiply(a, b) et son test."
        />
      </label>
      <label className="flex items-start gap-3 text-sm text-navy/85">
        <input
          type="checkbox"
          className="mt-1 size-4 accent-eggplant"
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
        />
        <span>{AGENTS[runtime].consent}</span>
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className={PRIMARY} disabled={!ready}>
          {AGENTS[runtime].action}
        </button>
        {start.error ? <StartError error={start.error} /> : null}
      </div>
    </form>
  );
}

// Codex keeps its own login: NFactory only points to the official command (spec §6.4).
function StartError({ error }: { error: Error }) {
  const needsLogin = error instanceof ApiError && error.code === "needs_login";
  return (
    <div role="alert" className={cn(ALERT, "basis-full space-y-2")}>
      {needsLogin ? (
        <p className="font-medium">
          <span aria-hidden>! </span>Connexion requise
        </p>
      ) : null}
      <p>{error.message}</p>
      {needsLogin ? (
        <p>
          Dans un terminal :{" "}
          <code className="bg-navy/6 px-1.5 py-0.5 font-mono text-[13px]">
            codex login
          </code>
          , puis vérifiez l&apos;état dans{" "}
          <Link href="/providers" className="underline">
            Moteurs IA
          </Link>
          .
        </p>
      ) : null}
    </div>
  );
}

function StatusTag({ status }: { status: string }) {
  const state = describeTaskStatus(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wider",
        TONE_CLASSES[state.tone],
      )}
    >
      <span aria-hidden>{state.glyph}</span>
      {state.label}
    </span>
  );
}

// The user runs the official `claude` themselves; the bridge only prints how (spec §6.5).
function HandoffSteps({
  task,
  onCollect,
  busy,
}: {
  task: AgentTask;
  onCollect: () => void;
  busy: boolean;
}) {
  return (
    <div className="space-y-3 border-l-4 border-butter pl-4 text-sm text-navy/85">
      <p>
        1. Dans un terminal, depuis le dossier NFactory, affichez la copie de
        travail et la commande à lancer :
      </p>
      <code className="block bg-navy/6 px-3 py-2 font-mono text-[13px]">
        {`./scripts/bridge.ps1 -Handoff ${task.id}`}
      </code>
      <p>
        2. Lancez Claude Code vous-même avec cette commande, et laissez-le
        travailler.
      </p>
      <p>
        3. Quand il a terminé, importez ses changements : NFactory affichera le
        diff.
      </p>
      <button
        type="button"
        className={PRIMARY}
        onClick={onCollect}
        disabled={busy}
      >
        Importer les changements
      </button>
    </div>
  );
}

function TaskView({ task, pollMs }: { task: AgentTask; pollMs: number }) {
  const action = useAgentTaskAction();
  const active = isTaskActive(task.status);
  return (
    <section aria-labelledby="agent-task-title" className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="agent-task-title" className="font-display text-2xl text-navy">
          {AGENTS[task.runtime]?.title ?? "Tâche"}
        </h2>
        <StatusTag status={task.status} />
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-navy/60">Dépôt</dt>
        <dd className="font-mono text-navy">{task.repo_id}</dd>
        <dt className="text-navy/60">Branche</dt>
        <dd className="font-mono text-navy">{task.branch}</dd>
      </dl>
      {task.error ? (
        <div role="alert" className={ALERT}>
          {task.error}
        </div>
      ) : null}

      {task.status === "awaiting_user" ? (
        <HandoffSteps
          task={task}
          busy={action.isPending}
          onCollect={() => action.mutate({ id: task.id, action: "collect" })}
        />
      ) : null}

      {task.events.length || active ? (
        <div className="space-y-2">
          <h3 className={KICKER}>Ce que fait l&apos;agent</h3>
          <ol
            aria-label="Événements de l'agent"
            className="space-y-2 border-l-2 border-navy/15 pl-4"
          >
            {visibleEvents(task.events).map((event, index) => {
              const line = describeAgentEvent(event);
              return (
                <li key={index} className="text-sm">
                  <span aria-hidden className="mr-2 font-mono text-navy/60">
                    {line.glyph}
                  </span>
                  <span className="mr-2 font-mono text-[11px] uppercase tracking-wider text-navy/60">
                    {line.label}
                  </span>
                  <span
                    className={cn(
                      "text-navy",
                      event.type === "command" && "font-mono text-[13px]",
                    )}
                  >
                    {line.text}
                  </span>
                  {line.detail ? (
                    <span className="ml-2 font-mono text-xs text-navy/60">
                      {line.detail}
                    </span>
                  ) : null}
                </li>
              );
            })}
            {active ? <li className="text-sm text-navy/60">…</li> : null}
          </ol>
        </div>
      ) : null}

      {task.manifest.length ? (
        <div className="space-y-2">
          <h3 className={KICKER}>Fichiers changés</h3>
          <ul aria-label="Fichiers changés" className="space-y-1 text-sm">
            {task.manifest.map((entry) => (
              <li key={entry.path} className="flex gap-3">
                <span className="font-mono text-navy">{entry.path}</span>
                <span className="text-navy/60">
                  {CHANGE_LABELS[entry.change] ?? entry.change}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {task.diff ? (
        <div className="space-y-2">
          <h3 className={KICKER}>Diff</h3>
          <DiffView diff={task.diff} truncated={task.diff_truncated} />
        </div>
      ) : null}

      {isTaskCheckable(task.status) ? (
        <AgentCheckPanel taskId={task.id} pollMs={pollMs} />
      ) : null}

      <div className="flex flex-wrap gap-3">
        {active ? (
          <button
            type="button"
            className={SECONDARY}
            onClick={() => action.mutate({ id: task.id, action: "cancel" })}
            disabled={action.isPending}
          >
            Arrêter l&apos;agent
          </button>
        ) : null}
        {!active && task.status !== "discarded" ? (
          <button
            type="button"
            className={DANGER}
            onClick={() => action.mutate({ id: task.id, action: "discard" })}
            disabled={action.isPending}
          >
            Abandonner les changements
          </button>
        ) : null}
      </div>
      {action.error ? (
        <div role="alert" className={ALERT}>
          {action.error.message}
        </div>
      ) : null}
    </section>
  );
}

function CurrentTask({ id, pollMs }: { id: string; pollMs: number }) {
  const task = useAgentTask(id, pollMs);
  if (task.error)
    return (
      <div role="alert" className={ALERT}>
        {task.error.message}
      </div>
    );
  if (!task.data)
    return (
      <Skeleton
        className="h-40 bg-navy/8"
        aria-label="Chargement de la tâche"
      />
    );
  return <TaskView task={task.data} pollMs={pollMs} />;
}

export function AgentTasks({ pollMs = 2000 }: { pollMs?: number }) {
  const repos = useLocalRepos();
  const [taskId, setTaskId] = useState<string | null>(null);

  if (repos.error) {
    const needsBridge =
      repos.error instanceof ApiError && repos.error.code.startsWith("bridge_");
    return (
      <div role="alert" className={ALERT}>
        {repos.error.message}
        {needsBridge ? (
          <>
            {" "}
            Voir{" "}
            <Link href="/providers" className="underline">
              Moteurs IA
            </Link>
            .
          </>
        ) : null}
      </div>
    );
  }
  if (!repos.data)
    return (
      <Skeleton className="h-40 bg-navy/8" aria-label="Chargement des dépôts" />
    );
  if (!repos.data.repos.length) {
    return (
      <div className="space-y-2 border-l-4 border-eggplant/40 pl-4 text-sm text-navy/80">
        <p>
          Aucun dépôt autorisé sur ce poste. Autorisez-en un depuis votre
          terminal :
        </p>
        <code className="block bg-navy/6 px-3 py-2 font-mono text-[13px]">
          ./scripts/bridge.ps1 -Allow C:\chemin\vers\mon-depot
        </code>
        <p>
          NFactory ne connaît que le nom du dépôt, jamais un chemin choisi
          depuis le navigateur.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-10">
      <TaskForm repos={repos.data.repos} onStarted={setTaskId} />
      {taskId ? <CurrentTask id={taskId} pollMs={pollMs} /> : null}
    </div>
  );
}
