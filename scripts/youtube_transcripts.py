#!/usr/bin/env python3
"""Baixa as transcrições (legendas) dos vídeos de um canal do YouTube para youtube/<canal>/.

Cada vídeo vira youtube/<canal>/<ano>/<data>-<id>.md, com frontmatter e a transcrição em
parágrafos de ~1 minuto, cada um com o horário linkado ao ponto do vídeo (para citar a fonte).
O arquivo youtube/<canal>/videos.csv guarda o estado de todos os vídeos; o INDEX.md é gerado dele.
Vídeos já baixados são pulados, então o script pode ser interrompido e rodado de novo.

Uso:
  python3 scripts/youtube_transcripts.py --limit 3          # 3 vídeos mais recentes ainda não baixados
  python3 scripts/youtube_transcripts.py --all --sleep 8     # importação completa (retomável)
  python3 scripts/youtube_transcripts.py --ids ID1 ID2       # vídeos específicos

Em servidores (GitHub Actions) o YouTube pede login ("confirm you're not a bot"): rode no seu
computador ou passe --cookies cookies.txt de uma conta secundária.

Requer: pip install yt-dlp
"""
import argparse
import csv
import html
import re
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = ["pt-orig", "pt", "pt-BR"]
CSV_FIELDS = ["video_id", "data", "titulo", "duracao", "legenda", "status", "arquivo"]


def hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def parse_vtt(text: str):
    """Devolve [(início_em_segundos, linha)] sem as repetições das legendas automáticas."""
    out, prev, start = [], "", None
    for line in text.splitlines():
        m = re.match(r"(\d+):(\d\d):(\d\d)\.\d+\s+-->", line)
        if m:
            start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            continue
        if start is None:  # cabeçalho WEBVTT
            continue
        line = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
        # legendas automáticas repetem a linha anterior no cue seguinte
        if not line or line == prev:
            continue
        out.append((start, line))
        prev = line
    return out


def paragraphs(lines, video_id: str, span: int = 60) -> str:
    paras, cur, cur_start = [], [], None
    for start, line in lines:
        if cur_start is None:
            cur_start = start
        cur.append(line)
        elapsed = start - cur_start
        if (elapsed >= span and re.search(r"[.?!]$", line)) or elapsed >= span * 2:
            paras.append((cur_start, " ".join(cur)))
            cur, cur_start = [], None
    if cur:
        paras.append((cur_start, " ".join(cur)))
    return "\n\n".join(f"[{hms(t)}](https://youtu.be/{video_id}?t={t}) {' '.join(p.split())}" for t, p in paras)


COOKIES = None  # arquivo cookies.txt (formato Netscape), via --cookies


def ydl(opts=None):
    import yt_dlp  # type: ignore
    base = {"quiet": True, "no_warnings": True, "ignoreerrors": False}
    if COOKIES:
        base["cookiefile"] = COOKIES
    return yt_dlp.YoutubeDL({**base, **(opts or {})})


def list_channel(url: str):
    """IDs do canal na ordem da página de vídeos (mais recente primeiro)."""
    with ydl({"extract_flat": "in_playlist"}) as y:
        info = y.extract_info(url, download=False)
    return [e["id"] for e in info.get("entries") or [] if e and e.get("id")]


def fetch(video_id: str, tmp: Path):
    """Metadados + caminho do .vtt baixado (ou None) + tipo de legenda."""
    with ydl({"skip_download": True}) as y:
        info = y.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    manual = [l for l in LANGS if l in (info.get("subtitles") or {})]
    auto = [l for l in LANGS if l in (info.get("automatic_captions") or {})]
    kind, langs = ("manual", manual[:1]) if manual else ("automatica", auto[:1]) if auto else (None, [])
    vtt = None
    if langs:
        opts = {"skip_download": True, "subtitlesformat": "vtt", "subtitleslangs": langs,
                "outtmpl": str(tmp / "%(id)s.%(ext)s"),
                "writesubtitles": kind == "manual", "writeautomaticsub": kind == "automatica"}
        with ydl(opts) as y:
            y.download([f"https://www.youtube.com/watch?v={video_id}"])
        vtt = next(tmp.glob(f"{video_id}*.vtt"), None)
    return info, vtt, kind


def write_video(out_dir: Path, channel: str, info: dict, vtt: Path, kind: str) -> Path:
    vid = info["id"]
    d = info.get("upload_date") or "00000000"
    day = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    path = out_dir / d[:4] / f"{day}-{vid}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    title = info.get("title", "").replace('"', "'")
    body = paragraphs(parse_vtt(vtt.read_text(encoding="utf-8")), vid)
    path.write_text(
        f'---\nvideo_id: {vid}\ntitulo: "{title}"\ndata: {day}\nurl: https://www.youtube.com/watch?v={vid}\n'
        f"duracao: {hms(info.get('duration') or 0)}\ncanal: {channel}\nlegenda: {kind}\n"
        f"transcrito_em: {date.today()}\n---\n\n# {info.get('title', vid)}\n\n"
        f"{day} · {hms(info.get('duration') or 0)} · https://www.youtube.com/watch?v={vid}\n\n"
        f"## Descrição\n\n{(info.get('description') or '').strip()}\n\n## Transcrição\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def load_csv(p: Path):
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as f:
        return {r["video_id"]: r for r in csv.DictReader(f)}


def save(out_dir: Path, rows: dict, channel: str):
    ordered = sorted(rows.values(), key=lambda r: (r["data"], r["video_id"]), reverse=True)
    with (out_dir / "videos.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(ordered)
    lines = [f"# {channel}: transcrições\n",
             f"{sum(r['status'] == 'ok' for r in ordered)} vídeos transcritos, "
             f"{sum(r['status'] == 'sem_legenda' for r in ordered)} sem legenda.\n",
             "| Data | Vídeo | Duração | Legenda |", "|---|---|---|---|"]
    for r in ordered:
        name = f"[{r['titulo'].replace('|', '/')}]({r['arquivo']})" if r["arquivo"] else r["titulo"]
        lines.append(f"| {r['data']} | {name} | {r['duracao']} | {r['legenda'] or r['status']} |")
    (out_dir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="https://www.youtube.com/@KIMPAIM/videos")
    ap.add_argument("--name", default="kim-paim", help="pasta em youtube/")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--limit", type=int, default=3, help="quantos vídeos novos baixar")
    g.add_argument("--all", action="store_true")
    g.add_argument("--ids", nargs="+")
    ap.add_argument("--sleep", type=float, default=5, help="pausa entre vídeos (segundos)")
    ap.add_argument("--cookies", help="cookies.txt do YouTube (necessário em IPs de datacenter)")
    args = ap.parse_args()
    global COOKIES
    COOKIES = args.cookies

    out_dir = ROOT / "youtube" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_csv(out_dir / "videos.csv")
    ids = args.ids or list_channel(args.channel)
    todo = [i for i in ids if rows.get(i, {}).get("status") not in ("ok", "sem_legenda")]
    if not args.all and not args.ids:
        todo = todo[: args.limit]
    print(f"{len(ids)} vídeos listados, {len(todo)} a processar", file=sys.stderr)

    for n, vid in enumerate(todo, 1):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                info, vtt, kind = fetch(vid, Path(tmp))
                d = info.get("upload_date") or "00000000"
                row = {"video_id": vid, "data": f"{d[:4]}-{d[4:6]}-{d[6:]}", "titulo": info.get("title", ""),
                       "duracao": hms(info.get("duration") or 0), "legenda": kind or "",
                       "status": "sem_legenda", "arquivo": ""}
                if vtt:
                    path = write_video(out_dir, args.name, info, vtt, kind)
                    row.update(status="ok", arquivo=str(path.relative_to(out_dir)))
        except Exception as e:  # noqa: BLE001 - registra e segue para o próximo
            print(f"ERRO {vid}: {e}", file=sys.stderr)
            row = {**rows.get(vid, {f: "" for f in CSV_FIELDS}), "video_id": vid, "status": "erro"}
        rows[vid] = row
        print(f"[{n}/{len(todo)}] {vid} {row['status']} {row.get('titulo', '')}", file=sys.stderr)
        if n % 25 == 0:
            save(out_dir, rows, args.name)
        time.sleep(args.sleep)
    save(out_dir, rows, args.name)


if __name__ == "__main__":
    main()
