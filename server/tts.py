import os
import re
import wave
import subprocess
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

try:
    import edge_tts
except ImportError:
    edge_tts = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PIPER_EXE = os.path.join(BASE_DIR, "piper", "piper.exe")

# Explicit Male Voice Configuration for all supported languages
TTS_VOICES = {
    "en": {
        "edge": "en-US-ChristopherNeural",
        "piper": os.path.join(BASE_DIR, "piper", "en_US-ryan-medium.onnx"),
        "gender": "Male",
        "description": "Microsoft Christopher Neural (Male)"
    },
    "ta": {
        "edge": "ta-IN-ValluvarNeural",
        "piper": None,
        "gender": "Male",
        "description": "Microsoft Valluvar Neural (Male)"
    },
    "hi": {
        "edge": "hi-IN-MadhurNeural",
        "piper": None,
        "gender": "Male",
        "description": "Microsoft Madhur Neural (Male)"
    }
}
DEFAULT_LANG = "en"


async def _generate_edge_tts(text: str, voice_name: str, output_path: str) -> bool:
    """Helper to run edge_tts with retries for connection stability."""
    if edge_tts is None:
        return False
    for attempt in range(1, 4):
        try:
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(output_path)
            return True
        except Exception as exc:
            print(f"[TTS] Edge-TTS attempt {attempt} failed for voice {voice_name}: {exc}")
            if attempt < 3:
                await asyncio.sleep(0.5)
    return False


def _run_edge_tts_sync(text: str, voice_name: str, output_path: str) -> bool:
    """Runs _generate_edge_tts safely in a dedicated worker thread with a clean event loop."""
    def _worker():
        return asyncio.run(_generate_edge_tts(text, voice_name, output_path))

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_worker)
            return future.result(timeout=30)
    except Exception as exc:
        print(f"[TTS] Event loop execution error: {exc}")
        return False


def text_to_speech(text: str, voice_key: str = "male") -> str:
    """
    Generates audio using ALWAYS MALE voices for English, Tamil, and Hindi.
    Guarantees no female voice fallback path.
    Returns the audio filename ('response.mp3' or 'response.wav').
    """
    # Determine language
    if re.search(r'[\u0B80-\u0BFF]', text):
        lang_code = "ta"
    elif re.search(r'[\u0900-\u097F]', text):
        lang_code = "hi"
    else:
        lang_code = "en"

    voice_config = TTS_VOICES.get(lang_code, TTS_VOICES[DEFAULT_LANG])
    voice_name = voice_config["edge"]

    # 1. Try Edge-TTS Male Voice
    audio_mp3_path = os.path.join(BASE_DIR, "response.mp3")
    if os.path.exists(audio_mp3_path):
        try:
            os.remove(audio_mp3_path)
        except Exception:
            pass

    success = _run_edge_tts_sync(text, voice_name, audio_mp3_path)
    if success and os.path.exists(audio_mp3_path) and os.path.getsize(audio_mp3_path) > 0:
        file_size = os.path.getsize(audio_mp3_path)
        print(f"[TTS] Language: {lang_code}")
        print(f"[TTS] Voice: {voice_name}")
        print(f"[TTS] Output: response.mp3")
        print(f"[TTS] File exists: True")
        print(f"[TTS] File size: {file_size}")
        return "response.mp3"

    # 2. English Male Piper Fallback (Offline)
    piper_model = voice_config.get("piper")
    if piper_model and os.path.exists(PIPER_EXE) and os.path.exists(piper_model):
        audio_wav_path = os.path.join(BASE_DIR, "response.wav")
        if os.path.exists(audio_wav_path):
            try:
                os.remove(audio_wav_path)
            except Exception:
                pass
        try:
            result = subprocess.run(
                [PIPER_EXE, "--model", piper_model, "--output_file", audio_wav_path],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and os.path.exists(audio_wav_path) and os.path.getsize(audio_wav_path) > 0:
                file_size = os.path.getsize(audio_wav_path)
                print(f"[TTS] Language: {lang_code}")
                print(f"[TTS] Voice: {voice_config['description']}")
                print(f"[TTS] Output: response.wav")
                print(f"[TTS] File exists: True")
                print(f"[TTS] File size: {file_size}")
                return "response.wav"
            else:
                print(f"[TTS] Piper error: {result.stderr.decode()}")
        except Exception as exc:
            print(f"[TTS] Piper fallback failed: {exc}")

    # 3. Log warning — Strict policy: NEVER fallback to female voice
    file_exists = os.path.exists(audio_mp3_path)
    file_size = os.path.getsize(audio_mp3_path) if file_exists else 0
    print(f"[TTS] Language: {lang_code}")
    print(f"[TTS] Voice: {voice_name}")
    print(f"[TTS] Output: response.mp3")
    print(f"[TTS] File exists: {file_exists}")
    print(f"[TTS] File size: {file_size}")
    raise RuntimeError(
        f"[TTS] Male voice for language '{lang_code}' ({voice_name}) is currently unavailable. "
        "Female voice fallback is disabled."
    )



# ═════════════════════════════════════════════════════════════
#  AUDIO DURATION (WAV + MP3)
# ═════════════════════════════════════════════════════════════
def get_audio_duration(filepath: str) -> float:
    """Returns duration of a WAV or MP3 file in seconds."""
    full_path = filepath if os.path.isabs(filepath) else os.path.join(BASE_DIR, filepath)
    try:
        if full_path.lower().endswith(".mp3"):
            # Get MP3 duration using mutagen if available, else ffprobe, else estimate from file size
            try:
                from mutagen.mp3 import MP3
                audio = MP3(full_path)
                return audio.info.length
            except ImportError:
                pass
            # Fallback: estimate from file size and average bitrate (128kbps)
            file_size = os.path.getsize(full_path)
            estimated_duration = file_size / (128 * 1000 / 8)  # 128kbps = 16000 bytes/sec
            return max(estimated_duration, 1.0)
        else:
            with wave.open(full_path, "r") as wf:
                return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 3.0  # fallback


# Keep old name as alias for backward compatibility
get_wav_duration = get_audio_duration


# ═════════════════════════════════════════════════════════════
#  MOUTH CUES GENERATION
#
#  Viseme letter map matches your frontend `corresponding` obj:
#  A→viseme_PP, B→viseme_kk, C→viseme_I,  D→viseme_AA,
#  E→viseme_O,  F→viseme_U,  G→viseme_FF, H→viseme_TH, X→viseme_PP
# ═════════════════════════════════════════════════════════════

PHONEME_TO_VISEME = {
    "p": "A", "b": "A", "m": "A",           # Bilabials
    "f": "G", "v": "G",                      # Labiodentals
    "th": "H",                               # Dentals
    "t": "B", "d": "B", "n": "B",           # Alveolars
    "k": "B", "g": "B", "ng": "B",          # Velars
    "sh": "B", "ch": "B", "zh": "B",        # Postalveolar
    "s": "B", "z": "B",                     # Sibilants
    "l": "B", "r": "D",                     # Sonorants
    "w": "F", "y": "C",                     # Glides
    "a": "D", "ah": "D", "aw": "D",        # Open vowels
    "e": "C", "eh": "C", "ey": "C",        # Front vowels
    "i": "C", "ih": "C", "iy": "C",        # High front vowels
    "o": "E", "oh": "E", "ow": "E",        # Mid-back vowels
    "u": "F", "uh": "F", "uw": "F",        # High back vowels
}


def word_to_visemes(word: str) -> list:
    """Convert a single word to a list of viseme letters."""
    word = word.lower().strip(".,!?;:'\"()-")
    visemes = []
    i = 0
    while i < len(word):
        digraph = word[i:i+2]
        if digraph in PHONEME_TO_VISEME:
            visemes.append(PHONEME_TO_VISEME[digraph])
            i += 2
        elif word[i] in PHONEME_TO_VISEME:
            visemes.append(PHONEME_TO_VISEME[word[i]])
            i += 1
        else:
            visemes.append("X")
            i += 1
    return visemes if visemes else ["X"]


def generate_mouth_cues(text: str, audio_duration: float) -> list:
    """
    Generate timed mouthCues from text + actual audio duration.
    Distributes visemes proportionally across the real audio length.
    """
    words = [w for w in text.split() if w.strip()]
    if not words:
        return [{"start": 0.0, "end": audio_duration, "value": "X"}]

    # Build weighted viseme list
    all_cues = []
    for word in words:
        for v in word_to_visemes(word):
            # Vowels get slightly more time than consonants
            weight = 1.5 if v in ("C", "D", "E", "F") else 1.0
            all_cues.append((v, weight))
        all_cues.append(("X", 0.4))   # short pause between words

    # Remove trailing silence
    while all_cues and all_cues[-1][0] == "X":
        all_cues.pop()

    if not all_cues:
        return [{"start": 0.0, "end": audio_duration, "value": "X"}]

    total_weight = sum(w for _, w in all_cues)
    mouth_cues   = []
    current_time = 0.0

    for viseme, weight in all_cues:
        duration = (weight / total_weight) * audio_duration
        mouth_cues.append({
            "start": round(current_time, 3),
            "end":   round(current_time + duration, 3),
            "value": viseme,
        })
        current_time += duration

    print(f"[MouthCues] {len(mouth_cues)} cues over {audio_duration:.2f}s")
    return mouth_cues


# ═════════════════════════════════════════════════════════════
#  REGEX CLEANER — strips leftover markdown
# ═════════════════════════════════════════════════════════════
def clean_text(text: str) -> str:
    text = text.strip()
    text = text.replace("\n", " ")
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\*",   "", text)
    text = re.sub(r"_",    "", text)
    text = re.sub(r"#+\s", "", text)
    text = re.sub(r"\s+",  " ", text)
    return text.strip()