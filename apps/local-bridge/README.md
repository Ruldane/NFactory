# local-bridge (phase 4)

Compagnon installé sur la machine de l'utilisateur pour détecter et piloter les outils locaux officiels (Codex CLI, Claude Code), avec son consentement.

Règles (spec §6.4, §6.5, §8.1) :
- écoute uniquement sur `127.0.0.1`, jeton d'appairage obligatoire ;
- n'expose jamais de shell brut ;
- ne lit jamais les fichiers d'authentification, cookies ou jetons des outils.

Pas encore implémenté : voir `IMPLEMENTATION_STATUS.md`, tâches 4.1 à 4.4.
