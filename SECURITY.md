# Security policy

This is a portfolio and demonstration system rather than a product, but the
defaults are the restrictive ones, so an environment that was never
configured fails closed:

- `DJANGO_DEBUG` is off unless asked for.
- The service refuses to boot without an explicit `DJANGO_SECRET_KEY`
  whenever debug is off, rather than falling back to a key committed to a
  public repository.
- `DEMO_MODE` is off unless asked for. On, it opens exactly two things:
  anonymous order placement and the `/api/demo/*` traffic generator behind
  the dashboard's "Simulate order" button.
- Order lifecycle transitions (advance, cancel) always require an
  authenticated user, in demo mode or out of it. Cancelling returns units to
  stock and order ids are readable from the list endpoint, so this tier is
  deliberately outside the demo allowance.

`.env.example` turns the first three of those on for local development, and
says so. It is a development file; the "Production values" block at the
bottom of it is what a deployment wants.

With debug off the service always sends `nosniff`, `X-Frame-Options: DENY`
and a same-origin referrer policy. `DJANGO_BEHIND_TLS` also enables
the HTTPS redirect, HSTS and secure-only session and CSRF cookies.

Those two groups are separate deliberately. The bundled single-instance
layout in `deploy/nginx.conf` listens on port 80 only, and switching on the
transport settings without a certificate in front is not a hardening step
but an outage: the redirect sends every request to a scheme nothing is
listening on, and the secure-only cookies stop anyone signing into the
admin. The flag belongs in the same deployment step that installs the
certificate. Every proxied nginx location forwards `X-Forwarded-Proto`, so
Django reads the original scheme rather than the plain-HTTP hop between
nginx and gunicorn once TLS exists.

CI runs `manage.py check --deploy --fail-level WARNING` with
`DJANGO_BEHIND_TLS` on, so the internet-facing posture is verified on every
push rather than described.

## Dependencies

Dependabot security updates are enabled, so a vulnerable dependency opens a
pull request that has to pass the full CI suite before it merges. Routine
version bumps are off on purpose: these requirements are compatible ranges,
so most of what that produced were floor raises for versions the ranges
already permitted, and a standing queue of those hides the one alert that
matters.

## Known limitations

The permission model is coarse on purpose: reads are public, because the
dashboard is a public demonstration over seeded data, and any authenticated
user may act as an operator on any order. Per-object ownership, roles and
an audit trail of who advanced what are the obvious next layer and are not
built here.

## Reporting

If you find a vulnerability, email **ariyantipu39@gmail.com** with details
and reproduction steps. Please do not open a public issue for security
reports.
