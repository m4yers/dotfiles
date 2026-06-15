'''Compile quintet rules into JMESPath predicates per extractor kind.'''
from __future__ import annotations

SLOTS = ('media', 'form', 'register', 'discipline', 'audience')


def compile(kind: str, rules: list[dict]) -> str | None:
    '''Return a JMESPath predicate for when `kind` should run.

    Returns None when the base (*,*,*,*,*) rule mentions kind (always run).
    Each matching rule contributes one OR-clause; slot constraints AND
    together inside a clause.
    '''
    clauses: list[str] = []
    for rule in rules:
        if kind not in rule['extractors']:
            continue
        slot_clauses = []
        for slot, val in zip(SLOTS, rule['match']):
            if val == '*':
                continue
            slot_clauses.append(
                f'task."extract-classify".quintet.{slot} == \'{val}\''
            )
        if not slot_clauses:
            return None  # base rule — always run
        if len(slot_clauses) == 1:
            clauses.append(slot_clauses[0])
        else:
            clauses.append('(' + ' && '.join(slot_clauses) + ')')
    if not clauses:
        return 'false'
    if len(clauses) == 1:
        return clauses[0]
    return ' || '.join(clauses)
