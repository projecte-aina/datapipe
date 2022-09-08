from db import get_connection
import json
import traceback


def add_ccma_json(path):
    try:
        conn = get_connection()
        cur = conn.cursor()

        f = open(path, 'r')

        data = json.loads(f.read())

        print(f"Importing {len(data)} videos")

        for i in data:
            subtitles = i.get("ebuttd_ca")
            duration = i.get("durada_segons")
            content_id = i.get("content_id")
            source_url = i.get("mp4_500") or i.get("mp4_1200") or i.get("mp4_500_es") or i.get("mp4_1200_es")

            if all(v is not None for v in [source_url, duration, subtitles, content_id]):
                print(f"{source_url} inserted to database.")
                cur.execute(
                    "INSERT INTO sources (url, type, status, subtitlepath, duration, license, metadata, has_captions) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (source_url, "ccma", "ready_for_download", subtitles, duration, "CCMA", f'{{"content_id": {content_id}}}', bool(subtitles)))
                conn.commit()
            else:
                print("No available urls found")
        print("Finished importing")
    except Exception:
        print("Failed to import json to DB")
        traceback.print_exc()
