# hello-graph

Reference skill for loom v2. A root graph with all task kinds — tool
(`greet-user`, `finalise`, `aggregate-summaries`), agent (`summarise`), human
(`confirm`), and a `tool.sh` shell shim (`banner-sh`, exercising the argv-based
dispatch path documented in `../guide.md` §2) — plus a child skill tree
(`child/loom/`) embedded TWICE via `kind: subgraph` entries (`child-lint`
lints the greeting, `child-relint` re-lints after the human gate), and a
revise loop: `confirm` is a latch back onto `summarise` (`fuel: 3`, `while_`
the human's decision is not `accept`).

The graph also exercises ref-based task instancing (see `../guide.md` §11):
two additional agent entries — `summarise-quick` and `summarise-formal` —
share the `summarise/` folder via `ref: summarise`, each carrying its own
`input:` mapping and workdir. `aggregate-summaries` (a tool) reads both
instances' outputs, and `finalise` depends on it via `depends_on_all`.

Walked step by step in `references/guide.md`; executed by the test suite.

Run it:

```bash
LOOM=~/.kiro/skills/home/loomv2/scripts/loom.sh
$LOOM runtime init /tmp/hello-run --loom-root references/hello-graph/loom
$LOOM runtime next /tmp/hello-run
```
