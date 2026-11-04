"use client";

import { useState } from "react";

import { ConfirmButton } from "@/components/ui/confirm-button";
import { can, useMe } from "@/lib/api/access";
import { useEraseMember, useMembers } from "@/lib/api/members";

const KICKER = "font-mono text-[11px] uppercase tracking-[0.2em] text-navy/60";

// Owners and admins only (ADR-0015): erasing removes the member from this workspace, and
// anonymises them when they belong to no other one.
export function MembersSection() {
  const me = useMe();
  const allowed = can(me.data, "configure");
  const members = useMembers(allowed);
  const erase = useEraseMember();
  // Kept at click time: once erased, the member may leave the refreshed list.
  const [erasedName, setErasedName] = useState("");

  if (!allowed) return null;

  return (
    <section className="space-y-4">
      <h2 className="font-display text-2xl text-navy">Membres</h2>
      <p className="max-w-2xl text-sm text-navy/70">
        Effacer un membre le retire de cet espace et ferme ses sessions. S&apos;il n&apos;appartient à
        aucun autre espace, son nom et son e-mail sont supprimés ; le journal d&apos;audit garde ses
        actions sous un identifiant anonyme. Retirez-le aussi de la liste d&apos;admission SSO, sinon il
        pourra revenir comme nouveau membre.
      </p>
      {members.error || erase.error ? (
        <div role="alert" className="border-l-4 border-coral-deep bg-coral-deep/8 px-5 py-4 text-sm">
          {(members.error ?? erase.error)?.message}
        </div>
      ) : null}
      {erase.data ? (
        <p role="status" className="text-sm text-forest">
          ✓ {erasedName} a été effacé
          {erase.data.anonymised ? " et anonymisé." : " de cet espace (il reste membre d'un autre espace)."}
        </p>
      ) : null}
      <ul className="divide-y divide-navy/10 border border-navy/10">
        {(members.data?.items ?? []).map((member) => (
          <li key={member.user_id} className="flex flex-wrap items-start justify-between gap-4 bg-cream px-5 py-4">
            <div>
              <p className="font-medium text-navy">{member.display_name}</p>
              <p className="font-mono text-xs text-navy/60">{member.email ?? "—"}</p>
            </div>
            <div className="flex items-start gap-6">
              <span className={KICKER}>{member.role_label}</span>
              {member.is_owner ? (
                <span className="text-sm text-navy/60">Propriétaire de l&apos;espace : ne peut pas être effacé</span>
              ) : (
                <ConfirmButton
                  label="Effacer"
                  confirmLabel={`Oui, effacer ${member.display_name}`}
                  warning="Irréversible : son accès, ses sessions et son identité sont supprimés."
                  pending={erase.isPending}
                  onConfirm={() => {
                    setErasedName(member.display_name);
                    erase.mutate(member.user_id);
                  }}
                />
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
