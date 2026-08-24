"""
Dashboard Library — dashboard specs (manifest ``dashboards`` fragments).

Three standard layouts (Executive / Operational / Analytical). Widgets reference reports by
``report_slug`` (resolved to a created Report at apply time); a widget whose report is absent
is created as a titled placeholder rather than failing the install.
"""


def _widget(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title,
          "grid_x": x, "grid_y": y, "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


DASHBOARD_LIBRARY: dict[str, dict] = {
    "executive": {
        "slug": "executive_dashboard", "name": "Executive Dashboard",
        "description": "High-level KPIs for leadership.",
        "is_default": True,
        "widgets": [
            _widget("metric_card", "Total Records", 0, 0, 3, 2),
            _widget("metric_card", "Created This Month", 3, 0, 3, 2),
            _widget("report", "Trend", 0, 2, 6, 4, report_slug="trend_report"),
        ],
    },
    "operational": {
        "slug": "operational_dashboard", "name": "Operational Dashboard",
        "description": "Day-to-day operational view.",
        "widgets": [
            _widget("report", "Open Items", 0, 0, 6, 4, report_slug="detail_report"),
            _widget("activity_feed", "Recent Activity", 6, 0, 6, 4),
        ],
    },
    "analytical": {
        "slug": "analytical_dashboard", "name": "Analytical Dashboard",
        "description": "Deeper breakdowns and aging.",
        "widgets": [
            _widget("report", "Summary", 0, 0, 6, 4, report_slug="summary_report"),
            _widget("report", "Aging", 6, 0, 6, 4, report_slug="aging_report"),
        ],
    },
}
