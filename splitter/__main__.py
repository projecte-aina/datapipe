import os
import wave
import argparse
import grpc
from stt_grpc.stt_service_pb2 import RecognitionSpec, RecognitionConfig, StreamingRecognitionRequest
from stt_grpc.stt_service_pb2_grpc import SttServiceStub

vosk_server_host = os.getenv('VOSK_SERVER_HOST') or '127.0.0.1'
vosk_server_port = os.getenv('VOSK_SERVER_PORT') or 5001
channel = grpc.insecure_channel(f"{vosk_server_host}:{vosk_server_port}")

CHUNK_SIZE = 4000

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

    # with open(audio_file_name, 'rb') as f:
    #     data = f.read(CHUNK_SIZE)
    #     while data != b'':
    #     print(len(data))
    #         data = f.read(CHUNK_SIZE)


def run(audio_file_name):
    stub = SttServiceStub(channel)
    it = stub.StreamingRecognize(gen(audio_file_name))

    try:
        for r in it:
            try:
                # print('Start chunk: ')
                # for alternative in r.chunks[0].alternatives:
                #     print('alternative: ', alternative.text)
                #     print('alternative_confidence: ', alternative.confidence)
                #     print('words: ', alternative.words)
                # print('Is final: ', r.chunks[0].final)
                # print('')
                if (len(r.chunks) > 0):
                    print(r.chunks[0].alternatives[0].text)
                    print(r.chunks[0].alternatives[0].words[0].start_time.seconds)
                    print(r.chunks[0].alternatives[0].words[-1].end_time.seconds)
                    end = r.chunks[0].alternatives[0].words[-1].end_time.seconds + r.chunks[0].alternatives[0].words[-1].end_time.nanos/1000000000
                    start = r.chunks[0].alternatives[0].words[0].start_time.seconds + r.chunks[0].alternatives[0].words[0].start_time.nanos/1000000000
                    print(end - start)
            except LookupError:
                print('No available chunks')
    except grpc._channel._Rendezvous as err:
        print('Error code %s, message: %s' % (err._state.code, err._state.details))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', required=True, help='audio file path')
    args = parser.parse_args()
    run(args.path)
