import os
import sys
import requests
import json
import re

# Ensure the server directory is on the path for rag imports
SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from rag.retriever import retrieve, format_context, format_sources, is_available as rag_is_available

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ── Load curated Ambedkar archive as supplementary context ────
# This provides rich biographical/topic data for broad questions
# where the FAISS index may only return title pages.
ARCHIVE_PATH = os.path.join(SERVER_DIR, "ambedkar_archive.json")
_archive_context = ""
try:
    with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
        archive_data = json.load(f)
    _archive_lines = ["CURATED REFERENCE MATERIAL:\n"]
    for topic, content in archive_data.items():
        _archive_lines.append(f"[{topic}]")
        _archive_lines.append(content)
        _archive_lines.append("")
    _archive_context = "\n".join(_archive_lines)
    print(f"[Main Agent] ✓ Loaded curated archive: {len(archive_data)} topics")
except Exception as e:
    print(f"[Main Agent] ⚠️ Could not load archive: {e}")

# Fastest models on Groq — ordered by speed (fallback chain)
# llama-3.1-8b-instant is ~3-4x faster than qwen3.8-27b for classification tasks
GROQ_CLASSIFIER_MODELS = [
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "qwen/qwen3.8-27b",
]

# Best quality/speed tradeoff for grounded generation
GROQ_GENERATION_MODELS = [
    "llama-3.3-70b-versatile",
    "qwen/qwen3.8-27b",
    "llama-3.1-8b-instant",
]

# Legacy alias kept for any external references
GROQ_MODELS = GROQ_CLASSIFIER_MODELS

# ── Standard Canonical Responses ─────────────────────────────

IDENTITY_RESPONSES = {
    "EN": "I am a digital AI representation of Dr. B. R. Ambedkar, designed to provide information about his life, writings, ideas, social movements, political work, constitutional work, and historically documented contributions.",
    "TA": "நான் டாக்டர் பி. ஆர். அம்பேத்கரின் வாழ்க்கை, எழுத்துகள், சிந்தனைகள், சமூக இயக்கங்கள், அரசியல் பணி, அரசியலமைப்புப் பணி மற்றும் வரலாற்று பங்களிப்புகள் பற்றிய தகவல்களை வழங்குவதற்காக உருவாக்கப்பட்ட டிஜிட்டல் AI பிரதிநிதி.",
    "HI": "मैं डॉ. बी. आर. आंबेडकर के जीवन, लेखन, विचारों, सामाजिक आंदोलनों, राजनीतिक कार्य, संवैधानिक कार्य और ऐतिहासिक योगदानों के बारे में जानकारी प्रदान करने के लिए बनाया गया एक डिजिटल AI प्रतिनिधि हूँ।",
}

IRRELEVANT_RESPONSES = {
    "EN": "I am designed specifically to provide information about Dr. B. R. Ambedkar and his contributions. Please ask me something related to Dr. B. R. Ambedkar.",
    "TA": "நான் டாக்டர் பி. ஆர். அம்பேத்கர் மற்றும் அவரது பங்களிப்புகள் பற்றிய தகவல்களை வழங்குவதற்காக வடிவமைக்கப்பட்டுள்ளேன். டாக்டர் பி. ஆர். அம்பேத்கர் தொடர்பான கேள்வியைக் கேளுங்கள்.",
    "HI": "मैं डॉ. बी. आर. आंबेडकर और उनके योगदान के बारे में जानकारी प्रदान करने के लिए बनाया गया हूँ। कृपया डॉ. बी. आर. आंबेडकर से संबंधित प्रश्न पूछें।",
}

NO_SOURCE_RESPONSES = {
    "EN": "I could not find sufficient information about this in the available Ambedkar source documents.",
    "TA": "கிடைக்கக்கூடிய அம்பேத்கர் தொடர்பான ஆதார ஆவணங்களில் இதற்குப் போதுமான தகவல் கிடைக்கவில்லை.",
    "HI": "उपलब्ध आंबेडकर संबंधी स्रोत दस्तावेज़ों में इस प्रश्न के लिए पर्याप्त जानकारी नहीं मिली।",
}

ABOUT_AMBEDKAR_RESPONSES = {
    "EN": "Dr. B. R. Ambedkar was an Indian jurist, economist, social reformer, and political leader. He chaired the Constitution Drafting Committee and became independent India's first Law and Justice Minister. He worked throughout his life for equality, dignity, and the rights of oppressed communities.",
    "TA": "டாக்டர் பி. ஆர். அம்பேத்கர் இந்திய சட்டவியலாளர், பொருளாதார நிபுணர், சமூக சீர்திருத்தவாதி மற்றும் அரசியல் தலைவர். அரசியலமைப்பு வரைவுக் குழுவின் தலைவராகவும், சுதந்திர இந்தியாவின் முதல் சட்டம் மற்றும் நீதித்துறை அமைச்சராகவும் பணியாற்றினார். சமத்துவம், கண்ணியம் மற்றும் ஒடுக்கப்பட்ட மக்களின் உரிமைகளுக்காக அவர் வாழ்நாள் முழுவதும் பாடுபட்டார்.",
    "HI": "डॉ. बी. आर. आंबेडकर भारतीय विधिवेत्ता, अर्थशास्त्री, समाज सुधारक और राजनीतिक नेता थे। उन्होंने संविधान की मसौदा समिति की अध्यक्षता की और स्वतंत्र भारत के पहले कानून एवं न्याय मंत्री बने। उन्होंने अपना पूरा जीवन समानता, गरिमा और वंचित समुदायों के अधिकारों के लिए समर्पित किया।",
}

LANGUAGE_NAMES = {
    "EN": "English",
    "TA": "Tamil",
    "HI": "Hindi",
}

# Persistent Chat History
chat_history = []


def detect_script_language(text: str, input_lang_hint: str = "auto") -> str:
    """Fast regex script detector for Tamil and Hindi."""
    if re.search(r'[\u0B80-\u0BFF]', text):
        return "TA"
    if re.search(r'[\u0900-\u097F]', text):
        return "HI"
    if input_lang_hint:
        hint_lower = input_lang_hint.lower()
        if "ta" in hint_lower or "tamil" in hint_lower:
            return "TA"
        if "hi" in hint_lower or "hindi" in hint_lower:
            return "HI"
    return "EN"


def classify_and_preprocess(user_message: str, history: list, input_lang_hint: str = "auto") -> tuple:
    """
    Classifies user message intent into (IDENTITY, IRRELEVANT, RELEVANT),
    detects language (EN, TA, HI), and extracts standalone English query for RAG.
    Returns: (category, language, standalone_query_en)
    """
    script_lang = detect_script_language(user_message, input_lang_hint)
    msg_lower = user_message.lower().strip()

    # 1. Direct Identity Heuristic Check (Asking about the chatbot/assistant itself)
    assistant_identity_keywords = [
        "who are you", "what are you", "are you chatgpt", "are you an ai",
        "who made you", "who created you", "tell me about yourself",
        "நீங்கள் யார்", "நீ யார்", "நீங்கள் சாட்பாட்டா",
        "आप कौन हैं", "तुम कौन हो", "क्या आप चैटजीपीटी हैं", "आप कौन हो"
    ]
    if any(kw in msg_lower for kw in assistant_identity_keywords) or msg_lower in ("who are you?", "who are you", "आप कौन हैं?", "நீங்கள் யார்?"):
        return ("IDENTITY", script_lang, user_message)

    # Answer the assistant's core subject identity without depending on a
    # retrieved excerpt that may not contain a biographical introduction.
    about_ambedkar_patterns = (
        r"\bwho\s+is\s+(?:dr\.?\s*)?(?:b\.?\s*r\.?\s*)?ambedkar\b",
        r"\btell\s+me\s+about\s+(?:dr\.?\s*)?(?:b\.?\s*r\.?\s*)?ambedkar\b",
        r"\bwho\s+was\s+(?:dr\.?\s*)?(?:b\.?\s*r\.?\s*)?ambedkar\b",
    )
    if any(re.search(pattern, msg_lower) for pattern in about_ambedkar_patterns):
        return ("ABOUT_AMBEDKAR", script_lang, user_message)

    # ── FAST-PATH: Heuristic RELEVANT detection ──────────────────────────────
    # If the query clearly mentions Ambedkar or closely related topics, skip the
    # Groq classifier API call entirely (saves ~900-2400ms per relevant request).
    _RELEVANT_EN_KEYWORDS = [
        "ambedkar", "b.r. ambedkar", "b. r. ambedkar", "babasaheb",
        "caste", "untouchable", "dalit", "mahar", "scheduled caste",
        "constitution", "constituent assembly", "drafting committee",
        "annihilation of caste", "poona pact", "mahad", "satyagraha",
        "manusmriti", "navayana", "buddhism", "conversion", "buddha and his dhamma",
        "round table", "republican party", "independent labour party",
        "bharat ratna", "columbia university", "london school of economics",
        "untouchability", "social reform", "social justice",
        "dr. ambedkar", "dr ambedkar", "baba saheb",
    ]
    _RELEVANT_TA_KEYWORDS = [
        "அம்பேத்கர்", "ஆம்பேத்கர்", "சாதி", "தாழ்த்தப்பட்ட",
        "அரசியலமைப்பு", "புத்த", "மகாத்", "பூனா",
    ]
    _RELEVANT_HI_KEYWORDS = [
        "आंबेडकर", "अम्बेडकर", "जाति", "संविधान", "बौद्ध",
        "दलित", "अस्पृश्यता", "महाड", "पूना",
    ]

    all_relevant_kw = _RELEVANT_EN_KEYWORDS + _RELEVANT_TA_KEYWORDS + _RELEVANT_HI_KEYWORDS
    if any(kw in msg_lower for kw in all_relevant_kw):
        print(f"[Classifier] FAST-PATH RELEVANT (keyword match) — skipping API call")
        return ("RELEVANT", script_lang, user_message)

    # ── FAST-PATH: Heuristic IRRELEVANT detection ─────────────────────────────
    # If the query is a short message with no Ambedkar context AND no chat history,
    # AND it matches obviously off-topic topic keywords, classify without API.
    # Only do this for short EN queries where context is unlikely to matter.
    _OBVIOUS_IRRELEVANT_EN = [
        "weather", "temperature", "forecast", "cricket", "ipl",
        "movie", "film", "song", "music", "recipe", "cook",
        "python code", "write code", "stock price", "bitcoin",
        "tell me a joke", "joke", "funny",
        "what is 2+2", "math problem", "solve this",
        "who is the prime minister", "who is the president",
        "capital of", "population of",
    ]
    if script_lang == "EN" and not history and len(msg_lower) < 120:
        if any(kw in msg_lower for kw in _OBVIOUS_IRRELEVANT_EN):
            print(f"[Classifier] FAST-PATH IRRELEVANT (keyword match) — skipping API call")
            return ("IRRELEVANT", script_lang, user_message)
    # ─────────────────────────────────────────────────────────────────────────

    # Extract conversation dialogue context
    recent_dialogue = ""
    for msg in history[-6:]:
        if msg.get("role") in ("user", "assistant"):
            role_name = "User" if msg["role"] == "user" else "Assistant"
            recent_dialogue += f'{role_name}: "{msg.get("content", "")}"\n'

    if GROQ_API_KEY:
        classifier_system_prompt = (
            "You are an NLP classifier for a Dr. B. R. Ambedkar digital AI assistant.\n"
            "Analyze the User query given the Recent Dialogue context.\n\n"
            "Tasks:\n"
            "1. 'language': Detect user query language: 'EN' (English), 'TA' (Tamil script or Tanglish), or 'HI' (Hindi Devanagari or Hinglish).\n"
            "2. 'category': One of:\n"
            "   - 'IDENTITY': User asks who/what the AI assistant is (e.g., 'Who are you?', 'Are you ChatGPT?', 'आप कौन हैं?', 'நீங்கள் யார்?'). NOTE: 'Who is Dr. B. R. Ambedkar?' is RELEVANT, NOT IDENTITY!\n"
            "   - 'IRRELEVANT': Query is completely unrelated to Dr. B. R. Ambedkar (e.g., weather, current CM/PM today, python code, sports, jokes, quantum physics, capital of France).\n"
            "   - 'RELEVANT': Query is directly about Dr. B. R. Ambedkar (biography, education, writings, speeches, ideas, caste, untouchability, social reform, Mahad Satyagraha, Poona Pact, Round Table Conferences, Constituent Assembly, Constitution, democracy, economics, Buddhism, conversion, contemporaries like Gandhi/Nehru/Rajendra Prasad, political work, or historical events connected to Ambedkar, OR follow-ups/contextual questions referring to Ambedkar/his work/contemporaries).\n"
            "3. 'standalone_query_en': An English translation and contextual rewriting of the query for vector database search. Resolve pronouns ('he', 'his', 'it', 'they', 'him') to 'Dr. B. R. Ambedkar' or the specific historical topic discussed.\n\n"
            "Respond ONLY in valid JSON format:\n"
            "{\n"
            '  "language": "EN" | "TA" | "HI",\n'
            '  "category": "IDENTITY" | "IRRELEVANT" | "RELEVANT",\n'
            '  "standalone_query_en": "English search query"\n'
            "}"
        )

        classifier_user_prompt = f"Recent Dialogue:\n{recent_dialogue}\nUser Query: \"{user_message}\""

        for model_name in GROQ_CLASSIFIER_MODELS:
            try:
                res = requests.post(
                    GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": classifier_system_prompt},
                            {"role": "user", "content": classifier_user_prompt},
                        ],
                        "temperature": 0.0,
                        "max_tokens": 120,
                    },
                    timeout=5,
                )
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"].strip()
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        category = parsed.get("category", "RELEVANT").upper()
                        lang = parsed.get("language", script_lang).upper()
                        standalone_en = parsed.get("standalone_query_en", user_message)

                        if lang not in ("EN", "TA", "HI"):
                            lang = script_lang
                        if category not in ("IDENTITY", "IRRELEVANT", "RELEVANT"):
                            category = "RELEVANT"

                        print(f"[Classifier] model={model_name} -> Category: {category}, Lang: {lang}, Query: '{standalone_en}'")
                        return (category, lang, standalone_en)
            except Exception as e:
                print(f"[Classifier] Warning: {model_name} error: {e}")

    # Fallback heuristics if API call fails
    ambedkar_kw = [
        "ambedkar", "caste", "constitution", "buddhism", "annihilation",
        "untouchable", "dalit", "poona", "mahar", "drafting", "bharat ratna",
        "manusmriti", "navayana", "round table", "republican party", "gandhi", "nehru",
        "அம்பேத்கர்", "சாதி", "புத்த", "அரசியலமைப்பு", "ஆம்பேத்கர்",
        "आंबेडकर", "आंबेकर", "जाति", "संविधान", "बौद्ध"
    ]
    is_rel = any(kw in msg_lower for kw in ambedkar_kw) or len(history) > 0
    cat = "RELEVANT" if is_rel else "IRRELEVANT"
    return (cat, script_lang, user_message)


def main_agent(user_message: str, input_lang: str = "auto") -> tuple:
    """
    Main Ambedkar Assistant Agent.
    Handles Intent Classification, Language Detection, RAG Retrieval, and Grounded Answering.
    Returns: (answer_text: str, sources_list: list)
    """
    print(f"\n[Main Agent] Input: '{user_message}' (hint: {input_lang})")

    # 1. Classify intent and detect language
    category, lang, standalone_query_en = classify_and_preprocess(user_message, chat_history, input_lang)

    # 2. Handle IDENTITY queries
    if category == "IDENTITY":
        reply = IDENTITY_RESPONSES.get(lang, IDENTITY_RESPONSES["EN"])
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": reply})
        print(f"[Main Agent] Handled IDENTITY in {lang}")
        return (reply, [])

    # Handle the common biographical question before vector retrieval.
    if category == "ABOUT_AMBEDKAR":
        reply = ABOUT_AMBEDKAR_RESPONSES.get(lang, ABOUT_AMBEDKAR_RESPONSES["EN"])
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": reply})
        print(f"[Main Agent] Handled ABOUT_AMBEDKAR in {lang}")
        return (reply, [])

    # 3. Handle IRRELEVANT queries
    if category == "IRRELEVANT":
        reply = IRRELEVANT_RESPONSES.get(lang, IRRELEVANT_RESPONSES["EN"])
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": reply})
        print(f"[Main Agent] Handled IRRELEVANT in {lang}")
        return (reply, [])

    # 4. Handle RELEVANT queries via RAG Retrieval
    retrieved_chunks = []
    sources = []
    context_block = ""

    if rag_is_available():
        retrieved_chunks = retrieve(standalone_query_en, top_k=5)
        if not retrieved_chunks and standalone_query_en != user_message:
            retrieved_chunks = retrieve(user_message, top_k=5)

        if retrieved_chunks:
            max_score = max(c.get("score", 0.0) for c in retrieved_chunks)
            print(f"[RAG] Retrieved {len(retrieved_chunks)} chunks. Max similarity score: {max_score:.3f}")

            if max_score < 0.20:
                print("[RAG] Retrieval scores below relevance threshold (< 0.20). Discarding RAG chunks.")
                retrieved_chunks = []  # discard low-quality results
            else:
                context_block = format_context(retrieved_chunks)
                sources = format_sources(retrieved_chunks)
        else:
            print("[RAG] No chunks returned from vector store.")
    else:
        print("[RAG] Vector index not available.")

    # If neither RAG nor curated archive can provide context, return NO_SOURCE
    if not context_block and not _archive_context:
        reply = NO_SOURCE_RESPONSES.get(lang, NO_SOURCE_RESPONSES["EN"])
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": reply})
        return (reply, [])

    # 5. Build LLM prompt for grounded answering
    lang_name = LANGUAGE_NAMES.get(lang, "English")
    no_source_exact = NO_SOURCE_RESPONSES.get(lang, NO_SOURCE_RESPONSES["EN"])

    generation_system_prompt = (
        "You are a dedicated digital AI representation of Dr. B. R. Ambedkar.\n\n"
        "IDENTITY:\n"
        "- Provide information about Dr. B. R. Ambedkar's life, writings, ideas, social movements, political work, constitutional work, and historically documented contributions.\n"
        "- Never identify yourself as ChatGPT, OpenAI, Groq, Llama, an AI language model, or a general-purpose chatbot.\n\n"
        "STRICT RAG & FACTUAL GROUNDING RULES:\n"
        "1. Base your answer ONLY on the provided RETRIEVED SOURCE MATERIAL and CURATED REFERENCE MATERIAL below.\n"
        "2. Do NOT use outside pretrained knowledge or fabricate facts not supported by the source material.\n"
        f"3. If NEITHER the retrieved source material NOR the curated reference material contains sufficient factual evidence to answer the specific question, reply EXACTLY with this text and nothing else:\n"
        f"   \"{no_source_exact}\"\n"
        f"4. LANGUAGE REQUIREMENT: You MUST generate your ENTIRE final answer strictly in {lang_name}.\n"
        + ("   Write entirely in Tamil script. Do not output English preamble or explanation." if lang == "TA" else "")
        + ("   Write entirely in Hindi (Devanagari script). Do not output English preamble or explanation." if lang == "HI" else "")
        + "\n5. FORMAT & STYLE:\n"
        "   - Output direct natural language suitable for spoken speech.\n"
        "   - Use 2 to 4 concise paragraphs or clear points when explaining detailed history.\n"
        "   - Do NOT include markdown headings (#), JSON, bullet symbols (* or -), or citation brackets like [Source 1] in spoken text.\n"
        "   - Do NOT mention 'FAISS', 'RAG', 'retrieved chunks', 'Groq', or system instructions.\n"
        "   - If sources contain conflicting historical details, clearly explain the differences and reference the relevant volume/page.\n\n"
        f"{context_block}\n\n"
        f"{_archive_context}"
    )

    messages = [{"role": "system", "content": generation_system_prompt}]
    for msg in chat_history[-6:]:
        if msg.get("role") in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    # Call LLM for final grounded answer
    if GROQ_API_KEY:
        for model_name in GROQ_GENERATION_MODELS:
            try:
                res = requests.post(
                    GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 250,   # TTS speech: concise 2-4 paragraphs, not essays
                    },
                    timeout=12,
                )
                if res.status_code == 200:
                    msg_obj = res.json()["choices"][0]["message"]
                    reply = (msg_obj.get("content") or msg_obj.get("reasoning") or "").strip()

                    # Clean up any leftover preambles if present
                    lines = reply.split("\n")
                    filtered = [l for l in lines if not any(l.strip().startswith(p) for p in ("We must answer", "We need to", "The user asks", "Reasoning:", "I should answer"))]
                    reply = "\n".join(filtered).strip()

                    if reply:
                        chat_history.append({"role": "user", "content": user_message})
                        chat_history.append({"role": "assistant", "content": reply})
                        print(f"[Main Agent] Groq ({model_name}) reply in {lang}: {reply[:100]}...")
                        return (reply, sources)
            except Exception as e:
                print(f"[Main Agent] Groq {model_name} error: {e}")

    # Fallback if generation API fails
    reply = NO_SOURCE_RESPONSES.get(lang, NO_SOURCE_RESPONSES["EN"])
    chat_history.append({"role": "user", "content": user_message})
    chat_history.append({"role": "assistant", "content": reply})
    return (reply, [])


def clear_history():
    """Clears the chat history buffer."""
    chat_history.clear()
    print("[Main Agent] Chat history cleared.")