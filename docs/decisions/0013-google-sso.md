# ADR-0013 — Connexion SSO par OpenID Connect (Google d'abord)

- Statut : accepté (2026-11-03)

## Contexte

La spec (F34, phase 6) demande un SSO « OIDC/SAML selon fournisseur », ajouté après le MVP local. L'utilisateur a choisi **Google**. Depuis 5.4 (ADR-0011), l'API sait déjà qui appelle par une seule dépendance, `get_user_id`, et en tire les rôles. Il ne manque que l'authentification. Le mode local doit rester tel quel : un seul utilisateur, aucune connexion.

## Décision

- **Deux modes, choisis par la configuration** : `NFACTORY_AUTH_MODE=local` (défaut, inchangé) ou `oidc`.
- **OpenID Connect générique, configuré pour Google par défaut.**
  - Émetteur par défaut : `https://accounts.google.com`. Le document de découverte donne les adresses.
  - Rien de propre à Google dans le code, sauf le contrôle de domaine par la revendication `hd`. Un autre fournisseur OIDC (Microsoft Entra, Okta…) n'est qu'un autre émetteur. SAML n'est pas fait.
- **Flux.** Le flux *Authorization Code* avec PKCE (S256), `state` et `nonce`, conduit côté serveur par l'API. Seuls `openid email profile` sont demandés : ce sont des scopes non sensibles, sans revue de sécurité Google.
  - `GET /auth/login` enregistre une tentative (`login_attempts` : `state`, `nonce`, vérificateur PKCE, 10 minutes, usage unique), puis redirige vers Google.
  - `GET /auth/callback` échange le code. Il vérifie ensuite le jeton d'identité :
    - signature par les clés JWKS de l'émetteur, RS256 seulement ;
    - `iss`, `aud`, `exp`, `nonce` ;
    - `email_verified`.
  - Il applique ensuite la règle d'admission, ouvre une session et redirige vers le dashboard.
  - En cas d'échec, il redirige vers `/?auth_error=<code>`, sans détail du fournisseur.
- **Admission, refusée par défaut.** Un compte entre si son domaine Google Workspace (`hd`, jamais le domaine de l'e-mail) figure dans `NFACTORY_OIDC_ALLOWED_DOMAINS`, ou si son e-mail vérifié figure dans `NFACTORY_OIDC_ALLOWED_EMAILS`. Une configuration sans liste n'admet personne.
  - Les comptes listés dans `NFACTORY_OIDC_OWNER_EMAILS` deviennent `owner` de l'espace local.
  - Les autres comptes deviennent `viewer` (moindre privilège). Un propriétaire change les rôles ; l'écran de gestion des membres relève du RBAC étendu.
  - Un compte est reconnu par `émetteur + sub`, jamais par l'e-mail seul. Seuls l'e-mail et le nom affiché sont gardés : ni photo ni jeton Google.
- **Session.**
  - Un jeton aléatoire (`secrets.token_urlsafe(32)`) est placé dans un cookie `nfactory_session` : `HttpOnly`, `SameSite=Lax`, `Path=/`, et `Secure` si l'adresse de retour est en HTTPS.
  - La base ne garde que son empreinte SHA-256 (`auth_sessions`), avec une expiration (`NFACTORY_SESSION_TTL_HOURS`, 12 h par défaut).
  - `POST /auth/logout` révoque la session.
  - Les jetons d'accès et de rafraîchissement Google ne sont pas conservés.
- **Toute l'API exige une session en mode `oidc`**, sauf `/health*` et `/auth/*`. Le contrôle est une dépendance posée sur le routeur, pas route par route : aucune route ne peut l'oublier. Sans session, la réponse est 401 `not_authenticated`.
- **Protection CSRF.** En mode `oidc`, une requête qui modifie quelque chose (POST, PUT, PATCH, DELETE) doit porter un en-tête `Origin` égal à l'origine du dashboard (déduite de l'adresse de retour). Sinon : 403 `csrf_rejected`. Ce contrôle complète `SameSite=Lax`.
- **Secret client.** `NFACTORY_OIDC_CLIENT_SECRET` est lu dans l'environnement, comme les autres secrets du `.env`. L'utilisateur le saisit lui-même ; aucun agent ne lit le `.env`. Il n'apparaît dans aucune réponse, aucun journal et aucun événement.
- **Adresse de retour.** Elle passe par le dashboard (`http://127.0.0.1:3000/api/v1/auth/callback` par défaut, réglable avec `NFACTORY_OIDC_REDIRECT_URL`), pour que le cookie appartienne à l'origine du dashboard. Si la console Google refuse `127.0.0.1` pour un client « Application Web », on y met `http://localhost:3000/...`. Seul le navigateur suit cette adresse : la règle « 127.0.0.1, jamais localhost » vise les appels de nos services.
- **Bibliothèque.** PyJWT (`pyjwt[crypto]`, déjà présent par `redis`, désormais déclaré) vérifie le jeton. Les clés et la découverte sont lues par `httpx`, ce qui permet de les simuler en test. Aucune dépendance OAuth complète n'est ajoutée : le flux tient en un module.
- **Audit.** `auth.login` (compte admis, rôle), `auth.denied` (motif, sans jeton) et `auth.logout` sont écrits par `app/services/audit.record`.

## Conséquences

- Pour l'activer, l'utilisateur crée un client OAuth « Application Web » dans Google Cloud, déclare l'adresse de retour, puis remplit son `.env`.
- Tant qu'aucun client Google réel n'existe, le flux est prouvé contre un fournisseur simulé (respx) qui signe de vrais jetons RS256. L'essai réel avec Google attend ce client.
- Les scripts (`smoke_test.py`, `load_test.py`, évals) visent le mode local. En mode `oidc`, ils n'ont pas de session et reçoivent 401.
- Le pont local et le worker n'appellent pas l'API : ils ne sont pas concernés.
