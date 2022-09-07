from db import get_connection
import traceback


def add_yt_video(url):
    try:
        conn = get_connection()
        cur = conn.cursor()

        print(f"Importing {url}")
        cur.execute("INSERT INTO sources (url, type) VALUES (%s,%s)", (url, "youtube"))
        conn.commit()
        print("Finished importing")
    except Exception:
        print("Failed to import video to DB")
        traceback.print_exc()
