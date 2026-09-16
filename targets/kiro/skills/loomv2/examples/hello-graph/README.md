# hello-graph

Reference skill for loom v2. A root graph with all task kinds — tool
(`greet-user`, `finalise`), agent (`summarise`), human (`confirm`) — plus a
child skill tree (`child/loom/`) embedded TWICE via `kind: subgraph` entries
(`child-lint` lints the greeting, `child-relint` re-lints after the human
gate), and a revise loop: `confirm` is a latch back onto `summarise`
(`fuel: 3`, `while_` the human's decision is not `accept`).
Walked step by step in `references/guide.md`; executed by the test suite.

Run it:

```bash
LOOM=~/.kiro/skills/home/loomv2/scripts/loom.sh
$LOOM runtime init /tmp/hello-run --loom-root examples/hello-graph/loom
$LOOM runtime next /tmp/hello-run
```
