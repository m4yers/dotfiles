# Trigger Phrase Hygiene

**Code:** TRG
**Applies:** always

Routing rules for skill descriptions. Supplements `authoring.md`.

## 1. Trigger Phrase Hygiene

1. (rule: TRG-1-1, severity: 80) New or updated skill descriptions MUST be
   checked against other skills' descriptions for overlapping trigger words.
2. (rule: TRG-1-2, severity: 60) Each skill SHOULD claim at least 2-3 unique
   trigger phrases that no other skill uses.
3. (rule: TRG-1-3, severity: 80) When two skills share a trigger domain, both
   descriptions MUST state the routing criteria explicitly.
4. (rule: TRG-1-4, severity: 80) When scope overlaps, descriptions MUST include
   a negative trigger — e.g., "Do NOT use for X (use Y skill instead)" — as in
   debug-symbolize vs fast-debug, or owls/fleet-sweep vs rca.
