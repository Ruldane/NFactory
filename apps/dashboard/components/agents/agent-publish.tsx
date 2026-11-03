"use client";

// Publishing an agent's change to GitHub (tasks 4.6, 4.7). Its own approval, separate from
// launching the agent: a local commit, a push of the task's branch, a draft PR. Every
// status shown is read back from GitHub by the bridge; nothing here merges.

import { useState } from "react";

import {
  ALERT,
  FIELD,
  KICKER,
  PRIMARY,
  SECONDARY,
} from "@/components/ui/form-styles";
import {
  useLocalRepos,
  usePublishTask,
  useVerifyPublication,
} from "@/lib/api/agent-tasks";
import type { AgentTask, Publication } from "@/lib/api/types";
import { publicationFacts } from "@/lib/agent-task-status";

function Facts({ publication }: { publication: Publication }) {
  return (
    <ol aria-label="Statut de la publication" className="space-y-1 text-sm">
      {publicationFacts(publication.state).map((fact) => (
        <li
          key={fact.key}
          data-done={fact.done}
          className="flex items-center gap-2"
        >
          <span
            aria-hidden
            className={fact.done ? "text-forest" : "text-navy/40"}
          >
            {fact.done ? "✓" : "○"}
          </span>
          <span className={fact.done ? "text-navy" : "text-navy/60"}>
            {fact.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Published({
  task,
  publication,
}: {
  task: AgentTask;
  publication: Publication;
}) {
  const verify = useVerifyPublication();
  return (
    <div className="space-y-3">
      <Facts publication={publication} />
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-navy/60">Commit</dt>
        <dd className="font-mono text-navy">
          {publication.commit.slice(0, 12)}
        </dd>
        {publication.pr ? (
          <>
            <dt className="text-navy/60">PR</dt>
            <dd>
              <a
                href={publication.pr.url}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-navy underline underline-offset-4"
              >
                PR #{publication.pr.number}
                {publication.pr.draft ? " (brouillon)" : ""}
              </a>
            </dd>
          </>
        ) : null}
      </dl>
      <p className="text-xs text-navy/60">
        Vérifié sur GitHub le{" "}
        {new Date(publication.verified_at * 1000).toLocaleString("fr-FR")}. La
        fusion reste une décision humaine, sur GitHub.
      </p>
      <button
        type="button"
        className={SECONDARY}
        disabled={verify.isPending}
        onClick={() => verify.mutate(task.id)}
      >
        Vérifier sur GitHub
      </button>
      {verify.error ? (
        <div role="alert" className={ALERT}>
          {verify.error.message}
        </div>
      ) : null}
    </div>
  );
}

function ApprovalForm({ task, github }: { task: AgentTask; github: string }) {
  const publish = usePublishTask();
  const [title, setTitle] = useState("");
  const [approved, setApproved] = useState(false);
  const ready = approved && title.trim().length > 0 && !publish.isPending;
  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) publish.mutate({ id: task.id, title: title.trim() });
      }}
    >
      <label className="block space-y-1 text-sm">
        <span className="text-navy/70">Titre de la PR</span>
        <input
          className={FIELD}
          value={title}
          maxLength={200}
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-1"
          checked={approved}
          onChange={(event) => setApproved(event.target.checked)}
        />
        <span>
          J&apos;approuve : NFactory commite le changement sur{" "}
          <span className="font-mono">{task.branch}</span>, pousse cette branche
          seule vers <span className="font-mono">github.com/{github}</span> et
          ouvre une PR brouillon. Aucun merge, aucun push forcé.
        </span>
      </label>
      <button type="submit" className={PRIMARY} disabled={!ready}>
        Pousser et ouvrir la PR brouillon
      </button>
      {publish.error ? (
        <div role="alert" className={ALERT}>
          {publish.error.message}
        </div>
      ) : null}
    </form>
  );
}

export function AgentPublishPanel({ task }: { task: AgentTask }) {
  const repos = useLocalRepos();
  const repo = repos.data?.repos.find((item) => item.id === task.repo_id);
  return (
    <section
      aria-label="Publication sur GitHub"
      className="space-y-3 border border-navy/15 bg-cream/60 p-5"
    >
      <h3 className={KICKER}>Publication sur GitHub</h3>
      {task.publication ? (
        <Published task={task} publication={task.publication} />
      ) : repo?.github ? (
        <ApprovalForm task={task} github={repo.github} />
      ) : (
        <div className="space-y-2 text-sm text-navy/80">
          <p>
            Ce dépôt n&apos;est pas autorisé à la publication. Pour
            l&apos;autoriser vers son remote GitHub « origin », lancez dans un
            terminal :
          </p>
          <code className="block bg-navy/6 px-3 py-2 font-mono text-[13px]">
            ./scripts/bridge.ps1 -AllowPush {task.repo_id}
          </code>
        </div>
      )}
    </section>
  );
}
