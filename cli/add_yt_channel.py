from pytubefix import Channel
from db import get_connection
import traceback

def add_yt_channel(channel):
    try:
        conn = get_connection()
        cur = conn.cursor()

        c = Channel(channel)
        print(f"Importing {len(c.video_urls)} videos")
        for url in c.video_urls:
            cur.execute(
                "INSERT INTO sources (url, type) VALUES (%s,%s)",
                (str(url), "youtube")  # <-- cast to plain text
            )
            conn.commit()
        print("Finished importing")
    except Exception:
        print("Failed to import channel to DB")
        traceback.print_exc()