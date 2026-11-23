# Examen LLMOps : mise en production

> English version: [EXAM.md](EXAM.md)

## Vue d'ensemble

Ce repository contient une stack LLMOps complète (FastAPI, LiteLLM, cache Qdrant, MLflow, Prometheus, Grafana). Elle fonctionne, mais six mauvaises pratiques la rendent dangereuse en production. Votre mission : les corriger.

- **Les exercices 1 à 3 sont obligatoires.** Ils s'appuient sur des notions vues dans les cours *Intégrer un LLM en production* et *Conception des systèmes ML*.
- **Les exercices 4 à 6 sont des bonus.** Ils vont au-delà des cours. Chacun est accompagné de pistes.

Chaque exercice a une vérification que vous pouvez lancer vous-même sur la stack démarrée :

```bash
docker compose up -d --build
bash scripts/check_exercise.sh 1    # de 1 à 6
```

Les lignes `[OK]` montrent ce qui fonctionne déjà, les lignes `[FAIL]` ce qui manque. Sur le code de départ, toutes les vérifications échouent.

### Mise en place

```bash
cp .env.example .env
# Renseigner JWT_SECRET_KEY (openssl rand -hex 32) et GROQ_API_KEY (clé gratuite : https://console.groq.com/keys)
docker compose up -d --build
```

### Méthode conseillée

```bash
git checkout -b fix/secure-config     # une branche par exercice
# implémenter, puis vérifier
bash scripts/check_exercise.sh 1
git commit -am "fix: secure configuration"
git checkout main && git merge fix/secure-config
```

---

## Exercices obligatoires

### Exercice 1 : configuration sécurisée (30 pts)

**Problème.** `src/api/config/settings.py` contient une valeur par défaut pour `JWT_SECRET_KEY` (`"your-secret-key-change-in-production"`) et `CORS_ORIGINS = ["*"]`. Si quelqu'un déploie sans changer le secret, n'importe qui peut forger un token admin avec la valeur lue dans le code.

**À faire**
- [ ] Passer la configuration sur `pydantic-settings` (`BaseSettings`), lue depuis l'environnement.
- [ ] Refuser de démarrer (fail fast) si `JWT_SECRET_KEY` est absente, égale à la valeur par défaut ou fait moins de 32 caractères.
- [ ] Remplacer `CORS_ORIGINS = ["*"]` par une liste explicite d'origines.
- [ ] Compléter `src/api/config/env_validator.py` (point de départ fourni) et l'appeler au démarrage.
- [ ] Tenir `.env.example` à jour avec toutes les variables requises.

**Pistes**
- Rappels de cours : les secrets dans les variables d'environnement (*Conception des systèmes ML*, chapitre 7) ; l'authentification JWT (*Intégrer un LLM en production*, chapitre 3).
- `pydantic-settings` : un champ sans valeur par défaut est obligatoire ; un `@field_validator` peut rejeter une valeur trop faible. Doc : https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- La vérification importe `config.settings` avec le secret par défaut et attend que l'import échoue.

**Vérification :** `bash scripts/check_exercise.sh 1`

### Exercice 2 : gestion des erreurs et retry (35 pts)

**Problème.** Dans `src/api/routers/llm.py`, toutes les erreurs finissent dans un `except Exception` qui renvoie `{"detail": "Failed to generate response"}`. Une erreur réseau passagère est renvoyée tout de suite au lieu d'être retentée, et rien ne permet au support de retrouver l'incident dans les logs.

**À faire**
- [ ] Traiter les erreurs par type : limite de débit (429), requête invalide ou modèle inconnu (400/404), connexion ou timeout (502/504).
- [ ] Renvoyer des erreurs structurées : type d'erreur, message, `incident_id`, `timestamp`.
- [ ] Retenter les erreurs passagères (connexion, timeout, limite de débit) avec un backoff exponentiel : 1 s, 2 s, 4 s, 3 nouvelles tentatives au maximum. Compléter `src/api/utils/retry.py` (point de départ fourni).
- [ ] Logger chaque tentative, par exemple `Attempt 1/4 failed: APIConnectionError. Retrying in 1.1s`.
- [ ] Si le traçage MLflow échoue, logger l'échec au lieu de l'ignorer.

**Pistes**
- Rappels de cours : retry avec backoff exponentiel et circuit breaker (*Conception des systèmes ML*, chapitre 5) ; fallback entre modèles avec LiteLLM (*Intégrer un LLM en production*, chapitre 1).
- Ne retentez pas une erreur client (400, 404) : elle échouera encore.
- Ajoutez un peu d'aléatoire au délai pour que les clients ne retentent pas tous en même temps.
- Librairie possible : `tenacity` (https://tenacity.readthedocs.io). Une petite boucle écrite à la main est acceptée aussi.
- Mettez `max_retries=0` sur le client OpenAI pour que seule votre logique de retry s'applique.

**Vérification :** `bash scripts/check_exercise.sh 2` (la vérification arrête LiteLLM quelques secondes et attend des tentatives dans les logs).

### Exercice 3 : logs structurés (35 pts)

**Problème.** Le code utilise `print()` partout. Quand une requête échoue, rien n'indique quel utilisateur ni quelle requête était en cause, et les logs ne sont pas exploitables (`docker compose logs api | jq` échoue).

**À faire**
- [ ] Configurer des logs JSON dans `src/api/config/logging_config.py` (point de départ fourni) : un objet JSON par ligne avec au moins `timestamp`, `level`, `message`, `request_id`.
- [ ] Compléter le middleware `src/api/middleware/request_id.py` (point de départ fourni) : générer un identifiant de requête, le garder pendant toute la requête, le renvoyer dans l'en-tête `X-Request-ID`.
- [ ] Remplacer chaque `print()` par `logger.debug/info/warning/error()` au bon niveau.
- [ ] Ajouter le `request_id` à chaque ligne de log écrite pendant une requête.

**Pistes**
- Rappel de cours : le pattern de journal de prédiction, un identifiant unique par requête (*Conception des systèmes ML*, chapitre 8).
- Une sous-classe de `logging.Formatter` qui renvoie `json.dumps({...})` suffit. Doc : https://docs.python.org/3/library/logging.html
- `contextvars.ContextVar` garde l'identifiant de requête accessible dans toute fonction appelée pendant la requête.
- Les logs d'accès d'Uvicorn peuvent rester tels quels ; vos logs applicatifs doivent être en JSON.

**Vérification :** `bash scripts/check_exercise.sh 3`

---

## Exercices bonus

Ces sujets ne sont pas traités dans les cours. Chacun rapporte des points en plus mais ne peut pas vous faire échouer.

### Exercice 4 (bonus) : arrêt propre de l'API (+10 pts)

**Problème.** Dans `src/api/config/lifespan.py`, rien ne se passe après `yield` : au `docker compose stop api`, les requêtes en cours sont coupées, les connexions Qdrant ne sont pas fermées et les traces MLflow restent incomplètes.

**À faire**
- [ ] Suivre les requêtes en cours avec un middleware (par exemple `src/api/middleware/shutdown.py`).
- [ ] À l'arrêt, attendre qu'elles se terminent (30 s maximum), puis fermer Qdrant et les clients HTTP et terminer les runs MLflow actifs.
- [ ] Logger chaque étape : `Waiting for 1 active request(s)...`, `Closing Qdrant connections...`, `Graceful shutdown completed in 2.3s`.

**Pistes**
- FastAPI exécute le code placé après `yield` dans la fonction lifespan quand le serveur s'arrête. Doc : https://fastapi.tiangolo.com/advanced/events/
- Un compteur incrémenté et décrémenté par un middleware suffit pour savoir combien de requêtes sont en cours.

**Vérification :** `bash scripts/check_exercise.sh 4`

### Exercice 5 (bonus) : timeouts et limites de requête (+10 pts)

**Problème.** Le client OpenAI de `src/api/routers/llm.py` n'a pas de timeout : si LiteLLM se bloque, tous les workers attendent indéfiniment. L'API accepte aussi des requêtes de n'importe quelle taille.

**À faire**
- [ ] Mettre un timeout sur le client OpenAI : 30 s pour la requête, 5 s pour la connexion. Renvoyer 504 en cas de timeout.
- [ ] Rejeter les requêtes de plus de 1 Mo avec 413 (middleware `src/api/middleware/request_limits.py`).
- [ ] Optionnel : un circuit breaker qui arrête d'appeler LiteLLM après 5 échecs consécutifs et renvoie 503 pendant un moment.

**Pistes**
- `openai.OpenAI(..., timeout=httpx.Timeout(30.0, connect=5.0))`. Doc : https://www.python-httpx.org/advanced/timeouts/
- Un middleware peut lire l'en-tête `Content-Length` et répondre 413 avant de lire le contenu.
- Circuit breaker : *Conception des systèmes ML*, chapitre 5.

**Vérification :** `bash scripts/check_exercise.sh 5`

### Exercice 6 (bonus) : health checks (+10 pts)

**Problème.** `/system/health` répond toujours `"healthy"`, même quand Qdrant ou LiteLLM est arrêté. Un load balancer continuerait d'envoyer du trafic vers une instance en panne.

**À faire**
- [ ] `/health` (liveness) : répond 200 tant que l'application tourne.
- [ ] `/health/detailed` (readiness) : vérifie Qdrant, LiteLLM et MLflow ; répond 200 si tout est disponible, sinon 503 avec `"status": "degraded"` et le détail par dépendance.
- [ ] Mettre les résultats en cache 30 s (par exemple dans `src/api/services/health_checker.py`).
- [ ] Utiliser `/health` dans le healthcheck du service `api` de `docker-compose.yml`.

**Pistes**
- La liveness répond à « le processus est-il vivant ? », la readiness à « peut-il recevoir du trafic ? ». Doc : https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- Les health checks sont présentés dans *Intégrer un LLM en production*, chapitre 6.
- Vérifiez les dépendances en parallèle avec des timeouts courts pour que `/health/detailed` reste rapide.

**Vérification :** `bash scripts/check_exercise.sh 6` (la vérification arrête Qdrant environ 35 s).

---

## Barème

| Exercice | Points |
|----------|--------|
| 1. Configuration sécurisée | 30 |
| 2. Gestion des erreurs et retry | 35 |
| 3. Logs structurés | 35 |
| **Total obligatoire** | **100** |
| 4. Arrêt propre (bonus) | +10 |
| 5. Timeouts et limites (bonus) | +10 |
| 6. Health checks (bonus) | +10 |

- **Validation :** au moins 60/100 sur les exercices 1 à 3.
- Un exercice qui fonctionne mais reste incomplet obtient la moitié de ses points.
- Les points bonus s'ajoutent à la note finale (plafonnée à 100). Ils ne remplacent pas les exercices obligatoires.

## Livrables

- Votre repository avec le code corrigé (archive ou lien, selon ce qui est demandé sur la plateforme).
- Un fichier `IMPLEMENTATION.md` à la racine, avec pour chaque exercice : le problème, votre solution, la commande qui montre que ça fonctionne.

## Checklist finale

- [ ] `bash scripts/check_exercise.sh 1`, `2` et `3` affichent `PASSED`.
- [ ] Exercices bonus tentés : leur vérification affiche `PASSED`.
- [ ] `IMPLEMENTATION.md` est rédigé.
- [ ] `.env` n'est pas commité (il contient vos clés API).
