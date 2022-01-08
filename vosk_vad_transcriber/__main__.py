import os
import wave
import grpc
import traceback
from time import sleep

from db import get_connection
from utils import GracefulKiller
from vosk_stt_grpc.stt_service_pb2 import RecognitionSpec, RecognitionConfig, StreamingRecognitionRequest
from vosk_stt_grpc.stt_service_pb2_grpc import SttServiceStub

killer = GracefulKiller()

vosk_server_host = os.getenv('VOSK_SERVER_HOST', '127.0.0.1')
vosk_server_port = os.getenv('VOSK_SERVER_PORT', 5001)
channel = grpc.insecure_channel(f"{vosk_server_host}:{vosk_server_port}")

def gen(audio_file_name):
    specification = RecognitionSpec(
        partial_results=False,
        audio_encoding='LINEAR16_PCM',
        sample_rate_hertz=16000,
        enable_word_time_offsets=True,
        max_alternatives=1,
    )
    streaming_config = RecognitionConfig(specification=specification)

    yield StreamingRecognitionRequest(config=streaming_config)

    wf = wave.open(audio_file_name, "rb")
    frames_to_read = wf.getframerate() * 0.2
    while True:
        data = wf.readframes(int(frames_to_read))
        if len(data) == 0:
            break
        yield StreamingRecognitionRequest(audio_content=data)

conn = get_connection()
conn.autocommit = True

cur = conn.cursor()

def transcribe(audio_file_name):
    stub = SttServiceStub(channel)
    it = stub.StreamingRecognize(gen(audio_file_name))

    try:
        for r in it:
            try:
                if (len(r.chunks) > 0):
                    text = r.chunks[0].alternatives[0].text
                    start = r.chunks[0].alternatives[0].words[0].start_time.seconds + r.chunks[0].alternatives[0].words[0].start_time.nanos/1000000000
                    end = r.chunks[0].alternatives[0].words[-1].end_time.seconds + r.chunks[0].alternatives[0].words[-1].end_time.nanos/1000000000
                    yield (text, start, end)
            except LookupError:
                pass
    except grpc._channel._Rendezvous as err:
        print('Error code %s, message: %s' % (err._state.code, err._state.details))

print("Starting")
while not killer.kill_now:
    cur.execute("UPDATE sources SET status='vad_running', status_update=now() \
    WHERE source_id = ( \
    SELECT source_id \
    FROM sources \
    WHERE status='audio_converted' \
    ORDER BY random()  \
    FOR UPDATE SKIP LOCKED \
    LIMIT 1 \
    ) \
    RETURNING source_id, audiopath_16;")
    conn.commit()
    next = cur.fetchone()

    if next:
        source_id, audiopath_16 = next
        try:
            print(f"Transcribing source {source_id}")
            for slice in transcribe(audiopath_16):
                text, start, end = slice
                duration = end - start
                print(f"Saving slice of {duration:.2f}s starting with: {text[:10]}")
                cur.execute('INSERT INTO clips (source_id, "start", "end", duration) VALUES (%s, %s, %s, %s) RETURNING clip_id;', (source_id, start, end, duration))
                clip_id = cur.fetchone()[0]
                print(f"Saved clip with id {clip_id}")
                print(f"Saving vosk transcript")
                cur.execute('INSERT INTO transcripts ("text", transcriber, clip_id) VALUES (%s, %s, %s) RETURNING transcript_id;', (text, "vosk", clip_id))
                transcript_id = cur.fetchone()[0]
                print(f"Saved transcript with id {transcript_id}")
            cur.execute(f"UPDATE sources SET status='vad_done', status_update=now() WHERE source_id = '{source_id}'")
            print(f"Finished transcribing source {source_id}")
        except KeyboardInterrupt:
            print("Stopping")
            cur.execute(f"UPDATE sources SET status='audio_converted', status_update=now() WHERE source_id = '{source_id}'")
            conn.commit()
            break
        except Exception as ex:
            print(f"Transcription failed")
            traceback.print_exc()
            cur.execute(f"UPDATE sources SET status='audio_converted', status_update=now() WHERE source_id = '{source_id}'")
        finally:
            conn.commit()
    else:
        try:
            print("No work, sleeping for 10s...")
            sleep(10)
        except KeyboardInterrupt:
            break

cur.close()
conn.close()
