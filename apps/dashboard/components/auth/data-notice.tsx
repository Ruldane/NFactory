// What the sign-in screen tells a visitor about their data (GDPR art. 13, legal review §2).
// The data controller is the organisation that runs this space, not NFactory's authors.

import { useId } from "react";

const CNIL_COMPLAINT = "https://www.cnil.fr/fr/adresser-une-plainte";

export function DataNotice({
  provider,
  sessionHours,
  contact,
}: {
  provider: string;
  sessionHours: number | null;
  contact: string | null;
}) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      className="mt-8 space-y-2 border-t border-navy/15 pt-6 text-sm text-navy/75"
    >
      <h2 id={headingId} className="font-mono text-[11px] uppercase tracking-[0.2em] text-navy">
        Vos données
      </h2>
      <p>
        {provider} transmet votre nom, votre adresse e-mail vérifiée et votre identifiant {provider},
        pour vous connecter et garder la trace de vos actions sensibles dans le journal d&apos;audit
        (sécurité de l&apos;espace).
      </p>
      <p>
        {sessionHours ? `La session dure ${sessionHours} h. ` : null}
        Un seul cookie, strictement nécessaire à la session, sans traceur. Le journal d&apos;audit
        est gardé pendant la durée choisie par l&apos;administrateur de l&apos;espace.
      </p>
      <p>
        Le responsable du traitement est l&apos;organisation qui administre cet espace. Vous pouvez
        télécharger vos données dans Réglages, et demander leur effacement ou leur correction à{" "}
        {contact ? (
          <span className="font-medium text-navy">{contact}</span>
        ) : (
          "l'administrateur de cet espace"
        )}
        . Vous pouvez aussi saisir la{" "}
        <a
          href={CNIL_COMPLAINT}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2 hover:text-coral-deep"
        >
          CNIL
        </a>
        .
      </p>
    </section>
  );
}
