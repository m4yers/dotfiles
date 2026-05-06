# Manual Checks

Cross-skill checks that require reasoning across multiple skills. These cannot
be delegated to per-reference sub-agents because they need the full skill index
to compare triggers, functionality, and naming.

| Check                      | What to verify                        |
| -------------------------- | ------------------------------------- |
| Trigger phrase uniqueness  | No overlap with other skill triggers  |
| Functionality uniqueness   | No overlap in operations/tools/output |
| Negative trigger phrases   | Present if scope overlaps with others |
| Reference file focus       | Each file covers one topic            |
| Repeatable actions         | Repeatable deterministic actions      |
|                            | are scripts, not prose instructions   |
|                            | the agent re-interprets each time.    |
|                            | If the action does not require LLM    |
|                            | reasoning, it MUST be a script        |
| Missing oracles            | Steps with verifiable outcomes have   |
|                            | automated oracle sub-steps. If the    |
|                            | outcome can be checked without LLM    |
|                            | reasoning (JSON valid, tests pass,    |
|                            | lint clean), it MUST have an oracle   |
|                            | — not LLM eyeballing. Exclude         |
|                            | file/dir creation by scripts: the     |
|                            | script's non-zero exit already        |
|                            | enforces it.                          |
| Positive framing           | Constraints prefer positive wording   |
|                            | over negative phrasing where possible |
| Magic constants in scripts | Hardcoded values have justifying      |
|                            | comments explaining why that value    |
|                            | was chosen                            |
| Gameable success criteria  | Success criteria that reference       |
|                            | measurable outcomes (test count,      |
|                            | coverage, lint clean) have anti-      |
|                            | gaming guards preventing the LLM      |
|                            | from trivially satisfying them        |
|                            | (e.g. deleting tests, writing no-op   |
|                            | tests, hard-coding expected values)   |
| Reinvention in scripts     | Scripts MUST NOT reimplement          |
|                            | functionality available in Python     |
|                            | stdlib modules (pathlib, shutil,      |
|                            | textwrap, json, argparse) or          |
|                            | standard Linux programs (find, grep,  |
|                            | sort, jq, sed) because custom code    |
|                            | adds maintenance burden and bugs.     |
|                            | Flag and suggest the existing tool    |
| Pipeline handoff schemas   | When one script's output file is      |
|                            | consumed by another script (data      |
|                            | pipeline), the producer's schema MUST |
|                            | match the consumer's expected input.  |
|                            | Mismatches force the agent to write   |
|                            | ad-hoc glue scripts at runtime.       |
|                            | Check: for each workflow step that    |
|                            | invokes script A producing a file and |
|                            | a later step invokes script B reading |
|                            | that file, verify B's argparse/input  |
|                            | schema accepts A's output shape with  |
|                            | no remap, rename, or projection.      |
|                            | Flag if the SKILL.md requires the     |
|                            | agent to transform between steps.     |
| Env var propagation        | Scripts that set env vars in the      |
|                            | caller's shell MUST print shell       |
|                            | assignments to stdout and be invoked  |
|                            | via `eval "$(script)"` because        |
|                            | subprocesses cannot mutate the        |
|                            | parent environment (see               |
|                            | script-conventions.md § Env Var       |
|                            | Propagation). Check: each script      |
|                            | invoked via `eval` in SKILL.md has    |
|                            | a docstring or --help output          |
|                            | enumerating every VAR it prints.      |
|                            | Check: SKILL.md code blocks that      |
|                            | rely on a propagated VAR either call  |
|                            | the producer in the same block or     |
|                            | re-eval it at the top. Flag scripts   |
|                            | that use `export VAR=...` internally  |
|                            | expecting the caller to inherit it,   |
|                            | or scripts that print JSON while      |
|                            | being consumed via `eval`.            |
| Script re-narration        | Sub-step prose MUST NOT restate what  |
|                            | a script does internally (algorithm,  |
|                            | edge cases, return values). A         |
|                            | one-line purpose is fine; detailed    |
|                            | re-explanation is not. The agent      |
|                            | reads the script directly when it     |
|                            | needs more than the result. Flag      |
|                            | prose paragraphs that duplicate       |
|                            | information available from the        |
|                            | script's --help / docstring or        |
|                            | describe internal behavior the        |
|                            | caller does not act on (see           |
|                            | workflow-conventions.md § Step Rules).|
| Prose script invocations   | Script invocations MUST appear as     |
|                            | actual commands in fenced bash        |
|                            | blocks, not as prose like             |
|                            | `run reporter.sh strikeout and        |
|                            | reload diffs`. Prose invocations      |
|                            | hide arguments, force the agent to    |
|                            | synthesize the command each run, and  |
|                            | drift from the real CLI. Flag any     |
|                            | sentence referencing a script by      |
|                            | name (`tool.py ...`, `foo.sh ...`)    |
|                            | outside a code block. Exception:      |
|                            | sibling skills named by skill name    |
|                            | (e.g. `build with <build-skill>`)     |
|                            | where the command lives in that       |
|                            | skill's SKILL.md.                     |
| Template rendering         | Any text produced from a              |
|                            | parameterized template (sub-agent     |
|                            | prompts, config files, generated      |
|                            | markdown, report fragments) MUST be   |
|                            | rendered via                          |
|                            | `$SKILLS/home/template/scripts/       |
|                            | render.sh`. Flag skills that vendor   |
|                            | `jinja2`, import `jinja2` directly    |
|                            | from a per-skill script, use          |
|                            | `str.format`/`%s`/f-string on read    |
|                            | template files, or pipe through       |
|                            | `sed`/`envsubst` for substitution.    |
|                            | Templates belong under                |
|                            | `<skill>/templates/<name>.j2` and     |
|                            | callers invoke `render.sh` with       |
|                            | `--var k=v` (or `--json-vars`).       |
