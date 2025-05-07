"""
tsv_exporter/__main__.py
Build /datapipe/dataset.tsv from /datapipe/clips and the transcripts table.

For each *.wav* in CLIPS_DIR we write:

    absolute_path <TAB> combined_transcription

The transcription is the STRING_AGG of every row in `transcripts`
belonging to that clip_id, ordered by `start`.
"""

from os import getenv, makedirs, path, walk, replace
from time import sleep
import hashlib
import traceback
import csv
import html
import re
from typing import Dict, List

from db import get_connection
from utils import GracefulKiller

# ─────────────────────────── configuration ────────────────────────────────
CLIPS_DIR  = getenv("CLIPS_DIR", "/datapipe/clips")
TSV_PATH   = getenv("TSV_PATH",  "/datapipe/dataset.tsv")
POLL_INTERVAL = int(getenv("POLL_INTERVAL", 30))
HEADER     = ["absolute_path", "transcription"]
AUTOCOMMIT = getenv("AUTOCOMMIT", "0") == "1"

# ─────────────────────────── helpers ───────────────────────────────────────
def list_clips() -> Dict[str, str]:
    """
    Return {clip_id: absolute_path} for every *.wav in CLIPS_DIR.
    The clip_id is the filename without gender suffix and extension.
    """
    clips = {}
    for root, _dirs, files in walk(CLIPS_DIR):
        for fn in files:
            if not fn.lower().endswith(".wav"):
                continue
            base = fn[:-4]                       # strip .wav
            base = base.split("_", 1)[0]         # strip _male / _female / …
            clips[base] = path.abspath(path.join(root, fn))
    return clips


def dir_signature(paths: List[str]) -> str:
    """Hash (path, mtime) so we know when /clips changed."""
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.encode())
        try:
            h.update(str(path.getmtime(p)).encode())
        except FileNotFoundError:
            pass
    return h.hexdigest()


def ensure_output_dir():
    makedirs(path.dirname(TSV_PATH), exist_ok=True)


_clean = re.compile(r"[\t\r\n]+").sub
def sanitize(txt: str) -> str:
    """Unescape HTML, collapse whitespace, trim."""
    return _clean(" ", html.unescape(txt or "")).strip()

# ─────────────────────────── TSV rebuild ───────────────────────────────────
QUERY = """
SELECT t.clip_id::text,
       string_agg(t.text, ' ' ORDER BY c.start) AS transcript
  FROM transcripts t
  JOIN clips      c USING (clip_id)
 WHERE t.clip_id::text = ANY(%s)
 GROUP BY t.clip_id;
"""


def rebuild_tsv(conn, clip_map: Dict[str, str]):
    ensure_output_dir()
    tmp = TSV_PATH + ".tmp"
    clip_ids = list(clip_map.keys())

    with conn.cursor() as cur:
        cur.execute(QUERY, (clip_ids,))
        rows = cur.fetchall()   # [(clip_id, "full text"), …]

    text_by_id = {cid: sanitize(t) for cid, t in rows}

    with open(tmp, "w", newline="") as f:
        writer = csv.writer(
            f,
            delimiter="\t",
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writerow(HEADER)
        for cid, fp in sorted(clip_map.items()):
            writer.writerow([fp, text_by_id.get(cid, "")])

    replace(tmp, TSV_PATH)
    print(f"💾  Wrote {len(clip_map)} rows to {TSV_PATH}")

# ─────────────────────────── main loop ─────────────────────────────────────
def main():
    killer = GracefulKiller()
    conn   = get_connection()
    conn.autocommit = AUTOCOMMIT
    last_sig = None

    while not killer.kill_now:
        try:
            clip_map = list_clips()
            if not clip_map:
                print("📂  No clips yet – sleeping")
                sleep(POLL_INTERVAL)
                continue

            sig = dir_signature(list(clip_map.values()))
            if sig != last_sig:
                print("🔄  Change detected – rebuilding TSV")
                rebuild_tsv(conn, clip_map)
                if not AUTOCOMMIT:
                    conn.commit()
                last_sig = sig
            else:
                print(f"😴  No change – sleeping {POLL_INTERVAL}s")

            sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            break
        except Exception:
            traceback.print_exc()
            try:
                conn.rollback()
            except Exception:
                pass
            sleep(10)

    conn.close()
    print("👋  TSV‑exporter stopped")


if __name__ == "__main__":
    main()