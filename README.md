# INTPOL

Base de informação construída a partir de PDFs.

## Fluxo
1. Adicione os PDFs na pasta [`pdfs/`](pdfs/).
2. Rode `python3 scripts/convert_pdf.py` (requer `poppler-utils`; usa `pymupdf4llm` se instalado).
3. Cada PDF vira `base/<nome>/README.md`; o [`INDEX.md`](INDEX.md) lista todos.
4. Commit e push.

PDFs já convertidos são ignorados; use `--force` para reprocessar. PDFs escaneados precisam de OCR.
