# Loom plan visualisation

Rendered via `$LOOM visualise` on the composed plan. Legend: ○ tool · ◆ agent
· ▣ human · ↻ loop.

```
PLAN  live-doc  ·  10 tasks

○  10 publish-output
○  09 commit-vault
○  08 verify-roundtrip
○  07 assemble-doc
○  06 write-result
◆  05 run-presentation
◆  04 run-inference
◆  03 run-ingestion
○  02 load-doc
○  01 ingest-input

legend: ○ tool · ◆ agent · ▣ human · ↻ loop   │ all-dep · ╷ any-dep   when:/↻ inline
```

The pipeline is linear: `ingest-input → load-doc → run-ingestion → run-inference
→ run-presentation → write-result → assemble-doc → verify-roundtrip →
commit-vault → publish-output`.

`create` has no graph — it is a shim subcommand (render scaffold + exec
editor).
