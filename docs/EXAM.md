# Examen LLMOps: Production Readiness

## Vue d'Ensemble

Vous avez devant vous une stack LLMOps complète avec cache, sécurité et monitoring. Cependant, ce code contient **6 mauvaises pratiques critiques** qui le rendent dangereux pour la production.

Votre mission: **identifier et corriger ces 6 problèmes**.

### Format de l'Examen
- **Type**: Take-home exam (archive)

### Workflow Recommandé
```bash
# 1. Fork/clone ce repository
$ git clone <votre-fork> llmops-exam-solution
$ cd llmops-exam-solution

# 2. Créer une branche par exercice (recommandé)
$ git checkout -b fix/structured-logging
$ # Implémenter le fix
$ git commit -m "feat: implement structured logging"

# 3. Merger dans main à la fin
$ git checkout main
$ git merge fix/structured-logging
$ git push origin main
```


## Exercice 1: Configuration Sécurisée et Validation d'Environnement (15 pts)

### Scénario
```bash
# Un développeur démarre l'API en production sans changer les secrets
$ docker compose up -d
$ cat src/api/config/settings.py
JWT_SECRET_KEY = "your-secret-key-change-in-production"  # Visible dans le code!

# Un attaquant forge un token admin
$ curl -H "Authorization: Bearer <forged-token>" http://api/admin/data
```

### Problèmes à Corriger
**Fichier**: `src/api/config/settings.py`

1. `JWT_SECRET_KEY` a une valeur par défaut insécurisée
2. `CORS_ORIGINS: ["*"]` autorise toutes les origines
3. Pas de validation des variables d'environnement au démarrage

### À Implémenter
- [ ] Migrer vers `pydantic.BaseSettings` pour validation des types
- [ ] Fail-fast si `JWT_SECRET_KEY` est la valeur par défaut
- [ ] CORS sécurisé avec liste explicite d'origines
- [ ] Créer `.env.example` avec toutes les variables requises
- [ ] Créer `src/api/config/env_validator.py` pour validation au startup

### Critères de Vérification
```bash
# Sans JWT_SECRET_KEY correcte, l'API doit refuser de démarrer
$ unset JWT_SECRET_KEY
$ docker compose up api
# Attendu: Error: JWT_SECRET_KEY must be set and different from default
```


## Exercice 2: Graceful Shutdown et Resource Cleanup (15 pts)

### Scénario
```bash
# Redémarrage de l'API
$ docker compose restart api

# Logs actuels:
Starting LLMOps Secure API...
MLflow experiment setup completed
Shutting down LLMOps Secure API...  # <- Aucun cleanup!

# Conséquences:
# - Connexions Qdrant non fermées -> connection leak
# - Traces MLflow incomplètes
# - Requêtes en cours interrompues brutalement
```

### Problème à Corriger
**Fichier**: `src/api/config/lifespan.py`

```python
# Actuellement:
yield
print("Shutting down LLMOps Secure API...")  # Ne fait RIEN!
```

### À Implémenter
- [ ] Cleanup des connexions dans lifespan (Qdrant, HTTP clients)
- [ ] Middleware pour tracker les requêtes en cours (in-flight)
- [ ] Attendre la fin des requêtes avant shutdown (avec timeout 30s)
- [ ] Finaliser les runs MLflow actifs
- [ ] Flush du cache avant fermeture

### Critères de Vérification
```bash
# Pendant une requête longue
$ curl -X POST http://localhost:8000/llm/generate -d '{...}' &
$ docker compose stop api

# Logs attendus:
Received shutdown signal
Waiting for 1 in-flight request(s)...
Request completed
Closing Qdrant connections...
Graceful shutdown completed in 2.3s
```


## Exercice 3: Request Timeouts et Resource Limits (15 pts)

### Scénario
```bash
# LiteLLM est lent ou down
$ docker compose stop litellm
$ curl -X POST http://localhost:8000/llm/generate -d '{...}'

# Actuellement: L'API attend INDÉFINIMENT
# Tous les workers bloqués -> API inaccessible
```

### Problème à Corriger
**Fichier**: `src/api/routers/llm.py:26`

```python
# Actuellement: Aucun timeout!
client = openai.OpenAI(
    base_url=f"{settings.LITELLM_URL}/v1",
    api_key="dummy-key"
)
```

### À Implémenter
- [ ] Timeout sur le client OpenAI (30s request, 5s connect)
- [ ] Limite de taille du body (1MB max)
- [ ] Circuit breaker pour LiteLLM (ouvrir après 5 échecs)
- [ ] Middleware `request_limits.py` pour les limites

### Critères de Vérification
```bash
# Timeout après 30s max
$ docker compose stop litellm
$ time curl -X POST http://localhost:8000/llm/generate -d '{...}'
# Attendu: 504 Gateway Timeout après ~30s

# Body trop grand rejeté
$ dd if=/dev/zero bs=1M count=10 | curl -X POST ... --data-binary @-
# Attendu: 413 Payload Too Large
```


## Exercice 4: Error Handling et Retry Logic (20 pts)

### Scénario
```bash
# Erreur réseau transitoire
$ curl -X POST http://localhost:8000/llm/generate -d '{...}'

# Logs actuels:
Error generating response: Connection reset by peer
# -> Erreur retournée immédiatement au lieu de retry

# Response:
{"detail": "Failed to generate response"}  # Aucun contexte!
```

### Problèmes à Corriger
**Fichier**: `src/api/routers/llm.py:175-180`

```python
# Actuellement: Exception générique
except Exception as e:
    print(f"Error generating response: {e}")
    raise HTTPException(status_code=500, detail="Failed to generate response")
```

**Fichier**: `src/api/routers/llm.py:167-169`
```python
# Échec silencieux de MLflow
except Exception as e:
    print(f"Warning: Could not trace LLM request: {e}")
    # Continue sans tracer -> perte de données!
```

### À Implémenter
- [ ] Error handling granulaire par type d'erreur
- [ ] Retry avec exponential backoff (1s, 2s, 4s - max 3 retries)
- [ ] Créer `src/api/utils/retry.py` avec décorateur retry
- [ ] Fallback local si MLflow échoue (log dans fichier)
- [ ] Messages d'erreur avec contexte (incident_id, timestamp)

### Critères de Vérification
```bash
# Retry automatique sur erreur transitoire
$ curl -X POST http://localhost:8000/llm/generate -d '{...}'

# Logs:
Attempt 1: Connection error
Retrying in 1.2s...
Attempt 2: Success

# Réponse avec contexte en cas d'erreur
{
  "error": "BadRequestError",
  "message": "Model 'invalid' not found",
  "incident_id": "inc_abc123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```


## Exercice 5: Health Checks Complets (15 pts)

### Scénario
```bash
# Qdrant est down mais l'API dit "healthy"
$ docker compose stop qdrant
$ curl http://localhost:8000/system/health
{"status": "healthy"}  # FAUX!

# Le load balancer continue d'envoyer du trafic
# -> 100% des requêtes échouent
```

### Problème à Corriger
**Fichier**: `src/api/routers/system.py:20-22`

```python
# Actuellement: Fake health check!
@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}
    # Ne vérifie RIEN!
```

### À Implémenter
- [ ] Endpoint `/health` (liveness) - vérifie que l'app répond
- [ ] Endpoint `/health/detailed` (readiness) - vérifie les dépendances:
  - Qdrant connectivité
  - LiteLLM accessible
  - MLflow accessible
- [ ] Cache des résultats (30s TTL)
- [ ] Créer `src/api/services/health_checker.py`
- [ ] Mettre à jour `docker-compose.yml` healthcheck

### Critères de Vérification
```bash
# Basic health toujours OK
$ docker compose stop qdrant
$ curl http://localhost:8000/health
{"status": "alive"}  # 200 OK

# Detailed health détecte le problème
$ curl http://localhost:8000/health/detailed
# 503 Service Unavailable
{
  "status": "degraded",
  "checks": {
    "qdrant": false,
    "litellm": true,
    "mlflow": true
  }
}
```


## Exercice 6: Structured Logging et Observabilité (20 pts)

### Scénario
```bash
# Bug en production, tentative de debugging
$ docker compose logs api | grep error
Error generating response: Connection refused
Error generating response: Timeout
# Quel user? Quel request? Quel timestamp exact? MYSTÈRE!

# Impossible d'analyser avec des outils
$ docker compose logs api | jq
parse error: Invalid JSON  # Ce ne sont pas des logs structurés!
```

### Problème à Corriger
**Partout dans le code**: `print()` statements

```python
# Exemples actuels:
print(f"DEBUG: Making LiteLLM request with model: {request.model}")
print(f"Warning: Could not trace LLM request: {e}")
print(f"Error generating response: {e}")
```

### À Implémenter
- [ ] Configuration logging JSON dans `src/api/config/logging.py`
- [ ] Middleware request ID dans `src/api/middleware/request_id.py`
- [ ] Remplacer TOUS les `print()` par `logger.*()` avec niveaux appropriés
- [ ] Propager request_id dans tous les logs
- [ ] Header `X-Request-ID` dans les réponses

### Critères de Vérification
```bash
# Logs JSON structurés
$ docker compose logs api | head -1 | jq
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "message": "llm_request_started",
  "request_id": "req_abc123",
  "user": "admin",
  "model": "groq-kimi-primary"
}

# Corrélation par request_id
$ curl -D - http://localhost:8000/llm/generate -d '{...}'
X-Request-ID: req_abc123

$ docker compose logs api | jq 'select(.request_id == "req_abc123")'
# Tous les logs de cette requête
```


## Barème

| Exercice | Points | Critères |
|----------|--------|----------|
| 1. Configuration Sécurisée | 15 | Pydantic settings, fail-fast, CORS |
| 2. Graceful Shutdown | 15 | Cleanup, in-flight tracking |
| 3. Request Timeouts | 15 | Timeouts, limits, circuit breaker |
| 4. Error Handling | 20 | Retry, granular errors, fallbacks |
| 5. Health Checks | 15 | Liveness/readiness, dependency checks |
| 6. Structured Logging | 20 | JSON logs, request ID, niveaux |
| **Total** | **100** | |


## Livrables Attendus

### Structure du Repository
```
votre-repo/
├── EXAM.md                           # Ce fichier
├── IMPLEMENTATION.md                 # Vos notes d'implémentation
├── .env.example                      # Template configuration (Ex 1)
├── src/api/
│   ├── config/
│   │   ├── settings.py              # Refactoré avec Pydantic (Ex 1)
│   │   ├── env_validator.py         # Nouveau (Ex 1)
│   │   ├── logging.py               # Nouveau (Ex 6)
│   │   └── lifespan.py              # Modifié (Ex 2)
│   ├── middleware/
│   │   ├── request_id.py            # Nouveau (Ex 6)
│   │   ├── request_limits.py        # Nouveau (Ex 3)
│   │   └── shutdown.py              # Nouveau (Ex 2)
│   ├── services/
│   │   ├── health_checker.py        # Nouveau (Ex 5)
│   │   └── circuit_breaker.py       # Nouveau (Ex 3)
│   ├── utils/
│   │   └── retry.py                 # Nouveau (Ex 4)
│   └── routers/
│       ├── llm.py                   # Modifié (Ex 3, 4, 6)
│       └── system.py                # Modifié (Ex 5, 6)
└── tests/
    └── test_*.py                    # Tests pour chaque exercice
```

### Documentation
Créer un fichier `IMPLEMENTATION.md` avec pour chaque exercice:
- Problème identifié
- Solution implémentée
- Commandes de vérification


## Ressources

- FastAPI: https://fastapi.tiangolo.com
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Python Logging: https://docs.python.org/3/library/logging.html
- Tenacity (retry): https://tenacity.readthedocs.io


## Checklist Finale

Avant de soumettre, vérifiez:

- [ ] `docker compose up` échoue si `JWT_SECRET_KEY` est la valeur par défaut
- [ ] Shutdown gracieux complète en < 30s avec cleanup visible dans les logs
- [ ] Requêtes timeout après 30s maximum
- [ ] Retry automatique sur erreurs transitoires (visible dans logs)
- [ ] `/health/detailed` retourne 503 si une dépendance est down
- [ ] Tous les logs sont en JSON structuré avec request_id
- [ ] Tous vos tests passent: `pytest tests/ -v`

Bonne chance!
