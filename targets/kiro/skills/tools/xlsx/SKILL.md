---
name: xlsx
description: Read and parse .xlsx spreadsheet attachments from tickets. Use when the user needs to extract data from Excel files attached to SIM/Taskei tickets.
---

# XLSX Skill

Read `.xlsx` files using openpyxl. Primarily used to parse
spreadsheet attachments from SIM/Taskei tickets (e.g.,
customer-provided query results, refresh histories).

## Usage

```bash
uv run \
  --python 3.12 \
  --project ~/.kiro/skills/tools/xlsx/scripts \
  python ~/.kiro/skills/tools/xlsx/scripts/read-xlsx.py \
  /path/to/file.xlsx
```

Output: TSV to stdout, one sheet at a time, with sheet name headers. Optional
second argument filters to a single sheet.

## Inline Usage

For ad-hoc parsing in a Python snippet:

```python
from openpyxl import load_workbook
wb = load_workbook('/path/to/file.xlsx', data_only=True)
for sheet in wb.sheetnames:
    ws = wb[sheet]
    for row in ws.iter_rows(values_only=True):
        print('\t'.join(
            str(c) if c is not None else '' for c in row
        ))
```

## Constraints

- You MUST use `--python 3.12` with uv to ensure a
  consistent Python version across all skills
- You MUST use `data_only=True` when reading because we only need computed
  values, not formulas
- You MUST NOT use `data_only=True` when saving/editing because formulas will
  be permanently lost
- You SHOULD prefer `uv run` because it manages the openpyxl dependency
  explicitly
- Cell indices are 1-based in openpyxl (row=1, column=1 = A1)


## Completion

| Status               | Criteria                             |
|----------------------|--------------------------------------|
| `DONE`               | Spreadsheet data extracted and shown |
| `DONE_WITH_CONCERNS` | Data extracted but some sheets empty |
|                      | or formatting unexpected             |
| `BLOCKED`            | File not found or parse error        |
| `NEEDS_CONTEXT`      | File path not provided               |
