# k8s manifests

Namespace `blog`. All manifests assume:

- A working **Gateway API** install (any conformant implementation: Envoy Gateway,
  Istio, kgateway, nginx-gateway-fabric, Cilium, …) with at least one `Gateway`
  resource already provisioned by the cluster operator.
- TLS termination handled on the Gateway listener (cert-manager or whatever the
  platform uses). HTTPRoute does not configure TLS itself.
- A default `StorageClass` that supports `ReadWriteOnce`
- DNS pointing the chosen hostname at the Gateway's address.

## Layout

```
k8s/
├── namespace.yaml
├── configmap.yaml             # non-secret app env
├── secret.example.yaml        # JWT_PRIVATE_KEY_PEM, ADMIN_PASSWORD_HASH, DATABASE_URL, GATEWAY_SHARED_SECRET
├── kustomization.yaml         # bundles everything except Jobs
├── postgres/
│   ├── secret.example.yaml    # POSTGRES_USER / PASSWORD / DB
│   ├── service.yaml           # headless, port 5432
│   ├── statefulset.yaml       # postgres:16, PVC 10Gi
│   └── backup-cronjob.yaml    # daily pg_dump → 5Gi PVC (rotates 14 days)
└── app/
    ├── service.yaml           # ClusterIP, port 8080
    ├── deployment.yaml        # 2 replicas, /healthz probes, non-root, readOnlyRoot
    ├── httproute.yaml         # Gateway API HTTPRoute attached to an existing Gateway
    ├── hpa.yaml               # 2–6 replicas, CPU 70% / mem 80%
    ├── pdb.yaml               # minAvailable: 1
    ├── networkpolicy.yaml     # default-deny + explicit allows
    └── seed-job.yaml          # python -m seed.fixtures

The app creates missing tables on startup via `Base.metadata.create_all()`
(see `app/core/db/schema.py`). There is no migration tool — schema changes
beyond initial creation require manual DDL on the live DB.
```

## Prerequisites — fill before apply

1. Copy and edit the secret templates (these are committed as `.example.yaml`):
   - `k8s/secret.example.yaml` → fill `JWT_PRIVATE_KEY_PEM` (multi-line PEM body),
     `ADMIN_PASSWORD_HASH`, `DATABASE_URL`, `GATEWAY_SHARED_SECRET`.
     The gateway has no JWT secret — it fetches the public key from
     `/.well-known/jwks.json`. `GATEWAY_SHARED_SECRET` must equal the gateway's
     `APP_CONFIG_SECURITY_GATEWAY_SHARED_SECRET`.
   - `k8s/postgres/secret.example.yaml` → fill `POSTGRES_PASSWORD` (must match `DATABASE_URL`)
2. Replace `REPLACE_ME_owner` in the two image refs:
   - `app/deployment.yaml`, `app/seed-job.yaml`
3. In `app/httproute.yaml`, replace `REPLACE_ME_gateway_name`,
   `REPLACE_ME_gateway_namespace`, `sectionName`, and `api.example.com`.
   Then update `CORS_ORIGINS` in `configmap.yaml` to match the FE origin.
4. `app/networkpolicy.yaml` pins the gateway data-plane namespace to `api-service`
   (self-operated Spring Cloud Gateway). When moving to a different Gateway API
   implementation update it to `envoy-gateway-system` / `istio-system` /
   `kgateway-system` / `nginx-gateway` etc. Cilium Gateway API sources from the
   node itself, so the policy needs to be redesigned in that case.
5. Build & push image:
   ```
   docker build -t ghcr.io/<owner>/blog-be:0.1.0 .
   docker push ghcr.io/<owner>/blog-be:0.1.0
   ```

## First install

```
kubectl apply -k k8s/

# wait for postgres before the app boots
kubectl -n blog rollout status statefulset/postgres

# app creates tables in its lifespan on first boot
kubectl -n blog rollout status deploy/blog-app

# (optional) seed initial 12 posts
kubectl -n blog apply -f k8s/app/seed-job.yaml
kubectl -n blog wait --for=condition=complete job/seed --timeout=120s
```

## Release loop

```
# 1) build & push new image tag
docker build -t ghcr.io/<owner>/blog-be:<tag> .
docker push  ghcr.io/<owner>/blog-be:<tag>

# 2) roll the deployment (any new tables are picked up on pod startup)
kubectl -n blog set image deploy/blog-app app=ghcr.io/<owner>/blog-be:<tag>
kubectl -n blog rollout status deploy/blog-app
```

> Column / type / index changes are NOT auto-applied. Apply DDL manually
> via `kubectl -n blog exec -it postgres-0 -- psql -U blog -d blog` before
> rolling code that depends on the change.

## Generating ADMIN_PASSWORD_HASH

```
.venv/bin/python -c "from app.core.security.password import hash_password; print(hash_password('your-pw'))"
```

## Generating JWT_PRIVATE_KEY_PEM

```
openssl genrsa -out priv.pem 2048
# paste the full content of priv.pem into Secret.stringData.JWT_PRIVATE_KEY_PEM
# (BEGIN/END lines included)
```

When rotating, bump `JWT_KID` in `configmap.yaml` (e.g. `v1` → `v2`) so verifiers
refresh their JWKS cache and old tokens stop matching the new key.

## Generating GATEWAY_SHARED_SECRET

```
openssl rand -hex 32
```

Must equal the gateway's `APP_CONFIG_SECURITY_GATEWAY_SHARED_SECRET`. The backend
boot fails if this is unset or shorter than 32 chars in prod.

## Switching to managed Postgres

If you use Neon / Supabase / RDS / Cloud SQL instead of the in-cluster StatefulSet:

1. Remove from `kustomization.yaml`:
   - `postgres/service.yaml`
   - `postgres/statefulset.yaml`
   - `postgres/backup-cronjob.yaml`
   - `postgres/secret.example.yaml`
2. In `blog-app-secret`, set `DATABASE_URL` to the managed connection string
   (must use the `postgresql+asyncpg://` scheme).
3. In `app/networkpolicy.yaml`, replace the postgres podSelector egress rule with an
   `ipBlock:` (or `to: []` if you don't care about egress restrictions).
