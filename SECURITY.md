# Politique de sécurité

## Versions suivies

NFactory n'a pas encore de version publiée. Seule la branche `main` reçoit les correctifs de sécurité.

## Signaler une vulnérabilité

N'ouvrez pas de ticket public. Utilisez le signalement privé de GitHub : onglet **Security** du dépôt, puis **Report a vulnerability**. Le signalement reste visible seulement de vous et du mainteneur.

Indiquez :
- le commit et le composant touché : API, worker, sandbox, pont local ou dashboard ;
- les étapes pour reproduire ;
- l'impact que vous constatez.

N'envoyez jamais un vrai secret, un jeton ou une donnée personnelle : remplacez-les par des valeurs factices.

## Ce qui se passe ensuite

1. Le mainteneur accuse réception et poursuit l'échange dans l'avis privé.
2. Le correctif arrive sur `main`, avec un test qui reproduit le problème.
3. L'avis est publié une fois le correctif disponible, avec votre nom si vous le souhaitez.

## Périmètre

Sont notamment des vulnérabilités :
- du code généré par un run qui sort du sandbox : accès au réseau, à un fichier hors de son espace de travail, au socket Docker ;
- un secret (clé de fournisseur, jeton du pont local, secret SSO) lisible dans une réponse de l'API, un événement, un journal ou un livrable ;
- l'accès aux données d'un autre espace de travail, ou une action permise à un rôle qui ne l'a pas ;
- une requête au pont local qui atteint un dépôt non autorisé, lance une commande arbitraire ou pousse sans approbation ;
- un document de la base de connaissances qui change les permissions d'un run (injection de prompt).

Le code d'un livrable n'est pas fiable par conception : un défaut dans un projet généré n'est une vulnérabilité de NFactory que s'il franchit l'une de ces limites. Une faille d'une dépendance se signale d'abord à son projet ; dites-nous si NFactory l'expose.

## Composants tiers

À chaque push, la CI produit l'artefact `supply-chain` :
- les SBOM CycloneDX de l'environnement Python, du dashboard et des outils web du sandbox ;
- `THIRD_PARTY_NOTICES.md`, la liste des composants avec leur licence et leurs textes de licence.

Le job échoue si un composant n'est disponible que sous une licence à copyleft fort (GPL, AGPL, SSPL).
