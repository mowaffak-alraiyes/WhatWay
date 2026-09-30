"""Environment variables, with the pre-rename AIDR_* names still honoured.

The project was renamed Aidr → WhatWay. Deployments (Streamlit Cloud, Railway,
Render) still hold secrets under the old AIDR_* names, so importing this module
copies any AIDR_* variable onto its WHATWAY_* twin unless that twin is already
set. New names always win; nothing is ever overwritten.

Import it for the side effect before reading any WHATWAY_* variable:

    import core.env  # noqa: F401
"""

import os

LEGACY_PREFIX = "AIDR_"
PREFIX = "WHATWAY_"


def alias_legacy_env(environ=None) -> list:
    """Copy AIDR_FOO to WHATWAY_FOO where WHATWAY_FOO is unset.

    Returns the names that were aliased, so callers can log the migration.
    """
    env = os.environ if environ is None else environ
    aliased = []
    for legacy in [k for k in env if k.startswith(LEGACY_PREFIX)]:
        current = PREFIX + legacy[len(LEGACY_PREFIX):]
        if not env.get(current):
            env[current] = env[legacy]
            aliased.append(legacy)
    return aliased


ALIASED = alias_legacy_env()
