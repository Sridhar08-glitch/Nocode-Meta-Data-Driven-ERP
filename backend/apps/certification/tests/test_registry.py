"""
Module 1 — Integration Registry tests.
Verify the registry is complete, non-empty, and structurally valid.
"""

from apps.certification.registry import (
    BY_SOURCE,
    BY_TARGET,
    CERTIFICATION_CHECKLIST,
    INTEGRATION_REGISTRY,
    all_certified,
    integrations_from,
    integrations_to,
)


class TestIntegrationRegistry:
    def test_registry_not_empty(self):
        assert len(INTEGRATION_REGISTRY) >= 15

    def test_all_entries_have_required_fields(self):
        for i in INTEGRATION_REGISTRY:
            assert i.source_module, f"missing source_module: {i}"
            assert i.target_module, f"missing target_module: {i}"
            assert i.service, f"missing service: {i}"
            assert i.trigger, f"missing trigger: {i}"
            assert i.event, f"missing event: {i}"
            assert i.status in ("certified", "partial", "deferred"), \
                f"unknown status: {i.status}"

    def test_all_certified_returns_subset(self):
        certified = all_certified()
        assert len(certified) > 0
        assert all(i.status == "certified" for i in certified)

    def test_lookup_by_source(self):
        procs = integrations_from("procurement")
        assert len(procs) >= 2
        targets = {i.target_module for i in procs}
        assert "inventory" in targets
        assert "ledger" in targets

    def test_lookup_by_target(self):
        to_ledger = integrations_to("ledger")
        sources = {i.source_module for i in to_ledger}
        # payroll, inventory, procurement, assets all post to ledger
        assert "payroll" in sources
        assert "inventory" in sources

    def test_critical_integrations_are_certified(self):
        """The core accounting/inventory flows must be certified."""
        critical = [
            ("procurement", "inventory"),
            ("procurement", "ledger"),
            ("inventory", "ledger"),
            ("manufacturing", "inventory"),
            ("payroll", "ledger"),
        ]
        certified_pairs = {(i.source_module, i.target_module) for i in all_certified()}
        for src, tgt in critical:
            assert (src, tgt) in certified_pairs, \
                f"Critical integration {src}→{tgt} is not certified"

    def test_certification_checklist_has_32_items(self):
        assert len(CERTIFICATION_CHECKLIST) == 32

    def test_checklist_ids_unique(self):
        ids = [c["id"] for c in CERTIFICATION_CHECKLIST]
        assert len(ids) == len(set(ids))

    def test_by_source_by_target_consistent(self):
        """Every entry in BY_SOURCE should appear in BY_TARGET for its target."""
        for intgs in BY_SOURCE.values():
            for i in intgs:
                assert i in BY_TARGET.get(i.target_module, []), \
                    f"{i} not found in BY_TARGET[{i.target_module}]"
