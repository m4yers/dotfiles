'''Placeholder resolution for cmd, vars, and free-form strings.

No skill-side extension. Five built-in placeholders only.
'''
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import jmespath
import yaml

from loom.engine.models import LoomPlan
from loom.engine import store


_PLACEHOLDER_RE = re.compile(r'(?<!\$)\$\{([^}]+)\}')
_WHOLE_PLACEHOLDER_RE = re.compile(r'^\$\{([^}]+)\}$')
_ESCAPE_RE = re.compile(r'\$\$')


def resolve_value(
    value: Any,
    workdir: Path,
    plan: LoomPlan,
    task_id: str | None = None,
) -> Any:
    '''Resolve placeholders in value. Recurse into lists/dicts.'''
    if isinstance(value, str):
        return _resolve_string(value, workdir, plan, task_id)
    if isinstance(value, list):
        return [resolve_value(v, workdir, plan, task_id) for v in value]
    if isinstance(value, dict):
        return {k: resolve_value(v, workdir, plan, task_id) for k, v in value.items()}
    return value


def _resolve_string(
    s: str,
    workdir: Path,
    plan: LoomPlan,
    task_id: str | None,
) -> Any:
    m = _WHOLE_PLACEHOLDER_RE.match(s)
    if m:
        spec = m.group(1)
        if spec.startswith('task:'):
            return _resolve_task_ref(spec, workdir, plan)
    out = _PLACEHOLDER_RE.sub(
        lambda mm: _stringify(_resolve_spec(mm.group(1), workdir, plan, task_id)),
        s,
    )
    return _ESCAPE_RE.sub('$', out)


def _resolve_spec(
    spec: str,
    workdir: Path,
    plan: LoomPlan,
    task_id: str | None,
) -> Any:
    if spec == 'workdir':
        return str(workdir)
    if spec == 'task_workdir':
        if task_id is None:
            return ''
        try:
            return str(store.task_dir(workdir, plan, task_id))
        except KeyError:
            return ''
    if spec == 'global':
        return str(store.global_dir(workdir))
    if spec.startswith('global:'):
        rel = spec[len('global:'):]
        return str(store.global_dir(workdir) / rel)
    if spec.startswith('task_path:'):
        tid = spec[len('task_path:'):]
        try:
            return str(store.task_output_path(workdir, plan, tid))
        except KeyError:
            return ''
    if spec.startswith('task:'):
        return _resolve_task_ref(spec, workdir, plan)
    return '${' + spec + '}'


_TASK_SPEC_RE = re.compile(
    r'^([A-Za-z0-9_\-]+)(?:@([A-Za-z0-9]+))?(?::(.+))?$', re.DOTALL)


def _resolve_task_ref(spec: str, workdir: Path, plan: LoomPlan) -> Any:
    rest = spec[len('task:'):]
    m = _TASK_SPEC_RE.match(rest)
    if not m:
        return None
    tid, sel, expr = m.group(1), m.group(2), m.group(3)
    if sel is not None:
        p = store.iteration_output_path(workdir, plan, tid, sel)
        output = None
        if p is not None and p.exists():
            try:
                output = yaml.safe_load(p.read_text(encoding='utf-8'))
            except Exception:
                output = None
    else:
        output = _load_output_or_none(workdir, plan, tid)
    if output is None:
        return None
    if not expr:
        return output
    try:
        return jmespath.search(expr, output)
    except Exception:
        return None


def _load_output_or_none(workdir: Path, plan: LoomPlan, task_id: str) -> Any:
    try:
        p = store.task_output_path(workdir, plan, task_id)
    except KeyError:
        return None
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def _stringify(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return yaml.safe_dump(value, sort_keys=False, default_flow_style=False).rstrip()
    return str(value)
