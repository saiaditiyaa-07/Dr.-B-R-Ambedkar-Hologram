# FastAPI server for Avatar Chatbot - Tamil TTS fixed
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import threading

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # python-dotenv not installed — env vars must be set externally

from agents import safety_agent, main_agent, cleanup_agent
from agents.main_agent import clear_history
from tts import text_to_speech, get_audio_duration, generate_mouth_cues, clean_text
from rag.retriever import preload as rag_preload

app = FastAPI()


@app.on_event("startup")
async def warmup_rag():
    """
    Pre-load the FAISS index and sentence-transformer embedding model
    in a background thread so server startup is instant and the first
    user request pays no cold-start penalty (~48 second saving).
    """
    def _warmup():
        try:
            rag_preload()
        except Exception as exc:
            print(f"[Startup] RAG pre-warm error (non-fatal): {exc}")
    threading.Thread(target=_warmup, daemon=True, name="rag-warmup").start()

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═════════════════════════════════════════════════════════════
#  PIPELINE
#  Safety → Main → Cleanup → TTS → MouthCues
# ═════════════════════════════════════════════════════════════
def run_pipeline(question: str, voice: str = "male", input_lang: str = "auto"):
    """
    Runs the full 3-agent pipeline and returns
    (answer_text, audio_filename, mouth_cues, sources).
    """

    # ── Agent 1: Safety ──────────────────────────────────────
    try:
        is_safe = safety_agent(question)
    except RuntimeError as e:
        error_msg = str(e)
        try:
            audio_file = text_to_speech(error_msg, voice)
            duration   = get_audio_duration(audio_file)
            cues       = generate_mouth_cues(error_msg, duration)
            return error_msg, audio_file, cues, []
        except Exception:
            return error_msg, None, None, []

    if not is_safe:
        blocked_msg = "I'm sorry, I can't help with that. Please ask me something else."
        audio_file  = text_to_speech(blocked_msg, voice)
        duration    = get_audio_duration(audio_file)
        cues        = generate_mouth_cues(blocked_msg, duration)
        return blocked_msg, audio_file, cues, []


    # ── Agent 2: Main response (now returns tuple with sources) ─
    sources = []
    try:
        result = main_agent(question, input_lang)
        if isinstance(result, tuple):
            raw_response, sources = result
        else:
            raw_response = result  # backward compatibility
    except RuntimeError as e:
        error_msg = str(e)
        try:
            audio_file = text_to_speech(error_msg, voice)
            duration   = get_audio_duration(audio_file)
            cues       = generate_mouth_cues(error_msg, duration)
            return error_msg, audio_file, cues, []
        except Exception:
            return error_msg, None, None, []

    # ── Agent 3: Cleanup ──────────────────────────────────────
    try:
        cleaned = cleanup_agent(raw_response)
    except RuntimeError:
        cleaned = clean_text(raw_response)   # fallback to regex

    final_text = clean_text(cleaned)

    # ── TTS Pronunciation Fixes (English only) ─────────────────
    import re as _re
    is_hindi = bool(_re.search(r'[\u0900-\u097F]', final_text))
    is_tamil = bool(_re.search(r'[\u0B80-\u0BFF]', final_text))

    tts_text = final_text

    if not is_hindi and not is_tamil:
        # Only apply English pronunciation fixes for English text
        tts_text = tts_text.replace("B. R. Ambedkar", "Bee Are Ambedkar")
        tts_text = tts_text.replace("B.R. Ambedkar", "Bee Are Ambedkar")

    # ── TTS ───────────────────────────────────────────────────
    try:
        audio_file = text_to_speech(tts_text, voice)
    except RuntimeError as e:
        print(f"[TTS Error] {e}")
        return final_text, None, None, sources

    # ── Mouth cues ────────────────────────────────────────────
    try:
        duration   = get_audio_duration(audio_file)
        mouth_cues = generate_mouth_cues(tts_text, duration)
    except Exception as exc:
        print(f"[MouthCues Error] {exc}")
        mouth_cues = []

    return final_text, audio_file, mouth_cues, sources


# ═════════════════════════════════════════════════════════════
#  ROUTES
# ═════════════════════════════════════════════════════════════
class VoiceRequest(BaseModel):
    message: str
    voice:   str = "male"   # "male" | "female" | "indian"
    input_lang: str = "auto"



class MouthCuesRequest(BaseModel):
    text:     str
    duration: float = 3.0


@app.post("/voice-chat")
async def voice_chat(request: VoiceRequest, raw_req: Request):
    base_url = str(raw_req.base_url).rstrip("/")
    result = run_pipeline(request.message, request.voice, request.input_lang)

    # Unpack with backward compatibility
    if len(result) == 4:
        answer, audio_file, mouth_cues, sources = result
    else:
        answer, audio_file, mouth_cues = result
        sources = []

    if not answer:
        answer = "I'm sorry, I couldn't find an answer to your question."

    return {
        "audio_url":  f"{base_url}/audio/{audio_file}" if audio_file else None,
        "text":       answer,
        "mouthCues":  mouth_cues,
        "sources":    sources,
    }


AUDIO_DIR = os.path.dirname(os.path.abspath(__file__))


@app.api_route("/audio/{filename}", methods=["GET", "HEAD"])
async def get_audio(filename: str, request: Request):
    file_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    if filename.lower().endswith(".mp3"):
        content_type = "audio/mpeg"
    else:
        content_type = "audio/wav"

    headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}

    if request.method == "HEAD":
        file_size = os.path.getsize(file_path)
        headers["Content-Length"] = str(file_size)
        headers["Content-Type"] = content_type
        return Response(
            status_code=200,
            headers=headers,
        )
    return FileResponse(file_path, media_type=content_type, headers=headers)


@app.post("/mouthCues")
async def get_mouth_cues(request: MouthCuesRequest):
    """Standalone mouth-cue generator — same schema as voice-chat mouthCues."""
    cues = generate_mouth_cues(request.text, request.duration)
    return {"mouthCues": cues}


@app.post("/clear-history")
async def clear_chat_history():
    """Clears the conversation memory — useful for starting a new session."""
    clear_history()
    return {"status": "Chat history cleared."}