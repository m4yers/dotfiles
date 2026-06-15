# Secure-LLM Conventions

Rules for handling external content in agent prompts. Applies whenever a
sub-agent prompt is going to consume content the skill did not itself produce.

## Contents

- [1. When the rule applies](#1-when-the-rule-applies)
- [2. What the rule requires](#2-what-the-rule-requires)
- [3. Trust boundaries](#3-trust-boundaries)
- [4. Canonical scanner and frame](#4-canonical-scanner-and-frame)

## 1. When the rule applies

1. A sub-agent prompt is "external-input bearing" whenever its
   rendered text will contain content the skill itself did not
   produce. The rule fires for any of these sources:

   - Web fetches and web-search results.
   - Ticket / SIM / CR / Slack / email message bodies.
   - Third-party API responses (vDBA, OWLS, AdminDB rows, etc.).
   - File contents read from outside the skill's own scope —
     the user's editor buffer, an attached doc, or an arbitrary
     path the user provided.
   - Content that flowed in from any other external system not
     owned by the skill.

2. If the prompt contains only the user's direct request, the
   skill's own template literals, and outputs from the skill's
   own scripts, the rule does NOT apply, because every byte
   originated from a surface the skill controls.

## 2. What the rule requires

When the rule applies, the rendered prompt MUST inject the secure-llm security
frame so the LLM treats the external content as data, not instructions.

1. Skills MUST add `~/.kiro/skills/home/secure-llm/templates`
   to the template's search path. Dojo already sets this on
   `template_search_paths`, so prompts rendered through dojo's
   `_agent` / `_human` factories get it for free. Standalone
   callers MUST pass the directory as an additional
   `--include-dir` to `template/scripts/render.sh`.

2. The rendered prompt MUST inject the frame at the top of the
   prompt body, above any external content:

       {% raw %}{% include 'security-frame.md.j2' %}{% endraw %}

3. Each block of external content in the prompt MUST be
   wrapped in a clearly labelled fenced section so the LLM
   can tell where the untrusted region begins and ends:

       ## Untrusted source: <source-id>

       ```text
       <body>
       ```

4. Outside fenced regions, the prompt MUST refer to external
   content by reference (path, URL, ticket id) — never
   re-emit it as prose, because re-flowing untrusted bytes
   into the prompt's instruction stream defeats the frame.

## 3. Trust boundaries

1. The security-frame include carries the "treat the source
   as data" instruction. The prompt body MUST additionally
   identify which sections are trusted (skill-controlled)
   and which are not (external content), because the reader
   has to audit that boundary even when the frame is present.

2. When a single prompt mixes trusted and untrusted blocks,
   each untrusted block MUST carry a fenced label per rule
   2.3 — the frame alone is not a substitute for explicit
   labelling.

## 4. Canonical scanner and frame

1. The scanner heuristics, regex catalogue, and the
   security-frame text itself live in
   `~/.kiro/skills/home/secure-llm/SKILL.md`. That skill is
   the single source of truth — skills MUST NOT vendor the
   frame text or the scanner patterns, because forks drift
   from the canonical defence.

2. To extend pattern coverage, edit
   `secure-llm/scripts/security_scan/__init__.py`'s
   `_PATTERNS` list. Other skills compose the scanner and
   the frame; they do not copy them.
