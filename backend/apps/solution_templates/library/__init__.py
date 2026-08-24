"""
Standard Solution Library (Phase P2.4A).

Reusable, composable building blocks every no-code solution draws from — expressed as
plain manifest fragments (dicts) so they apply through the same appliers as any template:

  - business_objects : Standard Business Object Library (entity specs)
  - workflows        : Standard Workflow Library (generic, entity-bound at compose time)
  - roles            : Standard Role Library
  - dashboards       : Dashboard Library (Executive / Operational / Analytical)
  - reports          : Report Library (Summary / Detail / Trend / Aging / KPI)

``get_library()`` returns the whole catalog for the API; ``business_object(slug)`` etc.
fetch a single fragment so the Create-Solution Wizard (P2.4B) can compose templates.
"""
from .business_objects import BUSINESS_OBJECTS
from .dashboards import DASHBOARD_LIBRARY
from .reports import REPORT_LIBRARY
from .roles import ROLE_LIBRARY
from .workflows import WORKFLOW_LIBRARY


def get_library() -> dict:
    """The full standard library, shaped for the /library/ API."""
    return {
        "business_objects": list(BUSINESS_OBJECTS.values()),
        "workflows": list(WORKFLOW_LIBRARY.values()),
        "roles": list(ROLE_LIBRARY.values()),
        "dashboards": list(DASHBOARD_LIBRARY.values()),
        "reports": list(REPORT_LIBRARY.values()),
    }


def business_object(slug: str) -> dict | None:
    return BUSINESS_OBJECTS.get(slug)


def workflow_template(key: str) -> dict | None:
    return WORKFLOW_LIBRARY.get(key)


def role_template(key: str) -> dict | None:
    return ROLE_LIBRARY.get(key)


__all__ = [
    "BUSINESS_OBJECTS", "WORKFLOW_LIBRARY", "ROLE_LIBRARY",
    "DASHBOARD_LIBRARY", "REPORT_LIBRARY",
    "get_library", "business_object", "workflow_template", "role_template",
]
