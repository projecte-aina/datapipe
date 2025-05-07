"""
channel_feeder – sequentially ingest every video in a YouTube channel
or playlist, strictly one at a time.
"""

import argparse, subprocess, time, logging, sys, os
from typing import Optional
from db import get_connection

try:
    import yt_dlp as ytdl
except ModuleNotFoundError:
    import youtube_dl as ytdl

log = logging.getLogger("channel-feeder")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)

# ────────────────────────── helpers ────────────────────────────────────────
def list_ids(url: str, cookies: Optional[str] = None):
    opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "ignoreerrors": "only_download",
    }
    if cookies:
        opts["cookies"] = cookies
    info = ytdl.YoutubeDL(opts).extract_info(url, download=False)
    entries = [e for e in info.get("entries", []) if e]
    return [e["id"] for e in reversed(entries)]            # oldest first


def finished(conn, vid: str) -> bool:
    """
    Return True once *every* clip for source_id=vid has been transcribed.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
              FROM clips AS c
              WHERE c.source_id::text = %s
                AND NOT EXISTS (
                      SELECT 1
                        FROM transcripts AS t
                       WHERE t.clip_id = c.clip_id
                   )
            """,
            (vid,),
        )
        # If zero clips lack a transcript, we're finished.
        return cur.fetchone()[0] == 0

# ────────────────────────── main ───────────────────────────────────────────
def main(argv=None):
    p = argparse.ArgumentParser(
        prog="channel_feeder",
        description="Feed a YouTube channel/playlist into Datapipe "
                    "one video at a time."
    )
    p.add_argument("url")
    p.add_argument("--poll", type=int, default=30,
                   help="seconds between DB checks (30)")
    p.add_argument("--cookies", help="cookies.txt for age‑gated videos")
    args = p.parse_args(argv)

    if args.cookies and not os.path.exists(args.cookies):
        log.error("Cookies file %s not found", args.cookies)
        sys.exit(1)

    conn = get_connection()
    ids = list_ids(args.url, args.cookies)
    log.info("Found %d videos", len(ids))

    for vid in ids:
        yt = f"https://www.youtube.com/watch?v={vid}"
        log.info("▶️  Adding %s", yt)
        subprocess.run(["python", "-m", "cli", "add-yt-video", yt], check=True)

        while not finished(conn, vid):
            log.info("⌛  Waiting for %s …", vid)
            time.sleep(args.poll)

        log.info("✅  Video %s finished", vid)

    conn.close()
    log.info("🏁  Channel done; exiting.")


if __name__ == "__main__":
    main()