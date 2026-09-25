import os
import re
import json
import time
import base64
import asyncio
import tempfile
import hashlib
import urllib.parse
from typing import Any, Dict, List, Optional

import requests
import edge_tts
import streamlit as st
from groq import Groq


# ============================================================
# STORY STUDIO — ENTERPRISE EDITION
# Architecture:
#   1. Story library / existing stories
#   2. Story generation service
#   3. Scene planner
#   4. Visual generation with persistent cache
#   5. Narrator / character presentation
#   6. Explicit audio generation
#
# Important design choice:
# Never let an LLM directly mutate Streamlit CSS/state.
# AI returns structured content; application code controls UI.
# ============================================================

st.set_page_config(
    page_title="Story Studio",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Environment / product config
# -----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

MAX_HISTORY = 40
MAX_PROMPT_LENGTH = 3000
MAX_STORY_CHARS = 18000
IMAGE_TIMEOUT = 25
IMAGE_RETRIES = 3

LANGUAGES = [
    "English", "Tamil", "Hindi", "Telugu", "Malayalam",
    "Kannada", "Bengali", "Marathi", "Gujarati", "French",
    "German", "Spanish",
]

ART_STYLES = {
    "Illustrated": "polished editorial digital illustration, warm professional storybook art",
    "Cartoon": "friendly high-quality cartoon illustration, expressive characters, clean shapes",
    "Comic": "professional comic-book illustration, expressive characters, clean ink",
    "Cinematic": "cinematic digital artwork, detailed environment, natural lighting",
    "3D": "high-quality 3D rendered illustration, soft studio lighting, polished materials",
}

NARRATORS = {
    "Story Guide": {
        "voice": "en-US-ChristopherNeural",
        "description": "Calm professional storyteller",
        "avatar": "📖",
    },
    "Emma": {
        "voice": "en-US-AriaNeural",
        "description": "Warm and friendly narrator",
        "avatar": "👩‍🏫",
    },
    "Sofia": {
        "voice": "en-US-JennyNeural",
        "description": "Expressive character narrator",
        "avatar": "👧",
    },
    "Indian English": {
        "voice": "en-IN-NeerjaNeural",
        "description": "Natural Indian English narration",
        "avatar": "🎙️",
    },
}

# Existing built-in stories.
# Replace these with database/Supabase records later.
STARTER_STORIES = [
    {
        "id": "moon_lantern",
        "title": "The Moon Lantern",
        "description": "A child discovers a lantern that can illuminate forgotten memories.",
        "prompt": "A young child discovers an old moon-shaped lantern in the attic. The lantern reveals beautiful memories from the child's family history.",
        "style": "Cartoon",
        "narrator": "Emma",
    },
    {
        "id": "little_robot",
        "title": "The Little Robot",
        "description": "A small robot learns that helping others is more valuable than being perfect.",
        "prompt": "A small friendly robot in a colorful town tries to become perfect, but eventually learns that helping people matters more than perfection.",
        "style": "3D",
        "narrator": "Story Guide",
    },
    {
        "id": "forest_friend",
        "title": "The Forest Friend",
        "description": "A curious child meets a gentle creature deep inside a magical forest.",
        "prompt": "A curious child enters a magical forest and meets a gentle creature who needs help finding its way home.",
        "style": "Illustrated",
        "narrator": "Sofia",
    },
]

# -----------------------------
# Session state
# -----------------------------
DEFAULTS = {
    "history": [],
    "stories": {},
    "image_cache": {},
    "audio_cache": {},
    "language": "English",
    "art_style": "Illustrated",
    "narrator": "Story Guide",
    "generate_images": True,
    "current_story_id": None,
    "pending_story": None,
    "last_error": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

for item in STARTER_STORIES:
    st.session_state.stories.setdefault(item["id"], item)


# ============================================================
# Clean enterprise UI
# ============================================================
st.markdown(
    """
<style>
:root {
    --blue: #1769e0;
    --blue-dark: #123f82;
    --blue-soft: #eef5ff;
    --text: #182235;
    --muted: #64748b;
    --border: #dbe4f0;
    --surface: #ffffff;
    --surface-soft: #f7faff;
    --green: #15803d;
}

.stApp {
    background: #f5f8fc;
    color: var(--text);
}

.block-container {
    max-width: 1240px;
    padding-top: 1.5rem;
    padding-bottom: 4rem;
}

.hero {
    background: linear-gradient(135deg, #ffffff 0%, #eef5ff 100%);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 28px 30px;
    margin-bottom: 20px;
    box-shadow: 0 8px 30px rgba(28, 67, 115, 0.07);
}

.hero-title {
    color: #123f82;
    font-size: 2.25rem;
    font-weight: 800;
    letter-spacing: -0.04em;
}

.hero-subtitle {
    color: var(--muted);
    margin-top: 6px;
}

.product-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 15px;
    padding: 18px;
    box-shadow: 0 5px 20px rgba(28, 67, 115, 0.05);
}

.story-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 26px;
    line-height: 1.75;
    box-shadow: 0 7px 25px rgba(28, 67, 115, 0.05);
}

.scene-header {
    color: var(--blue);
    font-weight: 750;
    font-size: 0.86rem;
    margin-bottom: 4px;
}

.character-card {
    background: #f8fbff;
    border: 1px solid #cfe0f7;
    border-radius: 16px;
    padding: 18px;
    text-align: center;
}

.character-avatar {
    font-size: 3.5rem;
    line-height: 1;
    margin-bottom: 8px;
}

.character-name {
    color: #123f82;
    font-weight: 750;
}

.character-status {
    color: var(--muted);
    font-size: 0.85rem;
}

.metric {
    background: white;
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 13px;
    text-align: center;
}

.metric-value {
    color: #123f82;
    font-size: 1.3rem;
    font-weight: 800;
}

.metric-label {
    color: var(--muted);
    font-size: 0.75rem;
}

div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div {
    background: white !important;
    border-color: var(--border) !important;
    border-radius: 10px !important;
}

div[data-baseweb="input"]:focus-within > div,
div[data-baseweb="textarea"]:focus-within > div,
div[data-baseweb="select"]:focus-within > div {
    border-color: var(--blue) !important;
    box-shadow: 0 0 0 2px rgba(23, 105, 224, .10) !important;
}

.stButton > button,
.stFormSubmitButton > button {
    border-radius: 9px !important;
    min-height: 40px;
    border: 1px solid #c8d8ee !important;
    background: white !important;
    color: #174a8b !important;
    font-weight: 650 !important;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover {
    border-color: var(--blue) !important;
    background: var(--blue-soft) !important;
}

[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid var(--border);
}

.stChatMessage {
    border-radius: 14px;
}

audio {
    width: 100%;
}

hr {
    border-color: var(--border);
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# Core helpers
# ============================================================
def get_client() -> Optional[Groq]:
    return Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def clean_prompt(value: str) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    return value[:MAX_PROMPT_LENGTH]


def stable_hash(*parts: str) -> str:
    return hashlib.sha256("||".join(parts).encode()).hexdigest()[:24]


def safe_error(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:500] if text else "Unexpected error."


def extract_json(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("AI returned invalid structured data.")

    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("AI response was not an object.")
    return value


def normalize_story_result(data: Dict[str, Any]) -> Dict[str, Any]:
    story = str(data.get("story", "")).strip()
    scenes = data.get("scenes", [])

    if not story:
        raise ValueError("The story response was empty.")

    normalized_scenes = []
    if isinstance(scenes, list):
        for item in scenes:
            if isinstance(item, dict):
                prompt = str(item.get("visual_prompt", "")).strip()
                if prompt:
                    normalized_scenes.append({
                        "title": str(item.get("title", "Scene")).strip(),
                        "visual_prompt": prompt[:500],
                    })

    # Fallback if the model omitted the scene array.
    if not normalized_scenes:
        for idx, prompt in enumerate(
            re.findall(r"\[SCENE:\s*(.*?)\]", story, flags=re.DOTALL),
            start=1,
        ):
            normalized_scenes.append({
                "title": f"Scene {idx}",
                "visual_prompt": prompt.strip()[:500],
            })

    clean_story = re.sub(
        r"\[SCENE:\s*(.*?)\]",
        "",
        story,
        flags=re.DOTALL,
    )
    clean_story = re.sub(r"\n{3,}", "\n\n", clean_story).strip()

    return {
        "story": clean_story[:MAX_STORY_CHARS],
        "scenes": normalized_scenes[:8],
        "title": str(data.get("title", "Untitled Story")).strip()[:120],
        "mood": str(data.get("mood", "warm")).strip()[:50],
    }


# ============================================================
# Story service
# ============================================================
def generate_story(prompt: str, language: str, narrator: str) -> Dict[str, Any]:
    client = get_client()
    if not client:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    narrator_description = NARRATORS[narrator]["description"]

    system_prompt = f"""
You are Story Studio's professional story generation service.

Create a complete, coherent story for the user.

Language: {language}
Narrator style: {narrator_description}

Return ONLY valid JSON:
{{
  "title": "short story title",
  "mood": "one-word mood",
  "story": "complete story text",
  "scenes": [
    {{
      "title": "short scene title",
      "visual_prompt": "detailed description of what should appear in the illustration"
    }}
  ]
}}

Rules:
- 500–1800 words depending on the request.
- Use clear paragraphs.
- Create 2–6 scenes.
- Visual prompts must describe visible characters, setting, action, lighting and composition.
- Keep the same characters visually consistent across scenes.
- Never place text, subtitles, logos or watermarks inside image prompts.
- Do not return markdown or code fences.
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": clean_prompt(prompt)},
        ],
        temperature=0.72,
        max_tokens=5000,
    )

    return normalize_story_result(
        extract_json(response.choices[0].message.content)
    )


# ============================================================
# Visual generation service
# ============================================================
def fetch_image(scene_prompt: str, style_name: str) -> Optional[bytes]:
    key = stable_hash(scene_prompt, style_name)

    if key in st.session_state.image_cache:
        return st.session_state.image_cache[key]

    style = ART_STYLES.get(style_name, ART_STYLES["Illustrated"])

    prompt = (
        f"{scene_prompt}. {style}. "
        "Professional composition, consistent character appearance, "
        "clean background separation, no text, no watermark."
    )

    encoded = urllib.parse.quote(prompt[:900])
    seed = int(key[:8], 16) % 1000000

    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1024&height=576&nologo=true&seed={seed}&model=flux"
    )

    for attempt in range(IMAGE_RETRIES):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "StoryStudio/1.0"},
                timeout=IMAGE_TIMEOUT,
            )
            if response.ok and response.content:
                st.session_state.image_cache[key] = response.content
                return response.content
        except requests.RequestException:
            if attempt < IMAGE_RETRIES - 1:
                time.sleep(1 + attempt)

    return None


# ============================================================
# Narration service
# ============================================================
async def create_audio_file(text: str, voice: str, path: str):
    await edge_tts.Communicate(text, voice).save(path)


def generate_audio(text: str, narrator: str) -> Optional[bytes]:
    voice = NARRATORS[narrator]["voice"]
    key = stable_hash(text, voice)

    if key in st.session_state.audio_cache:
        return st.session_state.audio_cache[key]

    path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            path = tmp.name

        try:
            asyncio.run(create_audio_file(text, voice, path))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(create_audio_file(text, voice, path))
            finally:
                loop.close()

        with open(path, "rb") as audio:
            data = audio.read()

        st.session_state.audio_cache[key] = data
        return data

    except Exception as exc:
        st.session_state.last_error = safe_error(exc)
        return None

    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


# ============================================================
# Story persistence inside the current session
# ============================================================
def save_story(title: str, story_data: Dict[str, Any]) -> str:
    story_id = stable_hash(title, story_data["story"], str(time.time()))
    st.session_state.stories[story_id] = {
        "id": story_id,
        "title": title,
        "description": story_data["story"][:180],
        "prompt": "",
        "story": story_data["story"],
        "scenes": story_data["scenes"],
        "mood": story_data.get("mood", "warm"),
        "style": st.session_state.art_style,
        "narrator": st.session_state.narrator,
    }
    return story_id


def load_story(story_id: str):
    story = st.session_state.stories.get(story_id)
    if not story:
        return

    st.session_state.current_story_id = story_id
    if "story" in story:
        st.session_state.pending_story = story



# ============================================================
# ENTERPRISE PRODUCT SHELL
# UI/UX direction:
# - calm blue/white SaaS visual language
# - clear hierarchy and fewer competing actions
# - library-first information architecture
# - prominent primary CTA
# - separate "read", "create", and "manage" workflows
# - narrator treated as a product character, not a technical widget
# ============================================================

st.markdown(
    """
<style>
:root {
    --brand: #2563eb;
    --brand-dark: #1d4ed8;
    --brand-50: #eff6ff;
    --ink: #0f172a;
    --ink-2: #334155;
    --muted: #64748b;
    --line: #e2e8f0;
    --page: #f8fafc;
    --card: #ffffff;
    --success: #15803d;
    --warning: #b45309;
}

/* ---------- App shell ---------- */
.stApp {
    background: var(--page);
    color: var(--ink);
}

.block-container {
    max-width: 1280px;
    padding: 1.5rem 2rem 5rem;
}

header[data-testid="stHeader"] {
    background: rgba(248,250,252,.92);
}

/* ---------- Typography ---------- */
h1, h2, h3, h4 {
    color: var(--ink) !important;
    letter-spacing: -0.025em !important;
}

p, label, .stCaption {
    color: var(--ink-2);
}

/* ---------- Top navigation ---------- */
.topbar {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:24px;
    padding:12px 0 24px;
}

.brand {
    display:flex;
    align-items:center;
    gap:11px;
    font-weight:800;
    color:#123b78;
    font-size:1.05rem;
}

.brand-mark {
    width:34px;
    height:34px;
    display:grid;
    place-items:center;
    border-radius:10px;
    background:var(--brand);
    color:white;
    font-size:17px;
    box-shadow:0 6px 18px rgba(37,99,235,.22);
}

.nav-note {
    color:var(--muted);
    font-size:.82rem;
}

/* ---------- Hero ---------- */
.hero {
    position:relative;
    overflow:hidden;
    background:
        radial-gradient(circle at 90% 15%, rgba(37,99,235,.13), transparent 30%),
        linear-gradient(135deg,#ffffff 0%,#f3f7ff 100%);
    border:1px solid var(--line);
    border-radius:22px;
    padding:42px;
    min-height:300px;
    box-shadow:0 16px 45px rgba(15,23,42,.06);
    margin-bottom:24px;
}

.hero-eyebrow {
    display:inline-block;
    color:var(--brand-dark);
    background:var(--brand-50);
    border:1px solid #dbeafe;
    padding:6px 10px;
    border-radius:999px;
    font-size:.76rem;
    font-weight:750;
    margin-bottom:16px;
}

.hero-title {
    max-width:720px;
    color:#102d5c;
    font-size:2.65rem;
    line-height:1.08;
    font-weight:850;
    letter-spacing:-.045em;
    margin:0;
}

.hero-copy {
    max-width:650px;
    color:var(--muted);
    font-size:1.02rem;
    line-height:1.65;
    margin-top:14px;
}

.hero-meta {
    display:flex;
    gap:9px;
    flex-wrap:wrap;
    margin-top:22px;
}

.pill {
    border:1px solid var(--line);
    background:white;
    color:#475569;
    border-radius:999px;
    padding:6px 10px;
    font-size:.75rem;
}

/* ---------- Cards ---------- */
.card {
    background:var(--card);
    border:1px solid var(--line);
    border-radius:16px;
    padding:20px;
    box-shadow:0 7px 24px rgba(15,23,42,.045);
}

.card-title {
    color:var(--ink);
    font-weight:760;
    font-size:1rem;
}

.card-subtitle {
    color:var(--muted);
    font-size:.84rem;
    margin-top:4px;
}

.section-head {
    display:flex;
    justify-content:space-between;
    align-items:end;
    margin:30px 0 13px;
}

.section-title {
    font-size:1.28rem;
    font-weight:800;
    color:var(--ink);
}

.section-note {
    color:var(--muted);
    font-size:.82rem;
}

/* ---------- Story cards ---------- */
.story-tile {
    background:white;
    border:1px solid var(--line);
    border-radius:15px;
    padding:17px;
    min-height:150px;
    box-shadow:0 5px 20px rgba(15,23,42,.035);
}

.story-icon {
    width:40px;
    height:40px;
    display:grid;
    place-items:center;
    border-radius:11px;
    background:var(--brand-50);
    margin-bottom:13px;
    font-size:19px;
}

.story-title {
    font-weight:780;
    color:var(--ink);
    margin-bottom:5px;
}

.story-description {
    color:var(--muted);
    font-size:.82rem;
    line-height:1.5;
}

/* ---------- Reader ---------- */
.reader {
    background:white;
    border:1px solid var(--line);
    border-radius:18px;
    padding:32px;
    box-shadow:0 8px 28px rgba(15,23,42,.05);
}

.reader-title {
    font-size:1.85rem;
    font-weight:820;
    color:#123b78;
    margin-bottom:15px;
}

.reader-copy {
    color:#334155;
    line-height:1.9;
    font-size:1.03rem;
}

/* ---------- Character ---------- */
.character {
    background:linear-gradient(180deg,#ffffff,#f6f9ff);
    border:1px solid #dbe7f7;
    border-radius:17px;
    padding:21px;
    text-align:center;
}

.avatar {
    width:74px;
    height:74px;
    margin:0 auto 12px;
    display:grid;
    place-items:center;
    border-radius:50%;
    background:#eaf2ff;
    font-size:34px;
}

.character-name {
    font-weight:800;
    color:#123b78;
}

.character-role {
    color:var(--muted);
    font-size:.8rem;
    margin-top:3px;
}

/* ---------- Metrics ---------- */
.metric {
    background:white;
    border:1px solid var(--line);
    border-radius:14px;
    padding:15px;
}

.metric-number {
    font-size:1.35rem;
    color:#123b78;
    font-weight:820;
}

.metric-label {
    font-size:.75rem;
    color:var(--muted);
    margin-top:2px;
}

/* ---------- Controls ---------- */
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div {
    background:#fff !important;
    border-color:var(--line) !important;
    border-radius:10px !important;
}

div[data-baseweb="input"]:focus-within > div,
div[data-baseweb="textarea"]:focus-within > div,
div[data-baseweb="select"]:focus-within > div {
    border-color:var(--brand) !important;
    box-shadow:0 0 0 2px rgba(37,99,235,.10) !important;
}

.stButton > button,
.stFormSubmitButton > button {
    min-height:42px;
    border-radius:9px !important;
    border:1px solid #cbd5e1 !important;
    background:white !important;
    color:#1e4f91 !important;
    font-weight:680 !important;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover {
    border-color:var(--brand) !important;
    background:var(--brand-50) !important;
}

[data-testid="stSidebar"] {
    background:#fff;
    border-right:1px solid var(--line);
}

[data-testid="stSidebar"] .block-container {
    padding:1.25rem;
}

audio {
    width:100%;
}

hr {
    border-color:var(--line);
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------- Sidebar: settings, not navigation clutter ----------
with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-mark">S</div> Story Studio</div>',
        unsafe_allow_html=True,
    )
    st.caption("Professional AI storytelling workspace")

    st.markdown("---")
    st.markdown("#### Creation settings")

    st.session_state.language = st.selectbox(
        "Language",
        LANGUAGES,
        index=LANGUAGES.index(st.session_state.language),
    )

    st.session_state.art_style = st.selectbox(
        "Illustration style",
        list(ART_STYLES),
        index=list(ART_STYLES).index(st.session_state.art_style),
    )

    st.session_state.narrator = st.selectbox(
        "Narrator",
        list(NARRATORS),
        index=list(NARRATORS).index(st.session_state.narrator),
    )

    st.session_state.generate_images = st.toggle(
        "Create illustrations",
        value=st.session_state.generate_images,
    )

    narrator = NARRATORS[st.session_state.narrator]
    st.markdown(
        f"""
        <div class="character">
            <div class="avatar">{narrator["avatar"]}</div>
            <div class="character-name">{st.session_state.narrator}</div>
            <div class="character-role">{narrator["description"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    if st.button("Clear workspace", use_container_width=True):
        st.session_state.history = []
        st.session_state.pending_story = None
        st.session_state.current_story_id = None
        st.rerun()

    st.caption(
        "AI service: " +
        ("Connected" if GROQ_API_KEY else "Setup required")
    )

# ---------- Top bar ----------
st.markdown(
    """
<div class="topbar">
    <div class="brand">
        <div class="brand-mark">S</div>
        Story Studio
    </div>
    <div class="nav-note">Create · Read · Listen</div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------- Primary product hero ----------
st.markdown(
    """
<div class="hero">
    <div class="hero-eyebrow">AI STORYTELLING PLATFORM</div>
    <div class="hero-title">Stories that feel alive.</div>
    <div class="hero-copy">
        Create original stories, build illustrated scenes and let a
        professional AI narrator bring every chapter to life.
    </div>
    <div class="hero-meta">
        <span class="pill">✦ AI story generation</span>
        <span class="pill">◉ Illustrated scenes</span>
        <span class="pill">▶ Character narration</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------- High-level workspace metrics ----------
m1, m2, m3, m4 = st.columns(4)
metrics = [
    (len(st.session_state.stories), "Stories"),
    (len(st.session_state.image_cache), "Illustrations cached"),
    (len(st.session_state.audio_cache), "Narrations cached"),
    ("Ready" if GROQ_API_KEY else "Setup", "Workspace"),
]
for col, (value, label) in zip((m1, m2, m3, m4), metrics):
    with col:
        st.markdown(
            f'<div class="metric"><div class="metric-number">{value}</div>'
            f'<div class="metric-label">{label}</div></div>',
            unsafe_allow_html=True,
        )

# ---------- Main workspace tabs ----------
library_tab, create_tab, reader_tab = st.tabs(
    ["Story Library", "Create Story", "Reader"]
)

# ============================================================
# LIBRARY
# ============================================================
with library_tab:
    st.markdown(
        '<div class="section-head"><div><div class="section-title">Your stories</div>'
        '<div class="section-note">Open a story to read, illustrate or narrate it.</div></div></div>',
        unsafe_allow_html=True,
    )

    stories = list(st.session_state.stories.values())

    if not stories:
        st.info("Your story library is empty. Create your first story.")
    else:
        cols = st.columns(3)

        for idx, item in enumerate(stories):
            with cols[idx % 3]:
                st.markdown(
                    f"""
                    <div class="story-tile">
                        <div class="story-icon">📖</div>
                        <div class="story-title">{item["title"]}</div>
                        <div class="story-description">
                            {item.get("description", "")[:150]}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(
                    "Open",
                    key=f"library_open_{item['id']}",
                    use_container_width=True,
                ):
                    load_story(item["id"])
                    st.rerun()

# ============================================================
# CREATE
# ============================================================
with create_tab:
    st.markdown(
        '<div class="section-head"><div><div class="section-title">Create a story</div>'
        '<div class="section-note">Describe the experience in your own words.</div></div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    prompt = st.text_area(
        "Story idea",
        placeholder=(
            "Example: Tell a warm adventure about a little robot "
            "who helps a lost child find their way home."
        ),
        height=130,
        label_visibility="visible",
    )

    c1, c2 = st.columns([3, 1])
    with c1:
        st.caption(
            f"{st.session_state.language} · "
            f"{st.session_state.art_style} · "
            f"{st.session_state.narrator}"
        )
    with c2:
        generate_clicked = st.button(
            "Create story",
            type="primary",
            use_container_width=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if generate_clicked:
        prompt = clean_prompt(prompt)

        if not prompt:
            st.warning("Describe the story you want to create.")
        elif not GROQ_API_KEY:
            st.error("GROQ_API_KEY is not configured.")
        else:
            with st.spinner("Creating story, characters and scenes..."):
                try:
                    result = generate_story(
                        prompt,
                        st.session_state.language,
                        st.session_state.narrator,
                    )

                    story_id = save_story(result["title"], result)
                    st.session_state.stories[story_id]["prompt"] = prompt
                    st.session_state.current_story_id = story_id
                    st.session_state.pending_story = st.session_state.stories[story_id]

                    st.session_state.history.extend([
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": result["story"]},
                    ])

                    st.rerun()
                except Exception as exc:
                    st.error(f"Story creation failed: {safe_error(exc)}")

    st.markdown(
        """
        <div class="section-head">
            <div>
                <div class="section-title">How it works</div>
                <div class="section-note">A simple workflow designed for non-technical users.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    h1, h2, h3 = st.columns(3)
    steps = [
        ("01", "Describe", "Give the story idea, characters or lesson."),
        ("02", "Create", "The story engine builds the narrative and scene plan."),
        ("03", "Bring it alive", "Generate illustrations and let your narrator tell it."),
    ]

    for col, (num, title, body) in zip((h1, h2, h3), steps):
        with col:
            st.markdown(
                f"""
                <div class="card">
                    <div style="color:#2563eb;font-weight:800;">{num}</div>
                    <div class="card-title" style="margin-top:8px;">{title}</div>
                    <div class="card-subtitle">{body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ============================================================
# READER
# ============================================================
with reader_tab:
    active = st.session_state.pending_story

    if not active:
        st.info("Open a story from the Story Library to start reading.")
    else:
        left, right = st.columns([3.2, 1])

        with left:
            st.markdown(
                f"""
                <div class="reader">
                    <div class="reader-title">{active["title"]}</div>
                    <div class="reader-copy">{active["story"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with right:
            active_narrator = NARRATORS.get(
                active.get("narrator", st.session_state.narrator),
                NARRATORS["Story Guide"],
            )

            st.markdown(
                f"""
                <div class="character">
                    <div class="avatar">{active_narrator["avatar"]}</div>
                    <div class="character-name">
                        {active.get("narrator", "Story Guide")}
                    </div>
                    <div class="character-role">
                        Your AI story narrator
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "▶ Tell this story",
                key=f"tell_{active.get('id', 'active')}",
                use_container_width=True,
            ):
                with st.spinner("Preparing narration..."):
                    audio = generate_audio(
                        active["story"],
                        active.get("narrator", st.session_state.narrator),
                    )

                if audio:
                    st.audio(audio, format="audio/mp3")
                else:
                    st.error("Narration could not be generated.")

        scenes = active.get("scenes", [])

        if scenes and st.session_state.generate_images:
            st.markdown(
                '<div class="section-head"><div><div class="section-title">Story scenes</div>'
                '<div class="section-note">Illustrations generated from the story plan.</div></div></div>',
                unsafe_allow_html=True,
            )

            for scene_idx, scene in enumerate(scenes):
                with st.container(border=True):
                    st.markdown(
                        f'<div class="scene-header">SCENE {scene_idx + 1} · '
                        f'{scene.get("title", "Scene")}</div>',
                        unsafe_allow_html=True,
                    )
                    st.caption(scene.get("visual_prompt", ""))

                    with st.spinner("Preparing illustration..."):
                        image = fetch_image(
                            scene.get("visual_prompt", ""),
                            active.get("style", st.session_state.art_style),
                        )

                    if image:
                        st.image(image, use_container_width=True)
                    else:
                        st.warning(
                            "This illustration is temporarily unavailable. "
                            "The story remains available."
                        )

# ============================================================
# Active story summary on every non-reader view
# ============================================================
if st.session_state.pending_story and "Reader" not in st.session_state:
    pass

st.markdown("---")
st.caption(
    "Story Studio · Professional AI storytelling workspace · "
    "Structured generation · Visual scenes · Character narration"
)
