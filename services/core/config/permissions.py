"""The project-wide permission floor.

The API has three tiers, and they are set here rather than view by view so
that a view added later inherits the restriction instead of quietly
inheriting DRF's ``AllowAny`` default:

1. **Reads are public.** The dashboard is a public demonstration over
   seeded data, and every readable endpoint is catalogue, stock level or
   order state that the demo is meant to show.
2. **Writes need an authenticated user, or demo mode.** Placing an order is
   the one mutation the demo deliberately exposes to anonymous visitors, so
   the traffic generator and the README's REST smoke test keep working.
   With ``DEMO_MODE`` off, the whole write surface closes behind
   authentication.
3. **Lifecycle transitions always need an authenticated user.** Advancing
   or cancelling an existing order is an operator action, never part of the
   public demo, so :class:`IsOperator` opts those endpoints out of the
   demo-mode allowance entirely. Cancelling restocks inventory, and order
   identifiers are listable, so leaving this on the public tier would let
   any visitor move stock for orders that are not theirs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from rest_framework.permissions import SAFE_METHODS, BasePermission

if TYPE_CHECKING:  # DRF resolves this module while rest_framework.views is
    # still initialising, so importing the view and request types eagerly
    # would be a circular import. They are only needed for annotations.
    from rest_framework.request import Request
    from rest_framework.views import APIView


class ReadOnlyOrDemoWrite(BasePermission):
    """Allow any read; allow writes only for a real user or in demo mode."""

    message = "Writing requires authentication; this deployment is not in demo mode."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in SAFE_METHODS:
            return True
        if request.user and request.user.is_authenticated:
            return True
        return bool(settings.DEMO_MODE)


class IsOperator(BasePermission):
    """Require a genuine authenticated user, whatever demo mode says."""

    message = "Changing an order's lifecycle requires an authenticated operator."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)
