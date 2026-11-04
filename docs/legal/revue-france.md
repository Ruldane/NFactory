# Revue juridique préalable — France / UE (2026-11-03)

> Ce document est une **revue préparatoire faite par un agent**, pas un avis juridique. Il sert à préparer l'échange avec un avocat (droit du numérique / données personnelles) avant toute distribution commerciale. Chaque point « à vérifier » doit être confirmé par un professionnel.

## 1. Situation de départ

- NFactory est un logiciel **auto-hébergé** : toute la pile tourne sur le poste de l'utilisateur, ports liés à `127.0.0.1`. **Aucun déploiement en ligne n'est prévu pour l'instant** (décision de l'utilisateur, 2026-11-03).
- Le code est **public** sur `Ruldane/NFactory`, **sans fichier de licence**.
- Rôles RGPD probables :
  - L'entreprise qui installe NFactory et y met ses données est **responsable de traitement**.
  - L'éditeur (vous) n'est qu'**éditeur de logiciel** tant qu'il n'héberge rien.
  - Une offre hébergée ferait de l'éditeur un **sous-traitant** (art. 28 RGPD), avec un contrat (DPA) à prévoir.
- Les modèles d'IA sont ceux de fournisseurs tiers (OpenAI, Anthropic, Mistral, Ollama local…). NFactory **ne fournit pas de modèle**.

## 2. Données personnelles (RGPD, loi Informatique et Libertés)

**Données traitées**

| Donnée | Où | Remarque |
|---|---|---|
| Identité des membres (aujourd'hui « Moi (local) » ; avec le SSO : e-mail, nom, identifiant Google `sub`) | `users`, `memberships` | Minimum nécessaire : ne pas stocker la photo ni d'autres données Google |
| Journal d'audit (qui a fait quoi) | `audit_log` | Intérêt légitime / sécurité ; durée de conservation à fixer |
| Demandes, briefs, documents de la base de connaissances, fichiers générés | `runs`, `knowledge`, artefacts | Peuvent contenir des données personnelles saisies par l'utilisateur |
| Traces et événements | `events`, OTel local | Déjà rédigés (secrets masqués) |

**Ce qui est déjà en place**

- Mode local par défaut.
- Pas de télémétrie externe, pas de traceur ni de cookie publicitaire.
- Polices auto-hébergées : aucun appel à Google depuis le navigateur.
- Secrets chiffrés (Fernet) et redaction des événements.
- Aucun envoi à un fournisseur externe sans choix explicite (pas de repli silencieux).

**Manques à combler (actions techniques)**

1. **Politique de rétention** : durées configurables par espace de travail, avec purge des runs, événements, documents et entrées d'audit anciennes. *Fait (ADR-0015) : runs terminés et journal d'audit, purge chaque nuit ; rien n'est supprimé tant que le propriétaire n'a pas choisi de durée.*
2. **Droits des personnes** :
   - export et effacement des données d'un membre ;
   - suppression d'un projet avec ses artefacts et ses vecteurs.
   - *Fait (ADR-0015) : export JSON par le membre, effacement (anonymisation) par un administrateur, suppression d'un projet.*
3. **Information** : un texte court sur l'écran de connexion SSO (quelles données, pourquoi, combien de temps).
4. **Modèle de registre des traitements** et, si la base de connaissances contient des données de salariés ou sensibles, une **AIPD**. Ces deux documents sont à fournir au client ; c'est le client qui les tient.

**Transferts hors UE**

- Choisir un moteur américain (OpenAI, Anthropic) envoie le contenu des demandes aux États-Unis.
- Le **Data Privacy Framework UE–États-Unis** reste en vigueur. Le Tribunal de l'UE l'a validé le 3 septembre 2025 (T-553/23, *Latombe*). Le pourvoi **C-703/25 P** est pendant devant la Cour de justice, sans arrêt connu à ce jour.
- Risque : une invalidation (comme Schrems II en 2020) obligerait à basculer sur des clauses contractuelles types et une analyse d'impact des transferts.
- Fournisseurs chinois (spec §6.6) : aucune décision d'adéquation. Ils exigent clauses types + analyse d'impact, et sont à déconseiller pour des données personnelles.
- Actions :
  - afficher, dans Moteurs IA, le pays de traitement de chaque fournisseur ;
  - proposer un réglage « données personnelles : moteurs UE ou locaux uniquement » (lié à la phase 6 « politiques provider par workspace ») ;
  - **à vérifier** : la certification DPF et les DPA de chaque fournisseur utilisé.

Référence CNIL : recommandations sur le développement des systèmes d'IA, finalisées en juillet 2025, et note exploratoire sur l'IA agentique (juillet 2026). Elles portent surtout sur l'entraînement de modèles. NFactory n'entraîne aucun modèle, mais les fiches sur la sécurité et la minimisation s'appliquent.

## 3. Règlement européen sur l'IA (AI Act, règlement 2024/1689)

- **Statut de NFactory** : un système d'IA qui intègre des modèles à usage général de tiers. Ce n'est pas un fournisseur de modèle (les obligations « GPAI » ne s'appliquent pas). Ce n'est pas un système **à haut risque** tant qu'il n'est pas vendu pour un usage de l'annexe III (recrutement, crédit, etc.).
- **Omnibus numérique IA** (règlement 2026/1744, en vigueur depuis le 27 juillet 2026 selon plusieurs sources ; **à confirmer au Journal officiel**) :
  - obligations haut risque de l'annexe III repoussées au 2 décembre 2027 ;
  - obligations de l'annexe I repoussées au 2 août 2028.
- **Article 50 (transparence) : applicable depuis le 2 août 2026, non repoussé.**
  - 50(1) : informer la personne qu'elle interagit avec une IA. L'interface le dit déjà implicitement (« usine IA »). À rendre explicite sur l'écran d'accueil et dans les livrables.
  - 50(2) : marquer les contenus générés (texte compris) dans un format lisible par machine. Délai jusqu'au **2 décembre 2026** pour les systèmes mis sur le marché avant le 2 août 2026.
  - L'exemption open source de l'article 2(12) **ne couvre pas l'article 50**.
  - **À vérifier** : du code et des documents générés à la demande relèvent-ils de 50(2) ? Et la mise à disposition gratuite d'un dépôt vaut-elle « mise sur le marché » ?
  - Mesure prudente et peu coûteuse :
    - une métadonnée « généré par IA (NFactory) » dans chaque livrable (propriétés du `.docx` / `.xlsx`, en-tête des fichiers, manifeste `.nfactory/provenance.json`) ;
    - une mention dans le README généré.
- **Article 4 (maîtrise de l'IA)**, depuis février 2025 : cette obligation pèse sur l'entreprise qui déploie NFactory. Une courte documentation utilisateur l'y aide.
- Sanctions sur l'article 50 : jusqu'à 15 M€ ou 3 % du chiffre d'affaires mondial.

## 4. Cyber Resilience Act (règlement 2024/2847)

- **Champ** : il s'applique aux produits avec éléments numériques **mis à disposition dans le cadre d'une activité commerciale**. Un dépôt gratuit tenu par une personne, sans monétisation, en est très probablement **hors champ**. Une vente, un support payant ou une monétisation y feraient entrer NFactory. Un service purement hébergé (SaaS) en est largement exclu.
- **Calendrier** :
  - signalement des vulnérabilités activement exploitées sous 24 h depuis le **11 septembre 2026** (fabricants) ;
  - application complète le **11 décembre 2027**.
- À préparer dès maintenant, car c'est peu coûteux :
  - un `SECURITY.md` (canal de signalement des vulnérabilités) ;
  - une **SBOM** générée en CI (voir l'inventaire du §6) ;
  - des mises à jour de sécurité suivies.

## 5. Responsabilité du fait des produits

- La directive **2024/2853** inclut explicitement les **logiciels**. Transposition attendue au **9 décembre 2026**. La France n'avait pas encore de texte final aux dernières sources consultées : le barreau de Paris a commenté un projet en mars 2026.
- Les logiciels libres fournis **hors activité commerciale** sont exclus.
- En cas de vente :
  - prévoir des conditions générales ;
  - suivre les vulnérabilités, car l'absence de mise à jour de sécurité peut rendre un produit défectueux ;
  - **à vérifier** avec l'avocat : la responsabilité attachée au code *généré* livré au client.

## 6. Licences

**Code de NFactory.** Sans fichier `LICENSE`, le dépôt public est « tous droits réservés » : personne n'a le droit légal de l'utiliser ni de le modifier. **Décision à prendre par vous** :

| Choix | Effet |
|---|---|
| MIT / Apache-2.0 | Réutilisation libre, y compris commerciale par d'autres. Apache-2.0 ajoute une licence de brevets |
| AGPL-3.0 | Libre, mais toute offre hébergée dérivée doit publier son code |
| Propriétaire (ou dépôt privé) | Vous gardez le contrôle ; publication publique peu utile |

**Dépendances**, inventaire du 2026-11-03 tiré des métadonnées installées :

- Python (98 paquets) : aucune GPL ni AGPL.
  - `psycopg` est en **LGPL-3.0** : acceptable utilisé tel quel, mais joindre sa licence aux images Docker distribuées.
  - `certifi`, `pathspec` et `orjson` sont en **MPL-2.0** (copyleft par fichier, sans effet si on ne les modifie pas).
- Dashboard npm (722 paquets) : MIT 578, Apache-2.0 45, ISC 27, MPL-2.0 25, BSD 21, LGPL-3.0 14, CC-BY-4.0 1, autres permissives. Aucune GPL ni AGPL.
  - Le LGPL vient de `libvips` par `sharp`, qui optimise les images de Next ; même remarque que pour psycopg.
  - Le CC-BY-4.0 demande une attribution.
- Outils du sandbox (`web-deps`, 114 paquets) : MIT, Apache-2.0, MPL-2.0, BSD, ISC, CC0 et BlueOak. Aucune GPL ni AGPL.
- Polices Fraunces, Instrument Sans et JetBrains Mono : SIL OFL 1.1, libre usage. Conserver la licence en cas de redistribution.
- Action : générer une SBOM et un fichier `THIRD_PARTY_NOTICES` en CI.

**Code généré.** Les modèles de recettes (`*.tmpl`) sont à vous. Décidez sous quelle licence le code généré est remis au client ; le plus simple est une cession ou une licence libre sans restriction. Les conditions commerciales d'OpenAI et d'Anthropic attribuent les sorties à l'utilisateur (**à vérifier** dans la version en vigueur de chaque contrat).

## 7. Conditions des fournisseurs

- **Claude Code / abonnement Claude** (spec §6.5) : déjà respecté. NFactory ne lance jamais `claude` et ne relaie aucun jeton. Le mode « runtime piloté » reste désactivé tant que les conditions Anthropic ne l'autorisent pas explicitement.
- **Codex / ChatGPT** : NFactory utilise la connexion officielle de l'utilisateur et ne contourne aucun quota. À relire avant une offre commerciale.
- **Google (SSO)** :
  - seuls les scopes `openid email profile` sont demandés. Ce sont des scopes **non sensibles**, sans revue de sécurité Google ;
  - une application « Interne » à un Google Workspace ne passe pas par la vérification ;
  - une application « Externe » en production demande une page de confidentialité, un domaine vérifié et le respect de la *Google API Services User Data Policy* ;
  - suivre la charte du bouton « Se connecter avec Google ».
- **GitHub** : PR brouillon uniquement, avec l'accord de l'utilisateur. Rien de particulier.

## 8. Autres points français

- **Langue (loi Toubon)** : pour une offre commerciale en France, l'interface, la documentation et le contrat doivent être en français. L'interface l'est déjà ; le contrat et la documentation utilisateur sont à faire.
- **LCEN (mentions légales), cookies, CGU** : ils ne deviennent nécessaires qu'avec un site en ligne. Le cookie de session du SSO est « strictement nécessaire » au sens de la CNIL : pas de bandeau de consentement.
- **Marque** : vérifier la disponibilité de « NFactory » à l'INPI et à l'EUIPO avant un usage commercial.

## 9. Plan d'action proposé

| # | Action | Qui | Quand |
|---|---|---|---|
| 1 | Choisir la licence du dépôt et ajouter `LICENSE` | Vous | Avant d'inviter d'autres utilisateurs |
| 2 | Marquage « généré par IA » des livrables (manifeste + métadonnées) et mention IA dans l'interface | Agent (code, test d'abord) | Fait le 3 novembre 2026 (ADR-0014) |
| 3 | Politique de rétention + export/effacement par membre | Agent (phase 6) | Fait le 4 novembre 2026 (ADR-0015) |
| 4 | `SECURITY.md`, SBOM et `THIRD_PARTY_NOTICES` en CI | Agent | Phase 6 |
| 5 | Pays de traitement par fournisseur + option « UE ou local uniquement » | Agent (phase 6) | Phase 6 |
| 6 | Modèles de registre des traitements et d'information SSO | Agent (brouillon) puis avocat | Avant le premier client |
| 7 | Revue par un avocat : statut AI Act art. 50(2), CRA, responsabilité du code généré, CGU/CGV, DPA | Avocat | Avant toute vente |
| 8 | Recherche de marque INPI / EUIPO | Vous ou conseil en propriété industrielle | Avant usage commercial |

## Sources

- AI Act et Omnibus : [Gibson Dunn](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/), [Jones Walker](https://www.joneswalker.com/en/insights/blogs/ai-law-blog/yes-august-2-still-matters-the-eu-approved-a-high-risk-ai-delay-but-most-trans.html), [Usercentrics](https://usercentrics.com/knowledge-hub/eu-ai-act-high-risk-delay-article-50-transparency-consent/), [DLA Piper](https://knowledge.dlapiper.com/dlapiperknowledge/globalemploymentlatestdevelopments/2026/The-Digital-AI-Omnibus-Proposed-deferral-of-high-risk-AI-obligations-under-the-AI-Act).
- Data Privacy Framework : [WilmerHale](https://www.wilmerhale.com/en/insights/blogs/wilmerhale-privacy-and-cybersecurity-law/20251201-european-court-of-justice-to-review-challenge-to-eu-us-data-privacy-framework), [EDPL](https://edpl.lexxion.eu/article/EDPL/2026/1/15), [Berkeley Technology Law Journal](https://btlj.org/2026/02/third-times-the-charm-the-fate-of-the-eu-u-s-data-privacy-framework/).
- Cyber Resilience Act : [Goodwin](https://www.goodwinlaw.com/en/insights/publications/2026/09/alerts-lifesciences-technology-preparing-for-eu-cyber-resilience-act), [Noze — guide de la Commission](https://www.noze.it/en/insights/cra-commission-guidance/), [OpenSSF stewards](https://policy.openssf.org/CRA/stewards-one-pager.html).
- Responsabilité produits : [Barreau de Paris — rapport](https://www.avocatparis.org/sites/bdp/files/2026-03/RAPPORT%20DIRECTIVE%20PRODUITS%20DEFECTUEUX.pdf), [Question écrite n° 11448](https://www.assemblee-nationale.fr/dyn/17/questions/QANR5L17QE11448), [Stibbe](https://www.stibbe.com/fr/publications-and-insights/nouvelles-regles-de-lue-sur-la-responsabilite-du-fait-des-produits).
- CNIL : [finalisation des recommandations IA](https://cnil.fr/fr/ia-finalisation-recommandations-developpement-des-systemes-ia), [recommandations spécifiques](https://www.cnil.fr/fr/developpement-des-systemes-dia-les-recommandations-specifiques).
- Google : [OpenID Connect reference](https://developers.google.com/identity/openid-connect/reference), [Sensitive scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification).
