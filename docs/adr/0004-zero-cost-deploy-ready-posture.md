# ADR 0004: zero cost by default, deploy-ready by design

**Status:** accepted

## Context

This is a portfolio system. It must demonstrate production CI/CD and AWS
deployment competence without requiring an always-on paid host, and it must
be runnable end to end by anyone with Docker.

## Decision

- **Local:** the whole stack runs under Docker Compose; nothing requires a
  cloud account.
- **CI:** GitHub Actions (free for public repositories) runs lint, both
  pytest suites against real PostgreSQL service containers (including the
  concurrency and LISTEN/NOTIFY tests), the C++ build with parity tests and
  a benchmark, the frontend typecheck, tests and build, the full Compose
  quickstart with a live end-to-end smoke test, and finally builds all
  three production images.
- **Registry:** images push to GitHub Container Registry (free for public
  images) on every main-branch build, tagged `latest` and by commit SHA.
- **Deployment:** `deploy.yml` targets a single EC2 instance over SSH using
  `docker-compose.prod.yml`, with an optional S3 sync for static artefacts.
  It is dormant: without the AWS secrets configured it exits with a notice
  and no side effects. The full runbook, including free-tier caveats and a
  realistic monthly cost table, lives in docs/deployment-aws.md.
- **Kubernetes:** deliberately not used. A single well-run Compose
  deployment is easier to defend end to end than an EKS cluster; the images
  are standard OCI artefacts, so the EKS path stays open.

## Consequences

- Zero standing cost; the repository still demonstrates the full pipeline
  from lint to registry to deploy with real, working configuration.
- Anyone reviewing the project can activate real AWS deployment by adding
  three secrets, with no code changes.
