"""Top-level typer app wiring every subcommand.

YAML on stdout; non-zero exit on error. Imports the per-area
submodules, not reverse.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from vault import agents as agents_mod
from vault import diff_fm as diff_fm_mod
from vault import notes as notes_mod
from vault import obsidian as obsidian_mod
from vault.config import VAULT_SEARCH_MAX_RESULTS
from vault.match import build_match
from vault.source import app as source_app
from vault.utils import emit, fail


# ── top-level commands ─────────────────────────────────


def cli_agents(
    folders: Annotated[list[str], typer.Argument(
        help="Top-level folder names whose AGENTS.md to include.")],
) -> None:
    """Print vault-root AGENTS.md plus each named folder's
    AGENTS.md as one YAML envelope."""
    try:
        emit(agents_mod.load_agents(folders))
    except ValueError as e:
        fail(str(e))


# ── vault subcommands ──────────────────────────────────


def cli_match(
    keywords: Annotated[Optional[str], typer.Option(
        "--keywords", help="Path to keywords/output.yaml")] = None,
    people: Annotated[Optional[str], typer.Option(
        "--people", help="Path to people/output.yaml")] = None,
    models: Annotated[Optional[str], typer.Option(
        "--models", help="Path to models/output.yaml")] = None,
) -> None:
    """Match extracted items against existing vault pages."""
    inputs: dict[str, str] = {}
    if keywords: inputs["keywords"] = keywords
    if people:   inputs["people"]   = people
    if models:   inputs["models"]   = models
    if not inputs:
        fail("at least one of --keywords / --people / --models "
             "is required")
    emit(build_match(inputs))


def cli_read(
    vault_path: Annotated[str, typer.Argument(
        help="Vault-relative path to the note.")],
) -> None:
    """Read a note; emit {frontmatter, body}."""
    try:
        emit(notes_mod.read(vault_path))
    except FileNotFoundError as e:
        fail(f"not found: {e}")


def _load_frontmatter_arg(raw: str | None) -> dict:
    if raw is None:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as e:
        fail(f"--frontmatter is not valid JSON: {e}")
        return {}  # unreachable
    if not isinstance(value, dict):
        fail("--frontmatter must be a JSON object")
        return {}
    return value


def cli_write(
    vault_path: Annotated[str, typer.Argument(
        help="Vault-relative path to the note.")],
    frontmatter: Annotated[Optional[str], typer.Option(
        "--frontmatter",
        help="JSON object for the frontmatter.")] = None,
    body_file: Annotated[Optional[str], typer.Option(
        "--body-file",
        help="Path to a file holding the note body. "
             "'-' reads stdin.")] = None,
    dry_run: Annotated[bool, typer.Option(
        "--dry-run",
        help="Return the diff without writing.")] = False,
) -> None:
    """Create or modify a note. ``--dry-run`` returns the preview.

    The zettel exception (``20 ZETTELKASTEN/`` is agent-writable
    only when the user named a zettel in the request) is enforced
    procedurally by the orchestrator, not by this shim.
    """
    fm = _load_frontmatter_arg(frontmatter)
    if body_file == "-":
        import sys
        body = sys.stdin.read()
    elif body_file is None:
        body = ""
    else:
        try:
            body = Path(body_file).read_text(encoding="utf-8")
        except OSError as e:
            fail(f"--body-file unreadable: {e}")
            return

    try:
        result = notes_mod.write(
            vault_path, fm, body,
            dry_run=dry_run,
        )
    except PermissionError as e:
        fail(f"not writable: {e}")
        return
    except ValueError as e:
        fail(str(e))
        return
    emit(result)


def cli_list(
    folder: Annotated[str, typer.Argument(
        help="Top-level vault folder to list.")],
) -> None:
    """List .md files directly under a vault folder."""
    emit(notes_mod.list_folder(folder))


def cli_search(
    query: Annotated[str, typer.Argument(
        help="Query string (case-insensitive substring).")],
    folders: Annotated[Optional[list[str]], typer.Option(
        "--folder",
        help="Restrict search to this top-level folder. "
             "Repeat for multiple.")] = None,
    max_results: Annotated[int, typer.Option(
        "--max-results",
        help="Cap on total hits. See VAULT_SEARCH_MAX_RESULTS "
             "in config.py for the rationale.")] = VAULT_SEARCH_MAX_RESULTS,
) -> None:
    """ripgrep over the vault, scoped to one or more folders."""
    emit(notes_mod.search(query, folders=folders,
                            max_results=max_results))


def cli_diff_fm(
    vault_path: Annotated[str, typer.Argument(
        help="Vault-relative path to the note.")],
    baseline: Annotated[Optional[str], typer.Option(
        "--baseline",
        help="JSON object for the baseline frontmatter.")] = None,
) -> None:
    """Compare current frontmatter against a baseline."""
    baseline_obj = _load_frontmatter_arg(baseline) if baseline else None
    try:
        emit(diff_fm_mod.diff_fm(vault_path, baseline=baseline_obj))
    except FileNotFoundError as e:
        fail(f"not found: {e}")


# ── vault obsidian subcommands ─────────────────────────


def cli_obsidian_move(
    src: Annotated[str, typer.Argument(
        help="Vault-relative source path.")],
    dst: Annotated[str, typer.Argument(
        help="Vault-relative destination path.")],
) -> None:
    """Move via Obsidian URL scheme (rewrites wikilinks)."""
    try:
        emit(obsidian_mod.move(src, dst))
    except (FileNotFoundError, RuntimeError) as e:
        fail(str(e))


def cli_obsidian_rename(
    src: Annotated[str, typer.Argument(
        help="Vault-relative source path.")],
    new_name: Annotated[str, typer.Argument(
        help="New filename (keep extension).")],
) -> None:
    """Rename via Obsidian URL scheme (rewrites wikilinks)."""
    try:
        emit(obsidian_mod.rename(src, new_name))
    except (FileNotFoundError, RuntimeError) as e:
        fail(str(e))


def cli_obsidian_delete(
    path: Annotated[str, typer.Argument(
        help="Vault-relative path to delete.")],
) -> None:
    """Delete via Obsidian URL scheme (removes wikilinks)."""
    try:
        emit(obsidian_mod.delete(path))
    except (FileNotFoundError, RuntimeError) as e:
        fail(str(e))


# ── app assembly ───────────────────────────────────────


obsidian_app = typer.Typer(
    help="Obsidian URL-scheme move / rename / delete.",
    no_args_is_help=True,
)
obsidian_app.command("move")(cli_obsidian_move)
obsidian_app.command("rename")(cli_obsidian_rename)
obsidian_app.command("delete")(cli_obsidian_delete)


vault_app = typer.Typer(
    help="Vault read/write/list/search + obsidian ops.",
    no_args_is_help=True,
)
vault_app.command("match")(cli_match)
vault_app.command("read")(cli_read)
vault_app.command("write")(cli_write)
vault_app.command("list")(cli_list)
vault_app.command("search")(cli_search)
vault_app.command("diff-fm")(cli_diff_fm)
vault_app.add_typer(obsidian_app, name="obsidian")


app = typer.Typer(
    help="Vault — agents, source, vault.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
app.command("agents")(cli_agents)
app.add_typer(source_app, name="source")
app.add_typer(vault_app, name="vault")
