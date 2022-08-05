from db import get_connection
import json
import traceback


def add_ccma_json(path):
    try:
        conn = get_connection()
        cur = conn.cursor()

        f = open(path, 'r')

        data = json.loads(f.read())


        print(f"Importing {len(data['docs'])} videos")

        for i in data['docs']:
            subtitles = None if "ebuttd_ca" not in i else i['ebuttd_ca']
            duration = None if "durada_segons" not in i else i['durada_segons']
            if 'mp4_500' in i:
                cur.execute("INSERT INTO sources (url, type, status, subtitlepath, duration, license, has_captions) VALUES (%s,%s,%s,%s,%s,%s,%s)", (i["mp4_500"], "ccma", "ready_for_download", subtitles, duration, "CCMA", bool(subtitles)))
                conn.commit()
            else:
                print("No available urls found")
        print("Finished importing")
    except Exception:
        print("Failed to import channel to DB")
        traceback.print_exc()
