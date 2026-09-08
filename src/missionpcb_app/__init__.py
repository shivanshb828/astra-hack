"""MissionPCB application layer: design state, persistence, adapters and API.

The constraint engine in ``constraint_engine`` remains the sole authority on
whether a design meets its constraints. This package orchestrates around it --
versioned state, history, integrations and transport -- and never re-implements
a check.
"""

from .schema import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION"]
