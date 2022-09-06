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
            # subtitles = None if "ebuttd_ca" not in i else i['ebuttd_ca']
            subtitles = i.get("ebuttd_ca")
            # duration = None if "durada_segons" not in i else i['durada_segons']
            duration = i.get("durada_segons")

            # source_url = i["mp4_500"] if "mp4_500" in i else i["mp4_1200"] if "mp4_1200" in i else i["mp4_500_es"]
            # if "mp4_500_es" in i else i["mp4_1200_es"] if "mp4_1200_es" in i else None
            source_url = i.get("mp4_500") or i.get("mp4_1200") or i.get("mp4_500_es") or i.get("mp4_1200_es")

            if source_url is not None and duration <= 100 and subtitles is not None:
                print(f"{source_url} inserted to database.")
                cur.execute(
                    "INSERT INTO sources (url, type, status, subtitlepath, duration, license, has_captions) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (source_url, "ccma", "ready_for_download", subtitles, duration, "CCMA", bool(subtitles)))
                conn.commit()
            else:
                print("No available urls found")
        print("Finished importing")
    except Exception:
        print("Failed to import channel to DB")
        traceback.print_exc()
