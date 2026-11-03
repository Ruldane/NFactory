# ADR-0007 — Base de connaissances : ingestion, vecteurs versionnés, recherche hybride

- Statut : accepté (2026-11-02)

## Contexte
La phase 3 ajoute la base de connaissances (spec §7, F10). Un utilisateur importe des documents ; les agents s'en servent pendant un run et citent leurs sources. Les tables `documents` et `document_chunks` existent depuis la phase 0 (pgvector, colonne `tsvector`).

## Décision
- **Emplacement.** Le module `nfactory_core.knowledge` est partagé : l'API ingère et cherche, le worker calcule les vecteurs et cherche pendant un run.
- **Ingestion synchrone, vecteurs en arrière-plan.**
  - L'API extrait le texte, le découpe et l'enregistre pendant l'envoi du fichier : la recherche plein texte marche dès la réponse.
  - Les vecteurs sont calculés par le job ARQ `index_knowledge`, relancé aussi chaque minute par le worker pour rattraper un envoi manqué.
- **Formats.** Markdown, texte, code, PDF (`pypdf`) et Word (`python-docx`).
  - Taille limitée à 10 Mo. Le PDF est limité en pages. Le `.docx` est refusé si son contenu décompressé est démesuré (bombe zip).
  - Le texte extrait est conservé (`documents.content`) : une citation pointe vers une ligne de ce texte.
- **Déduplication.** Un fichier identique (sha256) déjà présent dans le même périmètre n'est pas réindexé. Un même chemin au contenu différent remplace l'ancienne révision.
- **Découpage.**
  - Documents : par section (titres Markdown, titres Word), en fenêtres bornées avec 2 lignes de chevauchement.
  - Python : par fonction et classe (`ast`). Autres langages : par bloc, avec le symbole détecté.
  - Chaque morceau garde sa ligne de début et de fin, sa section ou son symbole, et sa page pour un PDF.
- **Vecteurs indépendants du modèle de génération.**
  - Le moteur d'embeddings est choisi par espace de travail : OpenAI, endpoint compatible OpenAI, Ollama, ou l'**empreinte locale**. L'empreinte locale est un hachage lexical sans modèle et sans réseau, honnête mais moins fine qu'un vrai modèle.
  - Par défaut, c'est l'empreinte locale : rien ne part vers un service externe sans configuration.
  - Un fournisseur distant est refusé en mode « local uniquement ». Une panne d'embeddings n'est jamais remplacée en silence par un autre moteur.
- **Index versionné.** Chaque vecteur porte son moteur (`embedding_model`) et sa dimension. La recherche ne compare que les vecteurs du moteur actif. Changer de moteur relance l'indexation ; tant qu'elle n'est pas finie, les morceaux non recalculés restent trouvables par le plein texte, jamais par un vecteur d'un autre moteur.
- **Recherche hybride.**
  - Les droits sont appliqués d'abord, dans la requête SQL : espace de travail, puis documents du projet ou de tout l'espace.
  - Ensuite plein texte (`websearch_to_tsquery`, configuration `simple`) et vecteur (distance cosinus), fusionnés par RRF (k = 60).
  - Chaque résultat est une citation : document, chemin, lignes, section, extrait.
- **Contenu non fiable.** Un passage récupéré est donné à un agent comme une donnée, dans une balise dont les délimiteurs sont neutralisés, avec la consigne de ne jamais suivre ses instructions. Les permissions ne dépendent pas des agents : commandes venues des recettes seulement, budget figé au lancement, sandbox sans réseau.

## Conséquences
- La recherche vectorielle est exacte (pas d'index ANN) : suffisant pour un poste local. Un index HNSW partiel par moteur viendra quand le volume le demandera.
- L'empreinte locale ne comprend pas les synonymes. Pour une recherche sémantique, il faut un vrai modèle d'embeddings (Ollama local ou fournisseur).
- Les fournisseurs dont l'API d'embeddings n'est pas vérifiée dans la documentation officielle ne sont pas proposés.
