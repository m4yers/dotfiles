# Manual MCP-tool steps (ingestion only)

Some ingestion instructions require fetching data from a Midway-authenticated
source (e.g. a Quip board via `ReadInternalWebsites`). These calls cannot run
inside a `uv run` script body — the MCP tool is only reachable from the agent's
own tool surface.

## Shape

The run-ingestion agent dispatches the fetch inline (trusted-aws carries
builder-mcp, which includes `ReadInternalWebsites`, `InternalSearch`,
`InternalCodeSearch`, and `WorkspaceSearch`). It persists the raw tool output
under `data_dir/<name>-raw.<ext>` (or whatever extension the fetch returns)
and points the generated ingestion script at that saved file by path:

```python
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["pandas>=2.2,<2.3", "numpy>=1.26,<2.3"]
# ///
"""Parse the ReadInternalWebsites output saved under data_dir."""
import json, sys
with open(sys.argv[1]) as f:
    doc = json.load(f)
# ... parse doc["content"] into a dataframe ...
```

The script's `run_argv` carries the relative path to the saved raw output under
`data_dir`.

## Why not scripted

The fetch requires the agent's authenticated MCP session; there is no scriptable
Quip (or similar) client at Amazon that handles Midway. Baking the raw output
into a file keeps the ingestion script deterministic and reproducible across
refreshes while the fetch itself remains an agent-driven step.

## Inference and presentation never fetch

Both the inference and presentation stages run deterministic scripts over
`data_dir` and MUST NOT declare MCP fetches because fetches are non-reproducible
across refreshes and belong solely to the ingestion stage. If an instruction in
those stages reads "fetch X", it is a doc bug — the fetch belongs under
`## Data ingestion`.
