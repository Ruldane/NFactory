"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useRef, useState } from "react";

import { ALERT, FIELD, KICKER, PRIMARY } from "@/components/ui/form-styles";
import { useRequestChange } from "@/lib/api/queries";
import type { RunDetail } from "@/lib/api/types";

// Scenario E: ask for a change on a delivered run. The child run starts from what was
// delivered, rebuilds, is tested again, and shows its diff.
export function ChangeRequest({ run }: { run: RunDetail }) {
  const router = useRouter();
  const change = useRequestChange(run);
  const [request, setRequest] = useState("");
  // Made on the first submit, then kept: a retry after a network error reuses it.
  const idempotencyKey = useRef<string | null>(null);
  const ready = request.trim() !== "" && !change.isPending;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!ready) return;
    idempotencyKey.current ??= crypto.randomUUID();
    change.mutate(
      { request: request.trim(), idempotencyKey: idempotencyKey.current },
      { onSuccess: (child) => router.push(`/runs/${child.id}`) },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3 border-t border-navy/15 pt-6">
      <label className="block space-y-2">
        <span className={KICKER}>Évolution demandée</span>
        <textarea
          value={request}
          onChange={(e) => {
            setRequest(e.target.value);
            idempotencyKey.current = null;
          }}
          rows={3}
          maxLength={20_000}
          placeholder="Ex. : ajoute un filtre par département."
          className={`${FIELD} resize-y font-sans`}
        />
      </label>
      <p className="text-xs text-navy/60">
        Le projet livré sert de point de départ : seul ce qui change est refait, puis tout est
        retesté. Les modifications s&apos;affichent sous forme de diff.
      </p>
      {change.error ? (
        <p role="alert" className={ALERT}>
          {change.error.message}
        </p>
      ) : null}
      <button type="submit" disabled={!ready} className={PRIMARY}>
        {change.isPending ? "Lancement…" : "Lancer l'évolution"}
      </button>
    </form>
  );
}
