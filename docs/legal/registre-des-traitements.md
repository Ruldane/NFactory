# Registre des traitements : modèle pour une organisation qui utilise NFactory

> **Brouillon à faire relire par un avocat** (revue juridique, action 6). Ce modèle suit l'article 30 du RGPD et le modèle de registre de la CNIL. Le registre appartient à l'organisation qui déploie NFactory (le responsable du traitement) : elle le complète, le tient à jour et le présente à la CNIL sur demande. Les crochets `[…]` sont à remplir.

**Responsable du traitement** : [nom de l'organisation], [adresse], [représentant légal].
**Délégué à la protection des données ou contact** : [nom, e-mail]. Ce contact s'affiche sur l'écran de connexion si `NFACTORY_PRIVACY_CONTACT` est rempli.
**Date de mise à jour** : [date].

## 1. Comptes et connexion

| Rubrique | Contenu |
|---|---|
| Finalité | Identifier les membres et sécuriser l'accès à l'espace NFactory |
| Base légale | Intérêt légitime (sécurité du système d'information), ou exécution du contrat de travail ou de prestation : [à choisir] |
| Personnes concernées | Membres de l'espace : salariés, prestataires [à préciser] |
| Données | Nom, adresse e-mail vérifiée, identifiant Google (`sub`), rôle, dates de session. Le jeton de session n'est conservé que sous forme d'empreinte SHA-256 |
| Destinataires | Administrateurs de l'espace. Google, comme fournisseur d'identité |
| Transferts hors UE | Google : [selon le contrat Google Workspace ou Cloud de l'organisation] |
| Durée de conservation | Session : `NFACTORY_SESSION_TTL_HOURS` (12 h par défaut). Les sessions finies et les tentatives expirées sont supprimées chaque nuit. Le compte est gardé jusqu'à l'effacement du membre, qui anonymise son identité |
| Sécurité | Admission refusée par défaut (domaines et e-mails listés), protection CSRF, cookie de session strictement nécessaire, ports liés à 127.0.0.1 |

## 2. Journal d'audit

| Rubrique | Contenu |
|---|---|
| Finalité | Tracer les actions sensibles : approbations, réglages, moteurs IA, publication, connexions, effacements |
| Base légale | Intérêt légitime (sécurité, preuve) |
| Personnes concernées | Membres de l'espace |
| Données | Identifiant de l'auteur, action, date, détails sans secret |
| Destinataires | Rôles ayant la permission « audit » |
| Transferts hors UE | Aucun : la base reste chez l'organisation |
| Durée de conservation | Durée choisie dans Réglages → Conservation des données (30 à 3650 jours ; la CNIL recommande 6 mois à 1 an). Sans choix, rien n'est supprimé : [durée à fixer] |
| Sécurité | Lecture réservée par rôle, entrées cloisonnées par espace de travail |

## 3. Production de livrables (runs)

| Rubrique | Contenu |
|---|---|
| Finalité | Transformer la demande d'un membre en livrable testé : code, classeur, document |
| Base légale | [Intérêt légitime ou exécution d'un contrat, selon l'usage] |
| Personnes concernées | Membres. Toute personne citée dans une demande ou un document : [à évaluer] |
| Données | Texte de la demande, livrables, événements du run. Données personnelles éventuelles saisies par les membres : [consigne interne à donner] |
| Destinataires | Membres de l'espace. Les moteurs IA choisis dans Moteurs IA, comme sous-traitants |
| Transferts hors UE | Selon les moteurs choisis. Moteurs IA affiche le pays de traitement de chacun (ADR-0016). La politique « UE ou local uniquement » refuse tout moteur hors UE ou non documenté. [Moteurs retenus, pays, garanties : décision d'adéquation, clauses types, DPA] |
| Durée de conservation | Réglages → Conservation des données : runs terminés supprimés après N jours (7 à 3650), avec leurs fichiers et points de reprise. Sans choix : [durée à fixer] |
| Sécurité | Code généré exécuté dans un sandbox sans réseau, secrets chiffrés, recherche de secrets avant livraison, marquage « généré par IA » |

## 4. Base de connaissances

| Rubrique | Contenu |
|---|---|
| Finalité | Donner aux agents les documents internes utiles (README, procédures, conventions), avec leurs citations |
| Base légale | Intérêt légitime |
| Personnes concernées | Toute personne citée dans les documents importés |
| Données | Texte des documents, découpé en extraits, et leurs empreintes vectorielles |
| Destinataires | Membres du projet. Le moteur d'embeddings choisi, si ce n'est pas l'empreinte locale (par défaut) |
| Transferts hors UE | Aucun avec l'empreinte locale. Sinon, selon le moteur (voir le §3) |
| Durée de conservation | Jusqu'à la suppression du document ou du projet |
| Sécurité | Documents traités comme non fiables : ils ne changent aucune permission |
| AIPD | **À évaluer** si les documents contiennent des données de salariés en grand nombre ou des données sensibles |

## 5. Agents de code sur un dépôt (Codex, Claude Code)

| Rubrique | Contenu |
|---|---|
| Finalité | Faire modifier un dépôt autorisé par l'agent de code du membre |
| Base légale | Intérêt légitime |
| Données | Code du dépôt et texte de la tâche ; données personnelles seulement si le dépôt en contient |
| Destinataires | OpenAI (Codex) ou Anthropic (Claude Code), sous le compte du membre ; GitHub en cas de publication approuvée |
| Transferts hors UE | États-Unis. Refusé si la politique « UE ou local uniquement » est active |
| Durée de conservation | Selon le contrat du membre avec l'éditeur. Le worktree local reste sous le contrôle du membre |
| Sécurité | Consentement à chaque tâche, dépôts sur liste blanche, aucune publication sans seconde approbation |

## Sous-traitants à lister

| Sous-traitant | Rôle | Pays | Garanties |
|---|---|---|---|
| [Google] | Fournisseur d'identité | [ ] | [ ] |
| [Moteur IA retenu] | Modèle de langage | Voir Moteurs IA | [DPA, certification DPF, clauses types : **à vérifier**] |
| [Hébergeur, si NFactory n'est pas installé dans vos locaux] | Hébergement | [ ] | [ ] |
