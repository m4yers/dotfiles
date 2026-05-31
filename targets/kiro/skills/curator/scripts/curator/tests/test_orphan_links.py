'''Tests for _name_matches_any_vault_page input shapes.

Covers the four shapes the orphan-link detector must accept:

- Plain wikilink names (``Csmith``).
- Path-style wikilink targets (``10 SOURCES/Articles/Foo``).
- Path-style targets with a redundant ``.md`` suffix.
- Absolute filesystem paths under the vault root (the form
  written into ``sources:`` frontmatter by the synthesis hub
  when the agent emits the absolute path of the source page).

A previous version doubled the ``.md`` suffix and treated
absolute paths as vault-relative, so a real vault page was
falsely reported as an orphan link in the gate report.
'''
from __future__ import annotations

from pathlib import Path

import pytest

from curator.vault import replica


@pytest.fixture
def fake_vault(monkeypatch, tmp_path):
    '''Point VAULT_ROOT at a tmp dir and pre-populate canonical
    artifact folders with a couple of sample pages.'''
    vault_root = tmp_path / "vault"
    (vault_root / "12 KEYWORDS").mkdir(parents=True)
    (vault_root / "13 PEOPLE").mkdir(parents=True)
    (vault_root / "10 SOURCES" / "Articles").mkdir(parents=True)

    (vault_root / "13 PEOPLE" / "John Regehr.md").write_text("x")
    (vault_root / "12 KEYWORDS" / "Executable Oracles.md").write_text("x")
    (vault_root / "10 SOURCES" / "Articles" / "Foo Bar.md").write_text("x")

    # Patch the module-level VAULT_ROOT used by the function.
    from curator.vault import config as vcfg
    monkeypatch.setattr(vcfg, "VAULT_ROOT", vault_root)
    monkeypatch.setattr(replica, "VAULT_ROOT", vault_root,
                        raising=False)

    return vault_root


def test_plain_name_matches_flat_folder(fake_vault):
    assert replica._name_matches_any_vault_page("John Regehr") is True


def test_plain_name_matches_keywords_folder(fake_vault):
    assert (
        replica._name_matches_any_vault_page("Executable Oracles") is True
    )


def test_plain_name_unknown(fake_vault):
    assert (
        replica._name_matches_any_vault_page("Nonexistent Foo") is False
    )


def test_path_style_target_matches_sources_subfolder(fake_vault):
    # No ``.md`` suffix — canonical wikilink shape.
    assert replica._name_matches_any_vault_page(
        "10 SOURCES/Articles/Foo Bar"
    ) is True


def test_path_style_target_with_redundant_md_suffix(fake_vault):
    # The caller named the file with its extension. The detector
    # must drop ``.md`` before composing ``<name>.md`` — otherwise
    # it probes ``Foo Bar.md.md`` and reports a false orphan.
    assert replica._name_matches_any_vault_page(
        "10 SOURCES/Articles/Foo Bar.md"
    ) is True


def test_path_style_unknown(fake_vault):
    assert replica._name_matches_any_vault_page(
        "10 SOURCES/Articles/Nonexistent"
    ) is False


def test_absolute_vault_path_with_md_suffix(fake_vault):
    # Synthesis frontmatter ``sources:`` written as a YAML scalar
    # surfaces here as an absolute filesystem path. The detector
    # must strip the VAULT_ROOT prefix and then the ``.md`` suffix.
    abs_path = f"{fake_vault}/10 SOURCES/Articles/Foo Bar.md"
    assert replica._name_matches_any_vault_page(abs_path) is True


def test_absolute_vault_path_unknown(fake_vault):
    abs_path = f"{fake_vault}/10 SOURCES/Articles/Nonexistent.md"
    assert replica._name_matches_any_vault_page(abs_path) is False
