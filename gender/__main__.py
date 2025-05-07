from os import getenv, path, makedirs, rename          # ⬅️ added rename
import sys
from joblib import load
from time import sleep
import traceback

import numpy as np
import pandas as pd
import torch
from pydub import AudioSegment, effects
import librosa
from pyannote.audio import Inference

from db import get_connection
from utils import GracefulKiller

# ───────────────────────────────────────────────────────── constants & paths ──
CLIPS_PATH          = getenv("CLIPS_PATH", "./clips")
HF_TOKEN            = getenv("HF_TOKEN")
MFCC_MIN_FREQUENCY  = 60
MFCC_MAX_FREQUENCY  = 8_000
MFCC_BANDS          = 80
EMPTY_VECTOR        = np.full(611, np.nan, dtype=np.float32)

if not path.exists(CLIPS_PATH):
    print(f"Clips path {CLIPS_PATH} does not exist – creating it.")
    makedirs(CLIPS_PATH, exist_ok=True)

# ─────────────────────────────────────────────── model / helper initialisation ─
inference = Inference(
    "pyannote/embedding",
    window="whole",
    use_auth_token=HF_TOKEN,
)
pipe = load("gender/model.joblib")           # sklearn pipeline

def pydub_to_np(audio):
    return np.array(audio.get_array_of_samples(),
                    dtype=np.float32).reshape((-1, audio.channels)).T

def get_tensor_from_audiofile(audio_file):
    chans = audio_file.channels
    if chans == 1:
        arr = np.array(audio_file.get_array_of_samples(), np.float32)
        arr = arr.reshape(-1, arr.size)
    else:  # stereo → mono
        mono = np.mean([np.array(ch.get_array_of_samples(), np.float32)
                        for ch in audio_file.split_to_mono()], axis=0)
        arr = mono.reshape(-1, mono.size)
    arr /= np.iinfo(audio_file.array_type).max
    return torch.tensor(arr)

def get_features(wav_path: str) -> np.ndarray:
    """Return 611‑D feature vector or EMPTY_VECTOR on any failure."""
    try:
        audio = AudioSegment.from_file(wav_path)
    except Exception:
        print(f"[⚠] {wav_path} can't be loaded.")
        return EMPTY_VECTOR

    try:
        audio = effects.normalize(audio)
    except Exception:
        print(f"[⚠] {wav_path} can't be normalized.")
        return EMPTY_VECTOR

    if audio.duration_seconds < 0.5:
        return EMPTY_VECTOR

    waveform = pydub_to_np(audio)
    if waveform.ndim == 2:
        waveform = waveform.mean(axis=0)

    sr = audio.frame_rate
    mfcc = np.mean(librosa.feature.mfcc(
        y=waveform, sr=sr, n_mfcc=MFCC_BANDS,
        fmin=MFCC_MIN_FREQUENCY, fmax=MFCC_MAX_FREQUENCY), axis=1)

    stft = np.abs(librosa.stft(waveform))
    chroma   = np.mean(librosa.feature.chroma_stft(S=stft, sr=sr).T, axis=0)
    contrast = np.mean(librosa.feature.spectral_contrast(S=stft, sr=sr).T, axis=0)

    emb = inference({"waveform": get_tensor_from_audiofile(audio),
                     "sample_rate": sr})

    return np.hstack([mfcc, chroma, contrast, emb])

def features_ok(vec: np.ndarray) -> bool:
    return vec.size and np.isfinite(vec).all()

# ─────────────────────────────────────────────────────────────────── DB setup ──
killer = GracefulKiller()
conn   = get_connection()
cur    = conn.cursor()

print("✓ gender service started")
QUERY_WORK = """
    SELECT c.clip_id, c.filepath
    FROM   clips c
    WHERE  c.filepath IS NOT NULL
      AND  c.clip_id NOT IN (SELECT clip_id
                             FROM genders
                             WHERE origin != 'model')
    ORDER BY random()
    LIMIT 1;
"""
INSERT_RESULT = """
    INSERT INTO genders (gender, origin, clip_id)
    VALUES (%s, %s, %s);
"""

# ───────────────────────────────────────────────────────────── main loop ──
while not killer.kill_now:
    cur.execute(QUERY_WORK)
    conn.commit()
    row = cur.fetchone()

    if not row:
        print("No work, sleeping 10 s …")
        sleep(10)
        continue

    clip_id, wav_path = row
    try:
        feat_vec = get_features(wav_path)
        if not features_ok(feat_vec):
            raise ValueError("invalid/NaN feature vector")

        gender_pred = pipe.predict(pd.DataFrame([feat_vec]))[0]

        # 1) store in DB
        cur.execute(INSERT_RESULT, (gender_pred, "model", clip_id))
        conn.commit()

        # 2) ONE‑TIME rename on disk
        dir_, base = path.split(wav_path)
        stem, ext  = path.splitext(base)
        if "_" not in stem:                 # not renamed yet
            new_base = f"{stem}_{gender_pred}{ext}"
            new_path = path.join(dir_, new_base)
            try:
                rename(wav_path, new_path)
                print(f"✓ clip {clip_id} → {gender_pred}  (saved as {new_base})")
            except FileNotFoundError:
                print(f"⚠ clip {clip_id}: file vanished before rename")
        else:
            print(f"✓ clip {clip_id} → {gender_pred}")

    except (FileNotFoundError, ValueError) as skip:
        print(f"⚠ skipping clip {clip_id}: {skip}")
        cur.execute(INSERT_RESULT, ("unknown", "error", clip_id))
        conn.commit()

    except Exception:
        print(f"‼ preprocessing failed for clip {clip_id}")
        traceback.print_exc()

print("Stopping gracefully …")
cur.close()
conn.close()