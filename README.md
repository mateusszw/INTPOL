# INTPOL

Base de informação construída a partir de PDFs.

## Fluxo
1. Adicione os PDFs na pasta [`pdfs/`](pdfs/).
2. Rode `python3 scripts/convert_pdf.py` (requer `poppler-utils`; usa `pymupdf4llm` se instalado).
3. Cada PDF vira `base/<nome>/README.md`; o [`INDEX.md`](INDEX.md) lista todos.
4. Commit e push.

PDFs já convertidos são ignorados; use `--force` para reprocessar. PDFs escaneados precisam de OCR.

## Vídeos do YouTube
`python3 scripts/youtube_transcripts.py --limit 3` (requer `pip install yt-dlp`) baixa as legendas dos vídeos mais recentes
do canal [@KIMPAIM](https://www.youtube.com/@KIMPAIM/videos) para `youtube/kim-paim/<ano>/<data>-<id>.md`.
Cada parágrafo começa com o horário linkado ao ponto do vídeo, para citar a fonte. `youtube/kim-paim/videos.csv`
guarda o estado de cada vídeo e `youtube/kim-paim/INDEX.md` lista todos. Vídeos já baixados são pulados;
`--all` faz a importação completa. O workflow "Transcrições do YouTube" roda o mesmo script no GitHub Actions.
