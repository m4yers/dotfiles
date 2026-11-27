"""Top-level typer app wiring every subcommand.

YAML on stdout; non-zero exit on error. Imports the per-area
submodules, not reverse.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml

from vault import agents as agents_mod
from vault import diff_fm as diff_fm_mod
from vault import notes as notes_mod
from vault import obsidian as obsidian_mod
from vault import validate as validate_mod
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
    except (ValueError, OSError) as e:
        fail(str(e))


# ── vault subcommands ──────────────────────────────────


def cli_match(
    keywords: Annotated[Optional[str], typer.Option(
        "--keywords",
        help="Path to a YAML file shaped "
             "{keywords: [{name: <str>}, ...]}.")] = None,
    people: Annotated[Optional[str], typer.Option(
        "--people",
        help="Path to a YAML file shaped "
             "{people: [{name: <str>}, ...]}.")] = None,
    models: Annotated[Optional[str], typer.Option(
        "--models",
        help="Path to a YAML file shaped "
             "{models: [{name: <str>}, ...]}.")] = None,
) -> None:
    """Match extracted items against existing vault pages.

    Each input file is a YAML mapping keyed by its kind holding a
    list of ``{name}`` items; a missing file, kind key, or ``name``
    field fails the command. Emits ``{<kind>: [{name, match}],
    skipped: [{path, reason}]}``; ``skipped`` lists pages whose
    frontmatter did not parse, so their aliases were not matched."""
    inputs: dict[str, str] = {}
    if keywords: inputs["keywords"] = keywords
    if people:   inputs["people"]   = people
    if models:   inputs["models"]   = models
    if not inputs:
        fail("at least one of --keywords / --people / --models "
             "is required")
    try:
        emit(build_match(inputs))
    except ValueError as e:
        fail(str(e))


def cli_read(
    vault_path: Annotated[str, typer.Argument(
        help="Vault-relative path to the note.")],
) -> None:
    """Read a note; emit {frontmatter, body}."""
    try:
        emit(notes_mod.read(vault_path))
    except FileNotFoundError as e:
        fail(f"not found: {e}")
    except ValueError as e:
        fail(str(e))


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
    zettel: Annotated[bool, typer.Option(
        "--zettel",
        help="Allow writing under 20 ZETTELKASTEN/. Pass only when "
             "the user named a zettel in the request.")] = False,
) -> None:
    """Create or modify a note. ``--dry-run`` returns the preview.

    ``20 ZETTELKASTEN/`` is blocked unless ``--zettel`` is passed;
    the orchestrator passes it only when the user named a zettel
    in the request.
    """
    fm = _load_frontmatter_arg(frontmatter)
    if body_file == "-":
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
            allow_zettel=zettel,
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
    """List .md files directly under a vault folder.

    Emits a list of ``{name, path, size}`` records: ``name`` is the
    file stem (note title), ``path`` the vault-relative path with
    extension, ``size`` the byte count. Fails with "unknown vault
    folder" when the folder does not exist."""
    try:
        emit(notes_mod.list_folder(folder))
    except ValueError as e:
        fail(str(e))


def cli_validate(
    vault_path: Annotated[str, typer.Argument(
        help="Vault-relative path of the note (existing or proposed).")],
    frontmatter: Annotated[Optional[str], typer.Option(
        "--frontmatter",
        help="JSON object to validate instead of the note on disk "
             "(preview-time check).")] = None,
    require: Annotated[Optional[list[str]], typer.Option(
        "--require",
        help="Extra required key from the Operations entry. "
             "Repeat for multiple.")] = None,
) -> None:
    """Check frontmatter against the folder's required keys and
    shape rules (REQUIRED_FRONTMATTER, DATE_KEYS in config.py).

    Emits ``{ok, path, folder, required, missing, errors}`` and
    exits 1 when ``ok`` is false, so the result is readable from
    the exit code alone."""
    fm = _load_frontmatter_arg(frontmatter) if frontmatter else None
    try:
        result = validate_mod.validate(
            vault_path, frontmatter=fm, require=tuple(require or ()))
    except FileNotFoundError as e:
        fail(f"not found: {e}")
        return
    except ValueError as e:
        fail(str(e))
        return
    emit(result)
    if not result["ok"]:
        raise typer.Exit(code=1)


def cli_search(
    query: Annotated[str, typer.Argument(
        help="Query string (case-insensitive literal substring).")],
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
    try:
        emit(notes_mod.search(query, folders=folders,
                                max_results=max_results))
    except (ValueError, RuntimeError) as e:
        fail(str(e))


def _load_baseline_file(path: str) -> dict:
    """Load the baseline frontmatter from a saved ``vault read``
    envelope (``{frontmatter, body}``), the one shape the Workflow
    captures before an edit. Any other shape fails, so a note whose
    own frontmatter happens to carry ``frontmatter`` or ``current``
    keys can never be misread as an envelope.
    """
    try:
        raw = (sys.stdin.read() if path == "-"
               else Path(path).read_text(encoding="utf-8"))
        value = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as e:
        fail(f"--baseline unreadable: {e}")
        return {}  # unreachable
    if (not isinstance(value, dict)
            or set(value) != {"frontmatter", "body"}
            or not isinstance(value["frontmatter"], dict)):
        fail("--baseline must be a saved `vault read` envelope "
             "{frontmatter, body}")
        return {}
    return value["frontmatter"]


def cli_diff_fm(
    vault_path: Annotated[str, typer.Argument(
        help="Vault-relative path to the note.")],
    baseline: Annotated[str, typer.Option(
        "--baseline",
        help="Path to the saved `vault read` output "
             "({frontmatter, body}) captured before the edit. "
             "'-' reads stdin.")],
) -> None:
    """Compare current frontmatter against a required baseline."""
    baseline_obj = _load_baseline_file(baseline)
    try:
        emit(diff_fm_mod.diff_fm(vault_path, baseline=baseline_obj))
    except FileNotFoundError as e:
        fail(f"not found: {e}")
    except ValueError as e:
        fail(str(e))


# ── vault obsidian subcommands ─────────────────────────


def cli_obsidian_move(
    src: Annotated[str, typer.Argument(
        help="Vault-relative source path.")],
    dst: Annotated[str, typer.Argument(
        help="Vault-relative destination path.")],
) -> None:
    """Move via the Obsidian CLI (rewrites wikilinks). Emits
    {op, src, dst, obsidian_rewrote, fm_diff}; see obsidian.move."""
    try:
        emit(obsidian_mod.move(src, dst))
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        fail(str(e))


def cli_obsidian_rename(
    src: Annotated[str, typer.Argument(
        help="Vault-relative source path.")],
    new_name: Annotated[str, typer.Argument(
        help="New filename (keep extension).")],
) -> None:
    """Rename via the Obsidian CLI (rewrites wikilinks). Emits
    {op, src, dst, obsidian_rewrote, fm_diff}; see obsidian.rename."""
    try:
        emit(obsidian_mod.rename(src, new_name))
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        fail(str(e))


def cli_obsidian_delete(
    path: Annotated[str, typer.Argument(
        help="Vault-relative path to delete.")],
) -> None:
    """Delete via the Obsidian CLI (moves the note to the trash).
    Emits {op, path, obsidian_rewrote}; see obsidian.delete."""
    try:
        emit(obsidian_mod.delete(path))
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        fail(str(e))


# ── app assembly ───────────────────────────────────────


obsidian_app = typer.Typer(
    help="Obsidian CLI move / rename / delete.",
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
vault_app.command("validate")(cli_validate)
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
