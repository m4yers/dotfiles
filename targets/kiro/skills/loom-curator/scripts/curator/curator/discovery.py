'''Walk templates/extractors/ to discover extractor kinds.'''
from __future__ import annotations

from pathlib import Path


def list_extractor_kinds(templates_root: Path) -> list[str]:
    '''Return sorted extractor kinds found under templates_root/extractors/.

    A directory qualifies if it has both extractor.j2 and judge.j2.
    Directories starting with _ are skipped.
    '''
    extractors_dir = Path(templates_root) / 'extractors'
    out = []
    for child in sorted(extractors_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith('_'):
            continue
        if not (child / 'extractor.j2').exists():
            continue
        if not (child / 'judge.j2').exists():
            continue
        out.append(child.name)
    return out
