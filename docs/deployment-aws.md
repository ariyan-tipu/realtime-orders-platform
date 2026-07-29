# AWS deployment runbook (EC2 + S3)

The repository is **deploy-ready, not deployed**: CI already builds and
publishes production images to GHCR, and `.github/workflows/deploy.yml`
performs the rollout below the moment secrets are configured. Nothing in this
document is required to run or evaluate the project locally.

> **Cost warning (deliberate design constraint):** the project runs at £0
> using local Docker and GitHub's free tiers. Following this runbook creates
> AWS resources that are free for 12 months on a new account's free tier
> (750 hours/month of t3.micro or t2.micro depending on region) and then
> cost roughly **8 to 11 USD per month**. Elastic IPs, S3 storage and egress
> can add small charges even inside the free year. Set a billing alarm
> before you start.

## 1. One-time AWS setup

1. Create an AWS account, enable MFA, create an IAM user (no root keys).
2. Set a **zero-spend budget alert** in Billing → Budgets.
3. Launch an EC2 instance:
   - AMI: Ubuntu Server 24.04 LTS, type `t3.micro` (free tier).
   - Security group: allow 22 (your IP only) and 80 (anywhere).
   - Key pair: create one; keep the `.pem` safe.
4. On the instance, install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker ubuntu && newgrp docker
   ```
5. Prepare the app directory and environment:
   ```bash
   mkdir -p ~/app && cd ~/app
   # copy .env.example from the repo and replace EVERY secret value:
   #   POSTGRES_PASSWORD, DJANGO_SECRET_KEY, DJANGO_SUPERUSER_PASSWORD,
   #   DJANGO_DEBUG=0, DEMO_MODE=0, DJANGO_ALLOWED_HOSTS=<instance-ip-or-domain>
   #   RT_DATABASE_URL must embed the same POSTGRES_PASSWORD.
   # Leave DJANGO_BEHIND_TLS unset for now; step 4 turns it on.
   nano .env
   ```

   The service will not start without `DJANGO_SECRET_KEY` once
   `DJANGO_DEBUG` is off. That is deliberate: the alternative is booting on
   the placeholder key committed to this repository. Generate one with
   `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
6. Make the GHCR packages public (repo → Packages → each image → settings →
   public), or `docker login ghcr.io` on the instance with a read-only PAT.

## 2. Wire up GitHub

Repository → Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| `EC2_HOST` | instance public IP / DNS |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | contents of the `.pem` private key |

Optional S3 static artefacts (skills-list item; not required for serving,
since nginx serves the SPA and whitenoise serves admin static):

| Secret / variable | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | IAM user with `s3:PutObject`/`ListBucket` on the bucket |
| `AWS_REGION`, `S3_BUCKET` | e.g. `eu-west-2`, `ariyan-orders-artifacts` |
| repo **variable** `S3_ENABLED` | `true` |

## 3. Deploy

Actions → **Deploy** → Run workflow (choose an image tag, default `latest`).
The workflow copies `docker-compose.prod.yml` to the instance, pulls the
GHCR images, and rolls the stack:

- nginx (SPA + reverse proxy) on **:80**
- gunicorn core (auto-migrates on start), uvicorn realtime, Postgres, Redis
  on the internal network only

First-run seeding, on the instance:

```bash
cd ~/app
IMAGE_PREFIX=ghcr.io/<owner>/realtime-orders-platform TAG=latest \
  docker compose -f docker-compose.prod.yml run --rm core python manage.py seed_data
```

Visit `http://<instance-ip>/` for the dashboard and `/admin/` for Django
admin. `/healthz` (core) and `/ws`-side health via
`docker compose exec realtime curl -s localhost:8001/healthz`.

## 4. TLS, and the flag that goes with it

Everything above serves plain HTTP, which is fine for a demo on an IP
address and not fine for anything with a domain in front of it. Point a
domain at the instance, then terminate TLS either with certbot on the box
or with an ALB upstream, and add a `listen 443 ssl` server block (or let
`certbot --nginx` write one) with the port 80 block redirecting to it.

In the same step, and not before it, set `DJANGO_BEHIND_TLS=1` in `.env`
and restart. That turns on the HTTPS redirect, HSTS and secure-only session
and CSRF cookies. Setting it while nginx still listens on port 80 alone is
an outage rather than a hardening step: Django redirects every request to a
scheme nothing answers on, and the browser stops returning the session and
CSRF cookies, so the admin becomes unusable. The two changes belong
together, which is why the flag is separate from `DJANGO_DEBUG`.

Verify afterwards:

```bash
docker compose -f docker-compose.prod.yml exec core \
  python manage.py check --deploy --fail-level WARNING
curl -sI http://<domain>/api/ | head -1     # expect 301 to https
```

CI runs that same check with `DJANGO_BEHIND_TLS=1` on every push, so a
regression in the hardening fails the build rather than waiting for a
deployment to notice.

## 5. Operations

- **Logs:** `docker compose -f docker-compose.prod.yml logs -f --tail 100`
- **Redeploy:** re-run the workflow (or `pull` + `up -d` manually).
- **Backups:** `docker compose exec db pg_dump -U orders orders | gzip > backup.sql.gz`
- **Teardown (stop all cost):** terminate the instance, release any Elastic
  IP, delete the S3 bucket, delete the key pair. Billing → verify £0.

## Why not EKS

A single well-run Compose deployment is fully explainable end-to-end in an
interview; a Kubernetes cluster that exists to exist is not. The images are
standard OCI artefacts, so promoting them into EKS (Deployment + Service +
HPA per service, RDS instead of the db container) is an additive step, not a
rewrite. See ADR 0004.
