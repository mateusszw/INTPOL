#!/usr/bin/env python3
"""Converte PDFs de pdfs/ em Markdown em base/<slug>/README.md e atualiza INDEX.md.

Uso: python3 scripts/convert_pdf.py [--force]
"""
import argparse
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDFS = ROOT / "pdfs"
BASE = ROOT / "base"
INDEX = ROOT / "INDEX.md"


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "documento"


def pages(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    return int(m.group(1)) if m else 0


def extract(pdf: Path) -> str:
    try:
        import pymupdf4llm  # type: ignore
        return pymupdf4llm.to_markdown(str(pdf))
    except ImportError:
        pass
    r = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    # separa páginas (form feed) com uma régua
    return "\n\n---\n\n".join(p.strip("\n") for p in r.stdout.split("\f") if p.strip())


def convert(pdf: Path, force: bool) -> bool:
    slug = slugify(pdf.stem)
    out = BASE / slug / "README.md"
    if out.exists() and not force:
        return False
    text = extract(pdf)
    if len(text.strip()) < 50:
        print(f"AVISO: {pdf.name} quase sem texto (PDF escaneado? precisa de OCR)", file=sys.stderr)
    title = pdf.stem.replace("_", " ").replace("-", " ").strip()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"---\ntitulo: {title}\norigem: pdfs/{pdf.name}\npaginas: {pages(pdf)}\n"
        f"convertido_em: {date.today()}\n---\n\n# {title}\n\n{text}\n",
        encoding="utf-8",
    )
    print(f"OK: {pdf.name} -> {out.relative_to(ROOT)}")
    return True


def write_index():
    rows = []
    for md in sorted(BASE.glob("*/README.md")):
        meta = dict(re.findall(r"^(\w+): (.*)$", md.read_text(encoding="utf-8").split("---")[1], re.M))
        rows.append(f"| [{meta.get('titulo', md.parent.name)}](base/{md.parent.name}/README.md) "
                    f"| `{meta.get('origem', '')}` | {meta.get('paginas', '')} |")
    INDEX.write_text(
        "# Índice da base\n\n| Documento | PDF original | Páginas |\n|---|---|---|\n"
        + "\n".join(rows) + "\n",
        encoding="utf-8",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="reprocessa PDFs já convertidos")
    args = ap.parse_args()
    for pdf in sorted(PDFS.glob("*.pdf")):
        convert(pdf, args.force)
    write_index()


if __name__ == "__main__":
    main()
