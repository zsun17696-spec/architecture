# Corpus preflight

Generated: 2026-11-18

SPEC `[EXISTS]` must cite **File** + this table. `chars=0` / `need_ocr=true` files must not enter the full-text ingest flowchart.

| # | File | bytes | sniff | pages | chars_sum | usable_chars | text_layer | need_ocr | ingest_role | notes |
|---|------|------:|-------|------:|----------:|-------------:|:----------:|:--------:|-------------|-------|
| 1 | `atlas-11G101-1.json` | 1681 | json |  | 1014 | 1014 | true | false | experimental-not-acceptance |  |
| 2 | `GB50010-2010.md` | 2195 | md |  | 946 | 946 | true | false | experimental-not-acceptance |  |
| 3 | `GB50010-2024.md` | 2409 | md |  | 1025 | 1025 | true | false | experimental-not-acceptance |  |
| 4 | `GB50204-2015.md` | 884 | md |  | 412 | 412 | true | false | experimental-not-acceptance |  |
| 5 | `GB55008-2021.pdf` | 3986824 | pdf | 26 | 962 | 0 | false | true | scan-page-locate | page extract_text is watermark-only |
| 6 | `GB55008-abolished-mandatory.docx` | 23040 | ole-doc |  | 23040 | 0 | false | false | provenance-only | OLE Compound File (.doc). python-docx cannot read. provenance-only unless parsed as ole. |
| 7 | `JGJ59-2011.md` | 954 | md |  | 444 | 444 | true | false | experimental-not-acceptance |  |
| 8 | `SOURCE.md` | 539 | md |  | 348 | 348 | true | false | provenance-only |  |

## Roles

- `fulltext-ingest-ok`: may enter §5.1 extract → article chunk.
- `scan-page-locate`: page-level chunks only (doc_id + page); no article body.
- `provenance-only`: metadata / official list; not article text.
- `experimental-not-acceptance`: not in manifest for grading.
- `skip-fulltext-ingest`: do not parse as articles.
