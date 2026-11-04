# ADR-0014 — Marquage « généré par IA » des livrables

- Statut : accepté (2026-11-03)

## Contexte

L'article 50 de l'AI Act s'applique depuis le 2 août 2026 ; l'Omnibus ne l'a pas repoussé.
- 50(1) : la personne doit savoir qu'elle a affaire à une IA.
- 50(2) : les contenus générés, texte compris, doivent être marqués dans un format lisible par machine. Un système mis sur le marché avant le 2 août 2026 a jusqu'au **2 décembre 2026**.

On ne sait pas encore si du code et des documents générés à la demande relèvent de 50(2) : c'est une question pour l'avocat (`docs/legal/revue-france.md`, action 7). Le marquage coûte peu ; NFactory le fait donc dès maintenant (action 2).

## Décision

- **Un manifeste par livraison** : `.nfactory/provenance.json`, écrit par l'étape `package` et livré dans le ZIP. C'est le seul fichier de `.nfactory/` qui sort ; les rapports JUnit restent internes. Il contient :
  - `ai_generated: true` ;
  - `digital_source_type` : le terme IPTC `trainedAlgorithmicMedia`, vocabulaire standard des contenus générés par IA ;
  - `generator`, `notice` (la phrase française), `run_id`, `project_type`, `recipe` ;
  - `engines` : le fournisseur et le modèle de chaque rôle d'agent, avec `demo` ;
  - `files` : le sha256 de chaque fichier livré.
  - **Pas d'horodatage.** Le même workspace donne toujours le même ZIP, octet pour octet ; le `run_id` renvoie à la date enregistrée du run. Le manifeste ne contient aucun secret : rien que des noms de fournisseurs et de modèles.
- **Dans les fichiers eux-mêmes**, pour un livrable téléchargé seul :
  - `.xlsx` : `creator` « NFactory (IA) », `keywords` « généré par IA; NFactory », `description` = la phrase ;
  - `.docx` : `author`, `keywords`, `comments` sur le même modèle.
  - C'est le script généré qui pose ces propriétés : il les repose quand l'utilisateur le relance. Son propre test le vérifie, dans le sandbox, à chaque run.
- **Pour une personne qui lit** : la phrase est dans chaque `README.md`, en tête d'`EXPLICATION.md` et dans la section `.NOTES` de l'aide du script PowerShell.
- **Dans le dashboard (50(1))** : une note près du bouton « Lancer la fabrication » (la demande est traitée par des agents d'IA) et au-dessus des livrables (ils sont générés par IA ; nom du manifeste).
- **Une seule source pour la phrase** : `AI_NOTICE` dans `nfactory_worker.artifacts`. Les recettes l'injectent dans les scripts ; les README la portent en dur, et un test vérifie que chaque recette la contient.

## Non retenu

- **Un commentaire en tête de chaque fichier source.** Il casserait des formats sans commentaires (JSON, CSV) et des en-têtes contraints (BOM des `.ps1`, shebang). Le manifeste couvre déjà chaque fichier, par son empreinte.
- **Une signature C2PA.** Elle exigerait un certificat et une clé de signature à gérer ; le standard vise surtout les images et les vidéos. À revoir si l'avocat ou un acte d'exécution l'exige.
- **Un horodatage dans le manifeste** : il casserait la reproductibilité du ZIP.

## Conséquences

- Les tests : `tests/artifacts/test_provenance.py` (manifeste, ZIP), `tests/pipeline/test_pipeline.py` (le ZIP d'un vrai run contient le manifeste, chaque empreinte correspond ; l'explication s'ouvre sur la phrase), `tests/recipes/test_ai_marking.py` (README de chaque recette, aide PowerShell), les tests Excel et Word (propriétés du fichier construit), dashboard `artifact-list.test.tsx` et `new-project-form.test.tsx`.
- Une nouvelle recette doit porter la phrase dans son README : le test paramétré la refuse sinon.
