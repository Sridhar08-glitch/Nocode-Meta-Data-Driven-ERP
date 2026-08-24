"""
Report Library — report specs (manifest ``reports`` fragments).

Five standard report shapes (Summary / Detail / Trend / Aging / KPI). Each is bound to a
concrete entity at compose time via ``nql_source`` (the wizard fills the entity); the applier
derives ``nql_ast`` from ``nql_source`` through the NQL engine, never raw SQL.
"""


def _report(slug, name, report_type, nql_source, display_config=None):
    return {
        "slug": slug, "name": name, "report_type": report_type,
        "nql_source": nql_source, "display_config": display_config or {},
    }


def report_set(entity_slug: str) -> list[dict]:
    """The five standard reports bound to a concrete entity (for the wizard).

    ``nql_source`` is a valid NQL query (``FROM <entity>``); the applier derives the
    ``nql_ast`` through the NQL engine — never raw SQL.
    """
    src = f"FROM {entity_slug}"
    return [
        _report("summary_report", "Summary", "pivot", src),
        _report("detail_report", "Detail", "table", src),
        _report("trend_report", "Trend", "chart", src,
                {"chart_type": "line", "x": "created_at"}),
        _report("aging_report", "Aging", "table", src),
        _report("kpi_report", "KPI", "table", src),
    ]


# Library catalogue (entity-agnostic shapes for browsing).
REPORT_LIBRARY: dict[str, dict] = {
    "summary": {"slug": "summary_report", "name": "Summary", "report_type": "pivot",
                "description": "Grouped totals."},
    "detail": {"slug": "detail_report", "name": "Detail", "report_type": "table",
               "description": "Row-level listing."},
    "trend": {"slug": "trend_report", "name": "Trend", "report_type": "chart",
              "description": "Over-time line chart."},
    "aging": {"slug": "aging_report", "name": "Aging", "report_type": "table",
              "description": "Bucketed by age."},
    "kpi": {"slug": "kpi_report", "name": "KPI", "report_type": "table",
            "description": "Key metric snapshot."},
}
