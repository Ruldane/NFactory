"use client";

import { useState } from "react";

const QUIET =
  "border border-coral-deep/50 px-3 py-1.5 text-sm text-coral-deep transition-colors hover:bg-coral-deep/8 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep disabled:opacity-45";
const LOUD =
  "bg-coral-deep px-3 py-1.5 text-sm font-medium text-cream transition-colors hover:bg-eggplant focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep disabled:opacity-45";

interface ConfirmButtonProps {
  label: string;
  confirmLabel: string;
  warning: string; // what will be lost, shown before the second click
  onConfirm: () => void;
  pending?: boolean;
  ariaLabel?: string;
}

// An irreversible action takes two clicks, in the page itself: browser dialogs are avoided.
export function ConfirmButton({ label, confirmLabel, warning, onConfirm, pending, ariaLabel }: ConfirmButtonProps) {
  const [asking, setAsking] = useState(false);

  if (!asking) {
    return (
      <button type="button" aria-label={ariaLabel} onClick={() => setAsking(true)} className={QUIET}>
        {label}
      </button>
    );
  }
  return (
    <div className="space-y-2">
      <p className="text-sm text-coral-deep">
        <span aria-hidden>⚠ </span>
        {warning}
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={pending}
          onClick={() => {
            onConfirm();
            setAsking(false);
          }}
          className={LOUD}
        >
          {confirmLabel}
        </button>
        <button type="button" onClick={() => setAsking(false)} className="px-3 py-1.5 text-sm text-navy/70 hover:text-navy">
          Annuler
        </button>
      </div>
    </div>
  );
}
