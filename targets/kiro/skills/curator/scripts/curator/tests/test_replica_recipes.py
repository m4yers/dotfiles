"""End-to-end test for build_replica with the recipes kind.

Unlike test_replica_merge, this test does NOT stub out
``_render_page_via_template`` — we want to verify the full pipeline
including pint enrichment and Jinja rendering of the recipe page.
The render shim shells out to ``template/scripts/render.sh``, which
is part of the user's dotfiles install.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from curator.vault import replica


@pytest.fixture
def fake_vault(monkeypatch, tmp_path):
    """Point abs_path at a tmp directory so existence checks
    return True only for paths the test pre-populates.

    Recipes are not matchable, so this primarily verifies that
    first-ingestion pages render at op=create.
    """
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    monkeypatch.setattr(
        replica, "abs_path",
        lambda vault_path: vault_root / vault_path,
    )
    return vault_root


def _basic_recipe() -> dict:
    return {
        "name": "Chocolate Chip Cookies",
        "description": "Soft, chewy cookies with crisp edges.",
        "yield": "24 cookies",
        "total_time": "45 min",
        "tags": ["dessert", "baking"],
        "source_quote": "Chocolate Chip Cookies",
        "ingredients": [
            # Volume: 2.25 cup → 540 ml
            {"quantity": "2 1/4 cups", "amount": 2.25, "unit": "cup",
             "item": "all-purpose flour"},
            # Custom unit: 1 stick → 113 g
            {"quantity": "1 stick", "amount": 1, "unit": "stick",
             "item": "butter", "notes": "softened"},
            # Kitchen-spoon stays verbatim
            {"quantity": "1 tsp", "amount": 1, "unit": "teaspoon",
             "item": "vanilla extract"},
            # Descriptive: pint returns None → quantity verbatim
            {"quantity": "a pinch", "amount": None, "unit": None,
             "item": "salt"},
            # Unitless count: pint unknown → quantity verbatim
            {"quantity": "3", "amount": 3, "unit": None,
             "item": "eggs", "notes": "large"},
        ],
        "steps": [
            "Preheat oven to 190°C.",
            "Cream butter and sugar until fluffy.",
            "Bake for 12 minutes.",
        ],
    }


class TestBuildReplicaRecipes:
    def test_recipe_page_created(self, tmp_path, fake_vault):
        replica.build_replica(
            workdir=tmp_path,
            extractions={"recipes": [_basic_recipe()]},
            destinations={"recipes": {"mode": "artifact",
                                       "folder": "22 RECIPES"}},
            vault_matches=None,
            source_basename="cookbook.pdf",
        )
        page = (tmp_path / "global" / "vault-replica"
                / "22 RECIPES" / "Chocolate Chip Cookies.md")
        assert page.exists(), \
            "recipe page must land under 22 RECIPES/"

    def test_metric_quantity_rendered(self, tmp_path, fake_vault):
        replica.build_replica(
            workdir=tmp_path,
            extractions={"recipes": [_basic_recipe()]},
            destinations={"recipes": {"mode": "artifact",
                                       "folder": "22 RECIPES"}},
            vault_matches=None,
            source_basename="cookbook.pdf",
        )
        body = (tmp_path / "global" / "vault-replica"
                / "22 RECIPES" / "Chocolate Chip Cookies.md").read_text()
        # Volume: 2.25 cup → 540 ml
        assert "540 ml all-purpose flour" in body
        # Custom unit: 1 stick → 113 g
        assert "113 g butter" in body
        # Kitchen-spoon stays verbatim
        assert "1 tsp vanilla extract" in body
        # Descriptive falls back to verbatim quantity
        assert "a pinch salt" in body
        # Unitless count falls back to verbatim quantity
        assert "3 eggs" in body

    def test_frontmatter_metadata(self, tmp_path, fake_vault):
        replica.build_replica(
            workdir=tmp_path,
            extractions={"recipes": [_basic_recipe()]},
            destinations={"recipes": {"mode": "artifact",
                                       "folder": "22 RECIPES"}},
            vault_matches=None,
            source_basename="cookbook.pdf",
        )
        body = (tmp_path / "global" / "vault-replica"
                / "22 RECIPES" / "Chocolate Chip Cookies.md").read_text()
        assert "type: recipe" in body
        assert 'title: "Chocolate Chip Cookies"' in body
        assert 'yield: "24 cookies"' in body
        assert 'total_time: "45 min"' in body
        assert "- dessert" in body
        assert "- baking" in body

    def test_steps_numbered(self, tmp_path, fake_vault):
        replica.build_replica(
            workdir=tmp_path,
            extractions={"recipes": [_basic_recipe()]},
            destinations={"recipes": {"mode": "artifact",
                                       "folder": "22 RECIPES"}},
            vault_matches=None,
            source_basename="cookbook.pdf",
        )
        body = (tmp_path / "global" / "vault-replica"
                / "22 RECIPES" / "Chocolate Chip Cookies.md").read_text()
        assert "1. Preheat oven to 190°C." in body
        assert "3. Bake for 12 minutes." in body

    def test_modified_op_when_page_exists(self, tmp_path, fake_vault):
        # Pre-populate the vault with the same-named recipe.
        recipes_dir = fake_vault / "22 RECIPES"
        recipes_dir.mkdir(parents=True)
        (recipes_dir / "Chocolate Chip Cookies.md").write_text(
            "---\ntype: recipe\n---\n\n# Chocolate Chip Cookies\n\nold\n",
            encoding="utf-8",
        )
        result = replica.build_replica(
            workdir=tmp_path,
            extractions={"recipes": [_basic_recipe()]},
            destinations={"recipes": {"mode": "artifact",
                                       "folder": "22 RECIPES"}},
            vault_matches=None,
            source_basename="cookbook.pdf",
        )
        entries = result["entries"]
        assert len(entries) == 1
        assert entries[0]["op"] == "modified"
        assert entries[0]["kind"] == "recipes"
