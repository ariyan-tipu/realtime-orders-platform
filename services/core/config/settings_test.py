"""Settings for test runs.

The real settings module refuses to start without an explicit
``DJANGO_SECRET_KEY`` whenever ``DJANGO_DEBUG`` is off, which is what stops a
deployment from ever running on the key committed to this repository. A test
run is not a deployment, so this module supplies a throwaway key and
development defaults and then defers to the real module for everything else.

Keeping it this thin is the point: tests exercise the same configuration the
service actually runs on, rather than a parallel one that can drift.

Note that Django's test runner forces ``DEBUG = False`` for the duration of
the run regardless of what is set here, so enabling it below only affects how
the settings module is imported, never how the tests behave.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-key-never-leaves-pytest")
os.environ.setdefault("DJANGO_DEBUG", "1")

from config.settings import *  # noqa: E402, F403
