import { MY_DATA_URL } from "@/lib/api/members";

// GDPR art. 15 and 20 (ADR-0015): a plain link, so the browser saves the JSON file itself.
export function MyData() {
  return (
    <div className="space-y-3">
      <p className="max-w-2xl text-navy/70">
        Votre profil, vos espaces et rôles, vos sessions (dates seulement), vos actions du journal
        d&apos;audit et vos approbations, dans un fichier JSON. Les projets et runs appartiennent à
        l&apos;espace de travail, pas à un membre.
      </p>
      <a
        href={MY_DATA_URL}
        download
        className="inline-block border border-eggplant px-6 py-3 font-medium text-eggplant transition-colors hover:bg-eggplant hover:text-cream focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep"
      >
        <span aria-hidden>↓ </span>Télécharger mes données
      </a>
    </div>
  );
}
