from pytubefix import Playlist
from db import get_connection
import traceback

def add_yt_playlist(url):
    try:
        conn = get_connection()
        cur = conn.cursor()

        playlist = Playlist(url)
        print(f"Importing {len(playlist.video_urls)} videos")
        for video_url in playlist.video_urls:
            cur.execute("INSERT INTO sources (url, type) VALUES (%s,%s)", (video_url, "youtube"))
            conn.commit()
        print("Finished importing")
    except Exception:
        print("Failed to import channel to DB")
        traceback.print_exc()