# Script execution

All stage scripts are self-contained uv scripts with PEP 723
`# /// script` metadata. The host is Amazon Linux 2 (glibc 2.26); no
pandas 3 / numpy ≥ 2.3 wheels exist for that glibc.

## Required PEP 723 header

```python
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["pandas>=2.2,<2.3", "numpy>=1.26,<2.3"]
# ///
```

Pin python explicitly on the run line so uv picks 3.12 (not whatever the host
venv picks):

```bash
uv run -p 3.12 <script>.py <argv...>
```

## cwd

Every stage script runs with `cwd=data_dir`, where `data_dir =
${workdir}/data/`. All intermediate files, raw fetches, and script outputs live
under this directory. Scripts MUST NOT scatter files across `/tmp/` because
co-locating with the task makes failures inspectable and keeps everything
self-contained for replay.

## Outputs

By default, a presentation script emits the Result-subsection body to stdout
and the write-result agent copies that stdout verbatim into the matching
`## <heading>` under `# Result`. A script MAY instead write a file under
`data_dir` and leave stdout empty when its instruction explicitly asks for a
file (rare).

## Prudent regeneration

The stage agents MUST keep existing Appendix scripts as-is when they still match
the instruction and still work. Regenerate ONLY when a script is missing,
mismatched, or buggy. The round-trip hash check in `verify-roundtrip` makes any
accidental regeneration visible immediately: the Appendix diff is the audit
trail.

## Minimality

The run-ingestion, run-inference, and run-presentation agents MUST generate
only what the stage instruction requires. They MUST NOT add helpers,
abstractions, defensive branches, or unused utilities because every unneeded
line widens the round-trip surface and the next refresh has to re-verify it.
