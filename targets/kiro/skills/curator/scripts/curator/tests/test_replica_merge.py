'''Tests for build_replica's merge consumption and build_report's
surfacing of rationale/existing_summary/new_info_present.

Both functions are exercised in isolation: ``_render_page_via_template``
is patched to a stub so the tests do not shell out to render.sh,
and ``abs_path`` is patched so an existing-vault-page lookup
returns a path under tmp without depending on the user's actual
vault.
'''
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from curator.vault import replica


@pytest.fixture
def stub_render(monkeypatch):
    '''Patch the render shim so build_replica does not shell out.

    Returns the captured (kind, item) pairs so tests can assert
    which item was rendered for each call.
    '''
    captured: list[tuple[str, dict]] = []

    def _stub(kind: str, item: dict) -> str:
        captured.append((kind, dict(item)))
        return f"---\ntype: {kind}\n---\n\n# {item.get('name')}\n\n{item.get('definition', '')}\n"

    monkeypatch.setattr(replica, "_render_page_via_template", _stub)
    return captured


@pytest.fixture
def fake_vault(monkeypatch, tmp_path):
    '''Point abs_path at a tmp directory so existence checks
    return True only for paths the test pre-populates.'''
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    def _abs(vault_path: str) -> Path:
        return vault_root / vault_path

    monkeypatch.setattr(replica, "abs_path", _abs)
    return vault_root


class TestBuildReplicaMergeConsumption:
    '''build_replica reads merge outputs and prefers ``merged_item``
    over the raw extractor item when both exist for the same name.'''

    def _basic_inputs(self, fake_vault):
        # Create an existing vault page so abs_path().exists() is True
        # for "12 KEYWORDS/Few-Shot Prompting.md".
        kw_dir = fake_vault / "12 KEYWORDS"
        kw_dir.mkdir(parents=True)
        (kw_dir / "Few-Shot Prompting.md").write_text(
            "---\ntype: keyword\n---\n\n# Few-Shot Prompting\n\nold body\n",
            encoding="utf-8",
        )

        extractions = {
            "keywords": [
                {"name": "Few-Shot Prompting",
                 "definition": "raw extractor definition",
                 "definition_source": "source",
                 "source_quote": "..."},
                {"name": "New Keyword",
                 "definition": "fresh def",
                 "definition_source": "source",
                 "source_quote": "..."},
            ]
        }
        destinations = {
            "keywords": {"mode": "artifact", "folder": "12 KEYWORDS"},
        }
        vault_matches = {
            "keywords": [
                {"name": "Few-Shot Prompting",
                 "match": "12 KEYWORDS/Few-Shot Prompting.md"},
                {"name": "New Keyword", "match": None},
            ]
        }
        return extractions, destinations, vault_matches

    def test_merged_item_replaces_raw_when_match_exists(
            self, tmp_path, stub_render, fake_vault):
        extractions, destinations, vault_matches = \
            self._basic_inputs(fake_vault)
        merges = {
            "keywords": [{
                "name": "Few-Shot Prompting",
                "vault_path": "12 KEYWORDS/Few-Shot Prompting.md",
                "merged_item": {
                    "name": "Few-Shot Prompting",
                    "definition": "INTEGRATED merged definition",
                    "definition_source": "merged",
                    "source_quote": "this run quote",
                },
                "rationale": "Adds source-specific framing.",
                "existing_summary": "Defines few-shot prompting.",
                "new_info_present": True,
            }]
        }

        replica.build_replica(
            tmp_path, extractions, destinations,
            vault_matches, "src.md", merges=merges)

        # The matched item was rendered with merged_item fields.
        rendered_kinds = [k for k, _ in stub_render]
        rendered_items = {it["name"]: it for _, it in stub_render}
        assert "Few-Shot Prompting" in rendered_items
        assert rendered_items["Few-Shot Prompting"]["definition"] \
            == "INTEGRATED merged definition"
        # The unmatched item used the raw extractor definition.
        assert rendered_items["New Keyword"]["definition"] == "fresh def"
        assert rendered_kinds == ["keywords", "keywords"]

    def test_manifest_carries_merge_fields_for_modified_entry(
            self, tmp_path, stub_render, fake_vault):
        extractions, destinations, vault_matches = \
            self._basic_inputs(fake_vault)
        merges = {
            "keywords": [{
                "name": "Few-Shot Prompting",
                "vault_path": "12 KEYWORDS/Few-Shot Prompting.md",
                "merged_item": {
                    "name": "Few-Shot Prompting",
                    "definition": "merged",
                },
                "rationale": "Adds source-specific framing.",
                "existing_summary": "Defines few-shot prompting.",
                "new_info_present": True,
            }]
        }

        result = replica.build_replica(
            tmp_path, extractions, destinations,
            vault_matches, "src.md", merges=merges)

        modified = [e for e in result["entries"]
                    if e.get("op") == "modified"]
        assert len(modified) == 1
        m = modified[0]
        assert m["name"] == "Few-Shot Prompting"
        assert m["rationale"] == "Adds source-specific framing."
        assert m["existing_summary"] == "Defines few-shot prompting."
        assert m["new_info_present"] is True

    def test_create_entries_have_no_merge_fields(
            self, tmp_path, stub_render, fake_vault):
        extractions, destinations, vault_matches = \
            self._basic_inputs(fake_vault)
        result = replica.build_replica(
            tmp_path, extractions, destinations,
            vault_matches, "src.md", merges=None)

        created = [e for e in result["entries"]
                   if e.get("op") == "create"]
        assert len(created) == 1
        assert "rationale" not in created[0]
        assert "existing_summary" not in created[0]
        assert "new_info_present" not in created[0]

    def test_no_merges_falls_back_to_raw_extractor_item(
            self, tmp_path, stub_render, fake_vault):
        extractions, destinations, vault_matches = \
            self._basic_inputs(fake_vault)
        replica.build_replica(
            tmp_path, extractions, destinations,
            vault_matches, "src.md", merges=None)
        rendered_items = {it["name"]: it for _, it in stub_render}
        # Without merges the raw extractor definition lands in the file.
        assert rendered_items["Few-Shot Prompting"]["definition"] \
            == "raw extractor definition"

    def test_modified_entry_defaults_when_merge_missing_optional_fields(
            self, tmp_path, stub_render, fake_vault):
        extractions, destinations, vault_matches = \
            self._basic_inputs(fake_vault)
        merges = {
            "keywords": [{
                "name": "Few-Shot Prompting",
                "vault_path": "12 KEYWORDS/Few-Shot Prompting.md",
                "merged_item": {"name": "Few-Shot Prompting",
                                 "definition": "merged"},
                "rationale": "Adds context.",
                "existing_summary": "Existing.",
                "new_info_present": False,  # explicitly false
            }]
        }
        result = replica.build_replica(
            tmp_path, extractions, destinations,
            vault_matches, "src.md", merges=merges)
        m = next(e for e in result["entries"]
                 if e.get("op") == "modified")
        assert m["new_info_present"] is False


class TestBuildReportMergeFields:
    '''build_report propagates rationale/existing_summary/
    new_info_present from manifest entries to
    manifest_modifications.'''

    def test_modifications_carry_merge_fields(
            self, tmp_path, monkeypatch):
        # Build a fake plan + outputs so build_report can read them.
        # Use a minimal LoomPlan with one task — we only need
        # the manifest reader path to fire.
        from loom.engine import store
        from loom.engine.models import LoomPlan, Task

        wd = tmp_path / "wd"
        (wd / "global" / "vault-replica").mkdir(parents=True)
        # Manifest with merge fields on a modified entry.
        manifest = {
            "entries": [
                {"vault_path": "12 KEYWORDS/Few-Shot Prompting.md",
                 "op": "modified",
                 "kind": "keywords",
                 "name": "Few-Shot Prompting",
                 "rationale": "RAT",
                 "existing_summary": "ES",
                 "new_info_present": False},
                {"vault_path": "12 KEYWORDS/New Term.md",
                 "op": "create",
                 "kind": "keywords",
                 "name": "New Term"},
            ],
        }
        (wd / "global" / "vault-replica" / "manifest.yaml").write_text(
            yaml.safe_dump(manifest), encoding="utf-8")

        # Stub a tiny plan so build_report's load_plan succeeds.
        # Use the tasks build_report iterates on:
        # ``classify``, ``extract-summary``, ``extract-<...>``,
        # ``synthesis``, ``prune-replica``, ``fetch``. None must
        # have output to make load_plan / safe_load happy — they
        # all default-load to None.
        tasks = [
            Task(id="fetch", kind="tool", depends_on=[],
                 cmd=["true"], output_schema="x"),
            Task(id="classify", kind="agent", depends_on=[],
                 template="x", output_schema="x"),
        ]
        plan = LoomPlan(tasks=tasks)
        store.save_plan(wd, plan)

        result = replica.build_report(wd)
        assert "manifest_modifications" in result
        mods = result["manifest_modifications"]
        assert len(mods) == 1   # only the modified entry, not create
        m = mods[0]
        assert m["vault_path"] == "12 KEYWORDS/Few-Shot Prompting.md"
        assert m["rationale"] == "RAT"
        assert m["existing_summary"] == "ES"
        assert m["new_info_present"] is False

    def test_legacy_modification_without_merge_fields_defaults(
            self, tmp_path):
        '''Manifest entries written before the merge feature lack
        the new fields. build_report must still produce valid
        output (empty strings for text, True for new_info_present
        so the entry surfaces as a real modification).'''
        from loom.engine import store
        from loom.engine.models import LoomPlan, Task

        wd = tmp_path / "wd"
        (wd / "global" / "vault-replica").mkdir(parents=True)
        manifest = {
            "entries": [
                {"vault_path": "12 KEYWORDS/Old.md",
                 "op": "modified",
                 "kind": "keywords",
                 "name": "Old"},
            ],
        }
        (wd / "global" / "vault-replica" / "manifest.yaml").write_text(
            yaml.safe_dump(manifest), encoding="utf-8")

        tasks = [
            Task(id="fetch", kind="tool", depends_on=[],
                 cmd=["true"], output_schema="x"),
            Task(id="classify", kind="agent", depends_on=[],
                 template="x", output_schema="x"),
        ]
        plan = LoomPlan(tasks=tasks)
        store.save_plan(wd, plan)

        result = replica.build_report(wd)
        m = result["manifest_modifications"][0]
        assert m["rationale"] == ""
        assert m["existing_summary"] == ""
        assert m["new_info_present"] is True
