import os
import re
import wave
import subprocess

try:
    from gtts import gTTS
except Exception:  # pragma: no cover
    gTTS = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PIPER_EXE = os.path.join(BASE_DIR, "piper", "piper.exe")

VOICES = {
    "male":   os.path.join(BASE_DIR, "piper", "en_US-ryan-medium.onnx"),
    "female": os.path.join(BASE_DIR, "piper", "en_US-kathleen-low.onnx"),
    "indian": os.path.join(BASE_DIR, "piper", "en_US-kusal-medium.onnx"),
}
DEFAULT_VOICE = "male"


# ═════════════════════════════════════════════════════════════
#  TTS
# ═════════════════════════════════════════════════════════════
def text_to_speech(text: str, voice_key: str = DEFAULT_VOICE) -> str:
    """
    Runs Piper TTS if local assets are available; otherwise falls back to gTTS.
    Returns the filename of the generated audio.
    """
    # Multilingual TTS Routing
    is_tamil = bool(re.search(r'[\u0B80-\u0BFF]', text))
    is_hindi = bool(re.search(r'[\u0900-\u097F]', text))
    
    if is_tamil or is_hindi:
        if gTTS is None:
            raise RuntimeError("gTTS is required for Tamil/Hindi TTS but is not installed.")
        try:
            audio_file_path = os.path.join(BASE_DIR, "response.mp3")
            lang_code = "ta" if is_tamil else "hi"
            tts = gTTS(text=text, lang=lang_code, slow=False)
            tts.save(audio_file_path)
            print(f"[TTS] Generated multilingual ({lang_code}) audio: {audio_file_path}")
            return "response.mp3"
        except Exception as exc:
            raise RuntimeError(f"Multilingual TTS failed: {exc}")

    if os.path.exists(PIPER_EXE) and os.path.exists(VOICES.get(voice_key, VOICES[DEFAULT_VOICE])):
        voice_model = VOICES.get(voice_key, VOICES[DEFAULT_VOICE])
        audio_file_path = os.path.join(BASE_DIR, "response.wav")

        try:
            result = subprocess.run(
                [PIPER_EXE, "--model", voice_model, "--output_file", audio_file_path],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Piper error: {result.stderr.decode()}")
            print(f"[TTS] Generated {audio_file_path} with voice: {voice_key}")
            return "response.wav"
        except subprocess.TimeoutExpired:
            raise RuntimeError("Piper TTS timed out.")

    if gTTS is not None:
        try:
            audio_file_path = os.path.join(BASE_DIR, "response.mp3")
            tts = gTTS(text=text, lang="en", slow=False)
            tts.save(audio_file_path)
            print(f"[TTS] Generated fallback audio: {audio_file_path}")
            return "response.mp3"
        except Exception as exc:
            raise RuntimeError(f"Fallback TTS failed: {exc}")

    raise RuntimeError(
        "Piper not found and gTTS is unavailable. "
        "Install a local TTS engine or ensure the Piper voice files are present."
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