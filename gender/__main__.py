from os import getenv, path
import sys
from joblib import load
from time import sleep

import numpy as np
import torch
from pydub import AudioSegment, effects
import librosa
from pyannote.audio import Inference
import pandas as pd
import traceback

from db import get_connection
from utils import GracefulKiller

killer = GracefulKiller()

CLIPS_PATH = getenv("CLIPS_PATH", "./clips")

if not path.exists(CLIPS_PATH):
    print(f"Clips path {CLIPS_PATH} does not exist!")
    sys.exit(1)

MFCC_MIN_FREQUENCY = 60
MFCC_MAX_FREQUENCY = 8_000
MFCC_BANDS         = 80

# instantiate pyannote voice embedding
inference = Inference("pyannote/embedding", window="whole")

# convert pydub audio file to numpy arraay
def pydub_to_np(audio):
    return np.array(audio.get_array_of_samples(), dtype=np.float32).reshape((-1, audio.channels)).T

# convert pydub audio file to pytorch tensor which is needed for pyannote
def get_tensor_from_audiofile(audio_file):
    channel_count = audio_file.channels
    if channel_count==1:
        samples = audio_file.get_array_of_samples()
        wv = np.array(samples).astype(np.float32).reshape(-1, len(samples))
        wv /= np.iinfo(samples.typecode).max
        wv_tensor = torch.tensor(wv)
    elif channel_count==2:
        channels = audio_file.split_to_mono()
        samples = [s.get_array_of_samples() for s in channels]
        wv = np.array(samples).astype(np.float32)
        wv = wv.mean(axis=0)
        wv = wv.reshape(-1, len(wv))
        wv /= np.iinfo(samples[0].typecode).max
        wv_tensor = torch.tensor(wv)
    return wv_tensor

# load and preprocess audio file, extract features with librosa and pyannote
def get_features(file):
    # create empty array to return in case processing fails
    empty_ = np.empty(611,)
    empty_[:] = np.nan 
    
    try:
        audio_file = AudioSegment.from_file(file)
    except Exception as e:
        print(e)
        print(f"{file} can't be loaded")
        return empty_  
        
    sample_rate = audio_file.frame_rate

    # normalize audio levels
    try:
        audio_file = effects.normalize(audio_file)  
    except Exception as e:
        print(f"{file} can't be normalized")
        return empty_  

    waveform = pydub_to_np(audio_file)
       
    if waveform.ndim == 2: # check if file is stereo 
        waveform = waveform.mean(axis=0) # if stereo merge channels by averaging

    if len(waveform)>0:
        # extract MFCCs
        mfcc_ = np.mean(librosa.feature.mfcc(y=waveform, 
                                             sr=sample_rate, 
                                             n_mfcc=MFCC_BANDS, 
                                             fmin=MFCC_MIN_FREQUENCY,
                                             fmax=MFCC_MAX_FREQUENCY,
                                            ), axis=1) 

        # extract chromagram and contrast
        stft_ = np.abs(librosa.stft(waveform))
        chroma_ = np.mean(librosa.feature.chroma_stft(S=stft_, sr=sample_rate).T, axis=0)
        contrast_ = np.mean(librosa.feature.spectral_contrast(S=stft_, sr=sample_rate).T, axis=0)
        
        # return empty if audio is less than 0.5 seconds after removing silence at beginning and end
        # embedding doesn't work on very short audio fragments
        if audio_file.duration_seconds < 0.5:
            return empty_
        
        # get embedding from pyannote
        waveform_tensor = get_tensor_from_audiofile(audio_file)
        embedding_ = inference({"waveform": waveform_tensor, "sample_rate":sample_rate})
        
        return np.hstack([mfcc_, chroma_, contrast_, embedding_])
                         
    else:
        return empty_

pipe = load('gender/model.joblib')

conn = get_connection()

cur = conn.cursor()

print("Starting")
while not killer.kill_now:
    cur.execute("\
        SELECT c.clip_id, c.filepath \
        FROM clips c \
        WHERE c.filepath IS NOT null and clip_id not in ( \
            select clip_id from genders where origin != 'model') \
        ORDER BY random() \
        LIMIT 1;")
    conn.commit()
    clip = cur.fetchone()
    
    if clip:
        clip_id, filepath = clip
        try:
            feat = pd.DataFrame([get_features(filepath)])
            prediction = pipe.predict(feat)[0]
            cur.execute('INSERT INTO genders (gender, origin, clip_id) VALUES (%s, %s, %s) RETURNING gender_id;', (prediction, "model", clip_id))
            conn.commit()
        except KeyboardInterrupt:
            print("Stopping")
            break
        except Exception as ex:
            print(f"Preprocessing failed")
            traceback.print_exc()
    else:
        try:
            print("No work, sleeping for 10s...")
            sleep(10)
        except KeyboardInterrupt:
            break

cur.close()
conn.close()