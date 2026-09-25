
"""
Story Studio Enterprise v4
---------------------------
A production-oriented Streamlit storytelling workspace.

Key improvements over v3:
- .env support for GROQ_API_KEY via python-dotenv.
- Starter stories are real readable stories, not metadata-only cards.
- Library/Open flow actually loads a story and switches to Reader.
- Explicit application navigation instead of static tabs.
- Advanced multi-stage story pipeline:
    1. Story brief / story bible
    2. Narrative outline
    3. Full draft
    4. Continuity / quality pass
    5. Scene + character visual plan
- Structured JSON outputs with schema validation.
- Groq structured-output support with graceful fallback.
- Optional open-source Ollama backend.
- Deterministic caching for AI text, images and audio.
- Character consistency instructions shared across scenes.
- Scene-level narration instead of one giant opaque audio job.
- Reader progress, scene selection and per-scene narration.
- Safer HTML escaping for generated text.
- No LLM-controlled CSS or Streamlit state.
- Provider abstraction so the UI is not tied to one LLM vendor.

Run:
    pip install -r requirements.txt
    copy .env.example .env
    # Put your real GROQ_API_KEY in .env
    streamlit run story_studio_enterprise_v4.py

Optional local open-source LLM:
    Install Ollama and pull a model such as llama3.1:8b.
    Set:
        LLM_PROVIDER=auto
        OLLAMA_MODEL=llama3.1:8b
"""

import os
import re
import json
import time
import base64
import asyncio
import tempfile
import hashlib
import html
import urllib.parse
from typing import Any, Dict, List, Optional

import requests
import edge_tts
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from ollama import chat as ollama_chat
except Exception:
    ollama_chat = None


# ============================================================
# PRODUCT CONFIG
# ============================================================

st.set_page_config(
    page_title="Story Studio",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "4.0.0"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b").strip()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip()

MAX_PROMPT_LENGTH = 3000
MAX_STORY_CHARS = 22000
MAX_HISTORY = 40
MAX_SCENES = 8
IMAGE_TIMEOUT = 30
IMAGE_RETRIES = 3

LANGUAGES = [
    "English", "Tamil", "Hindi", "Telugu", "Malayalam",
    "Kannada", "Bengali", "Marathi", "Gujarati", "French",
    "German", "Spanish",
]

ART_STYLES = {
    "Illustrated": "polished editorial storybook illustration, warm professional digital art",
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


# ============================================================
# REAL STARTER STORIES
# ============================================================

STARTER_STORIES: List[Dict[str, Any]] = [
    {
        "id": "moon_lantern",
        "title": "The Moon Lantern",
        "description": "A child discovers a lantern that can illuminate forgotten memories.",
        "prompt": "A young child discovers an old moon-shaped lantern in the attic. The lantern reveals beautiful memories from the child's family history.",
        "style": "Cartoon",
        "narrator": "Emma",
        "mood": "wonder",
        "story": """Mira had always wondered why the attic was locked.

One rainy evening, while her grandmother searched for an old blanket, the attic door was left open. Mira climbed the narrow stairs and found boxes filled with photographs, ribbons, wooden toys, and a small moon-shaped lantern.

The lantern looked ordinary until Mira brushed away the dust.

A soft silver light appeared inside it.

The light did not shine on the walls. Instead, it painted a tiny scene in the air: a little girl running through the same garden behind Mira's house. The girl was laughing beside a much younger version of Mira's grandmother.

Mira called her grandmother upstairs.

For a long moment, Grandma simply stared.

“That was my sister,” she whispered. “Her name was Leela.”

The lantern showed another memory. Two sisters sitting beneath a mango tree. Another followed: the sisters making paper boats after a storm. Then another: Leela leaving the village with her family.

Mira realized that the lantern did not reveal forgotten objects. It revealed forgotten moments.

Together, Mira and Grandma spent the evening watching memories that had been hidden for years. They laughed at old mistakes, remembered people whose names had almost disappeared, and discovered stories nobody had written down.

Before bed, Mira asked, “Why did the lantern choose me?”

Grandma smiled.

“Perhaps memories need someone curious enough to listen.”

Mira placed the lantern beside her bed.

Its silver light became quiet.

But she knew that whenever someone was ready to remember, the little moon would shine again.""",
        "characters": [
            {
                "name": "Mira",
                "description": "A curious 10-year-old child with dark wavy hair, a yellow raincoat and a small blue backpack."
            },
            {
                "name": "Grandma",
                "description": "A kind elderly woman with silver hair, round glasses and a soft lavender shawl."
            },
        ],
        "scenes": [
            {
                "title": "The Hidden Attic",
                "visual_prompt": "Mira, a curious 10-year-old child with dark wavy hair, yellow raincoat and blue backpack, stands in a dusty attic filled with old boxes and photographs while holding a small moon-shaped lantern, rainy evening light through a round window, warm magical atmosphere, wide cinematic composition."
            },
            {
                "title": "The First Memory",
                "visual_prompt": "The silver moon lantern projects a glowing memory into the attic: a young girl running through a family garden beside her sister, soft silver light, Mira watching in wonder, magical particles, intimate storybook composition."
            },
            {
                "title": "Remembering Leela",
                "visual_prompt": "Mira and her elderly grandmother with silver hair, round glasses and lavender shawl sit together in the attic watching a luminous memory of two young sisters beneath a mango tree, emotional but gentle mood, warm blue-silver lighting."
            },
            {
                "title": "The Lantern Sleeps",
                "visual_prompt": "Mira places the moon-shaped lantern beside her bed at night, the lantern glowing softly while rain falls outside the window, peaceful bedroom, subtle magical light, cozy children's storybook illustration."
            },
        ],
    },
    {
        "id": "little_robot",
        "title": "The Little Robot",
        "description": "A small robot learns that helping others is more valuable than being perfect.",
        "prompt": "A small friendly robot in a colorful town tries to become perfect, but learns that helping people matters more than perfection.",
        "style": "3D",
        "narrator": "Story Guide",
        "mood": "hope",
        "story": """Pip was the smallest robot in Brightwood.

Every morning, the town's other robots completed their tasks perfectly. One painted straight lines. Another sorted every package without a mistake. Pip wanted to be perfect too.

He practiced polishing windows until they shone like mirrors.

He practiced carrying boxes without dropping a single one.

Then, one windy afternoon, a little girl named Nia ran into the square.

“My kite is stuck!” she cried.

Pip looked at the tall clock tower. The other robots calculated the safest route, but none of them could reach the kite because a narrow maintenance path had been blocked by fallen branches.

Pip was small enough to squeeze through.

He climbed carefully, moved the branches one by one, and reached the kite.

But on the way down, he slipped.

His paint became scratched.

His perfect record was ruined.

Pip expected everyone to laugh.

Instead, Nia hugged him.

“You helped me,” she said. “That's more important than being perfect.”

The next morning, Pip noticed something unusual. The town's robots were still doing their jobs, but now they were helping one another between tasks.

Pip smiled.

He finally understood that a useful robot was not the one that never made mistakes.

It was the one that noticed when someone needed help.""",
        "characters": [
            {
                "name": "Pip",
                "description": "A tiny friendly rounded robot with white metal panels, a blue chest light, expressive digital eyes and small wheels."
            },
            {
                "name": "Nia",
                "description": "A cheerful young girl with curly dark hair, a red hoodie and a bright yellow kite."
            },
        ],
        "scenes": [
            {
                "title": "Pip Practices",
                "visual_prompt": "Pip, a tiny friendly rounded robot with white metal panels, blue chest light and expressive digital eyes, carefully polishing a shop window in a colorful small town, cheerful morning, polished 3D children's animation style."
            },
            {
                "title": "The Lost Kite",
                "visual_prompt": "Nia, a cheerful young girl with curly dark hair and red hoodie, points toward a bright yellow kite trapped high on a clock tower, Pip standing beside her ready to help, colorful town square, afternoon light."
            },
            {
                "title": "The Brave Climb",
                "visual_prompt": "Tiny robot Pip squeezes through branches on a narrow clock tower maintenance path while reaching toward Nia's yellow kite, wind moving the branches, dynamic but friendly children's animation scene."
            },
            {
                "title": "More Than Perfect",
                "visual_prompt": "Nia hugs Pip in the town square after the rescue, Pip has a few harmless scratches on his white metal panels, townspeople and friendly robots smiling in the background, warm sunset, emotional 3D storybook composition."
            },
        ],
    },
    {
        "id": "forest_friend",
        "title": "The Forest Friend",
        "description": "A curious child meets a gentle creature deep inside a magical forest.",
        "prompt": "A curious child enters a magical forest and meets a gentle creature who needs help finding its way home.",
        "style": "Illustrated",
        "narrator": "Sofia",
        "mood": "wonder",
        "story": """Arun loved exploring the forest behind his village.

One morning, he followed a trail of glowing blue leaves deeper than he had ever gone. The trees became taller, the air became cooler, and tiny lights floated between the branches.

Then he heard a quiet sneeze.

Behind a mossy stone was a small creature with silver fur, leaf-shaped ears and bright green eyes.

“I am Luma,” the creature said.

Arun had never heard a forest creature speak.

Luma had become lost after a storm and could not find the Moonflower Clearing where her family lived.

Arun offered to help.

They followed streams, crossed a fallen tree, and climbed a hill where the whole forest looked like a green ocean.

At sunset, Luma noticed three stars appearing above the tallest tree.

“That is the way home,” she said.

But Arun was not sure.

The forest paths all looked the same.

Then he remembered the glowing blue leaves. They were brighter near water.

Arun followed them to a hidden stream. Across the stream was a field of enormous white flowers glowing beneath the moon.

Luma's family was waiting.

Before leaving, Luma gave Arun one silver leaf.

“Whenever you feel lost,” she said, “remember that a path can appear when you help someone else find theirs.”

Arun returned home carrying the leaf.

The next morning, the forest looked completely ordinary.

But sometimes, when the wind moved through the trees, he heard Luma laughing.""",
        "characters": [
            {
                "name": "Arun",
                "description": "A curious 11-year-old child with short dark hair, green shirt, brown shorts and a small explorer satchel."
            },
            {
                "name": "Luma",
                "description": "A gentle small forest creature with soft silver fur, leaf-shaped ears, bright green eyes and a glowing silver tail."
            },
        ],
        "scenes": [
            {
                "title": "The Blue Trail",
                "visual_prompt": "Arun, an 11-year-old curious child with short dark hair, green shirt, brown shorts and explorer satchel, follows glowing blue leaves into a magical forest, tall trees and floating lights, enchanting illustrated storybook style."
            },
            {
                "title": "Meeting Luma",
                "visual_prompt": "Arun kneels beside a mossy stone and meets Luma, a small gentle creature with silver fur, leaf-shaped ears, bright green eyes and glowing silver tail, shafts of forest light, friendly magical atmosphere."
            },
            {
                "title": "Across the Forest",
                "visual_prompt": "Arun and Luma carefully cross a fallen tree above a sparkling stream, giant trees and tiny floating lights surrounding them, adventurous but gentle children's illustration."
            },
            {
                "title": "The Moonflower Clearing",
                "visual_prompt": "Under a full moon, Arun and Luma arrive at a clearing filled with enormous glowing white moonflowers while Luma's family waits nearby, magical forest night, luminous blue-green atmosphere."
            },
        ],
    },
]


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "stories": {},
    "image_cache": {},
    "audio_cache": {},
    "text_cache": {},
    "history": [],
    "language": "English",
    "art_style": "Illustrated",
    "narrator": "Story Guide",
    "generate_images": True,
    "current_story_id": None,
    "pending_story": None,
    "view": "Library",
    "selected_scene": 0,
    "last_error": None,
    "generation_meta": {},
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

for starter in STARTER_STORIES:
    st.session_state.stories.setdefault(starter["id"], starter)


# ============================================================
# UI CSS
# ============================================================

st.markdown(
    """
<style>
:root {
    --blue:#2563eb;
    --blue-dark:#123f82;
    --blue-soft:#eff6ff;
    --text:#0f172a;
    --muted:#64748b;
    --line:#dbe4f0;
    --page:#f5f8fc;
    --card:#ffffff;
}

.stApp { background:var(--page); color:var(--text); }

.block-container {
    max-width:1280px;
    padding:1.3rem 2rem 4rem;
}

h1,h2,h3,h4 { color:var(--text)!important; letter-spacing:-.025em; }

[data-testid="stSidebar"] {
    background:#fff;
    border-right:1px solid var(--line);
}

[data-testid="stSidebar"] .block-container { padding:1.2rem; }

.brand {
    display:flex;
    align-items:center;
    gap:10px;
    font-weight:800;
    color:var(--blue-dark);
}

.brand-mark {
    width:35px;height:35px;
    display:grid;place-items:center;
    border-radius:10px;
    background:var(--blue);
    color:#fff;
    font-weight:900;
    box-shadow:0 7px 20px rgba(37,99,235,.22);
}

.topbar {
    display:flex;
    justify-content:space-between;
    align-items:center;
    padding:10px 0 20px;
}

.hero {
    background:
        radial-gradient(circle at 90% 10%,rgba(37,99,235,.14),transparent 30%),
        linear-gradient(135deg,#fff,#eef5ff);
    border:1px solid var(--line);
    border-radius:22px;
    padding:38px;
    margin-bottom:20px;
    box-shadow:0 12px 40px rgba(15,23,42,.06);
}

.eyebrow {
    display:inline-block;
    padding:6px 10px;
    border-radius:999px;
    background:var(--blue-soft);
    border:1px solid #dbeafe;
    color:#1d4ed8;
    font-size:.75rem;
    font-weight:800;
}

.hero-title {
    font-size:2.65rem;
    line-height:1.06;
    font-weight:850;
    letter-spacing:-.05em;
    color:#102d5c;
    margin-top:14px;
}

.hero-copy {
    max-width:720px;
    color:var(--muted);
    line-height:1.65;
    font-size:1rem;
    margin-top:13px;
}

.pills { display:flex; gap:8px; flex-wrap:wrap; margin-top:20px; }
.pill {
    padding:6px 10px;
    border:1px solid var(--line);
    background:#fff;
    border-radius:999px;
    color:#475569;
    font-size:.75rem;
}

.card,.story-tile,.reader,.character,.metric,.pipeline {
    background:#fff;
    border:1px solid var(--line);
    border-radius:16px;
    box-shadow:0 6px 24px rgba(15,23,42,.045);
}

.card { padding:20px; }
.story-tile { padding:18px; min-height:160px; }
.reader { padding:32px; }
.character { padding:20px; text-align:center; }
.metric { padding:14px; }
.pipeline { padding:15px; }

.story-icon {
    width:42px;height:42px;
    display:grid;place-items:center;
    border-radius:12px;
    background:var(--blue-soft);
    margin-bottom:12px;
}

.story-title { font-weight:800; color:var(--text); }
.story-description { color:var(--muted); font-size:.82rem; line-height:1.5; margin-top:5px; }

.reader-title { font-size:2rem; font-weight:850; color:var(--blue-dark); }
.reader-copy { margin-top:18px; color:#334155; line-height:1.95; font-size:1.04rem; white-space:pre-line; }

.avatar {
    width:78px;height:78px;
    display:grid;place-items:center;
    margin:0 auto 12px;
    border-radius:50%;
    background:#eaf2ff;
    font-size:36px;
}

.character-name { font-weight:800; color:var(--blue-dark); }
.character-role { color:var(--muted); font-size:.8rem; margin-top:4px; }

.metric-number { font-size:1.35rem; font-weight:850; color:var(--blue-dark); }
.metric-label { color:var(--muted); font-size:.75rem; }

.scene-label {
    color:var(--blue);
    font-weight:800;
    font-size:.78rem;
    text-transform:uppercase;
    letter-spacing:.05em;
}

.scene-card {
    padding:18px;
    border:1px solid var(--line);
    border-radius:15px;
    background:#fff;
    margin-bottom:14px;
}

.pipeline-step {
    display:flex;
    align-items:center;
    gap:10px;
    color:#475569;
    font-size:.82rem;
}

.pipeline-dot {
    width:27px;height:27px;
    border-radius:50%;
    display:grid;place-items:center;
    background:var(--blue-soft);
    color:var(--blue);
    font-weight:800;
}

.stButton > button,
.stFormSubmitButton > button {
    min-height:42px;
    border-radius:10px!important;
    font-weight:700!important;
}

div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div {
    background:#fff!important;
    border-color:var(--line)!important;
    border-radius:10px!important;
}

hr { border-color:var(--line); }

audio { width:100%; }

.small-note {
    color:var(--muted);
    font-size:.78rem;
}

.status-ok { color:#15803d; font-weight:750; }
.status-warn { color:#b45309; font-weight:750; }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# CORE UTILITIES
# ============================================================

def clean_prompt(value: str) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    return value[:MAX_PROMPT_LENGTH]


def stable_hash(*parts: str) -> str:
    payload = "||".join(str(x) for x in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def safe_error(exc: Exception) -> str:
    text = str(exc).strip()
    text = re.sub(r"gsk_[A-Za-z0-9_-]+", "[REDACTED]", text)
    return text[:600] or "Unexpected error."


def safe_html(value: Any) -> str:
    return html.escape(str(value or ""))


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

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        value = json.loads(raw[start:end + 1])
        if isinstance(value, dict):
            return value

    raise ValueError("AI returned invalid structured data.")


def provider_status() -> str:
    if LLM_PROVIDER == "groq":
        return "Groq"
    if LLM_PROVIDER == "ollama":
        return "Ollama"
    if GROQ_API_KEY:
        return "Groq"
    if ollama_chat:
        return "Ollama"
    return "Unavailable"


def get_groq_client() -> Optional[Any]:
    if not GROQ_API_KEY or Groq is None:
        return None
    return Groq(api_key=GROQ_API_KEY)


def schema_response_format(name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": schema,
        },
    }


# ============================================================
# STRUCTURED SCHEMAS
# ============================================================

STORY_BIBLE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "logline": {"type": "string"},
        "theme": {"type": "string"},
        "tone": {"type": "string"},
        "setting": {"type": "string"},
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "description": {"type": "string"},
                    "goal": {"type": "string"},
                    "visual_identity": {"type": "string"},
                },
                "required": ["name", "role", "description", "goal", "visual_identity"],
                "additionalProperties": False,
            },
        },
        "conflict": {"type": "string"},
        "resolution": {"type": "string"},
    },
    "required": [
        "title", "logline", "theme", "tone", "setting",
        "characters", "conflict", "resolution"
    ],
    "additionalProperties": False,
}

OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "beat": {"type": "integer"},
                    "title": {"type": "string"},
                    "purpose": {"type": "string"},
                    "events": {"type": "array", "items": {"type": "string"}},
                    "emotion": {"type": "string"},
                },
                "required": ["beat", "title", "purpose", "events", "emotion"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["beats"],
    "additionalProperties": False,
}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "story": {"type": "string"},
        "ending": {"type": "string"},
    },
    "required": ["story", "ending"],
    "additionalProperties": False,
}

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "story": {"type": "string"},
        "editor_notes": {"type": "array", "items": {"type": "string"}},
        "quality_score": {"type": "integer"},
    },
    "required": ["story", "editor_notes", "quality_score"],
    "additionalProperties": False,
}

SCENES_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "story_excerpt": {"type": "string"},
                    "visual_prompt": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "location": {"type": "string"},
                    "time_of_day": {"type": "string"},
                    "camera": {"type": "string"},
                },
                "required": [
                    "title", "story_excerpt", "visual_prompt",
                    "characters", "location", "time_of_day", "camera"
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scenes"],
    "additionalProperties": False,
}


# ============================================================
# LLM PROVIDER LAYER
# ============================================================

def call_groq_json(
    *,
    system: str,
    user: str,
    schema_name: str,
    schema: Dict[str, Any],
    temperature: float = 0.35,
    max_tokens: int = 5000,
) -> Dict[str, Any]:
    client = get_groq_client()
    if not client:
        raise RuntimeError("Groq is not configured.")

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=schema_response_format(schema_name, schema),
    )
    return extract_json(response.choices[0].message.content)


def call_groq_json_fallback(
    *,
    system: str,
    user: str,
    temperature: float = 0.35,
    max_tokens: int = 5000,
) -> Dict[str, Any]:
    """Fallback for older Groq models that do not support strict schemas."""
    client = get_groq_client()
    if not client:
        raise RuntimeError("Groq is not configured.")

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system + "\nReturn ONLY valid JSON."},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return extract_json(response.choices[0].message.content)


def call_ollama_json(
    *,
    system: str,
    user: str,
    schema: Dict[str, Any],
    temperature: float = 0.35,
) -> Dict[str, Any]:
    if ollama_chat is None:
        raise RuntimeError(
            "Ollama Python package is not installed. Install 'ollama' "
            "or configure Groq in .env."
        )

    response = ollama_chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        format=schema,
        options={"temperature": temperature},
    )

    content = getattr(getattr(response, "message", None), "content", None)
    if not content:
        raise RuntimeError("Ollama returned an empty response.")
    return extract_json(content)


def llm_json(
    *,
    system: str,
    user: str,
    schema_name: str,
    schema: Dict[str, Any],
    temperature: float = 0.35,
    max_tokens: int = 5000,
) -> Dict[str, Any]:
    """
    Provider strategy:
      groq   -> Groq only
      ollama -> Ollama only
      auto   -> Groq when key exists, otherwise Ollama
    """
    provider = LLM_PROVIDER

    if provider == "groq":
        try:
            return call_groq_json(
                system=system,
                user=user,
                schema_name=schema_name,
                schema=schema,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as first_error:
            # A controlled compatibility fallback for models where strict
            # structured output is unavailable.
            try:
                return call_groq_json_fallback(
                    system=system,
                    user=user,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception:
                raise first_error

    if provider == "ollama":
        return call_ollama_json(
            system=system,
            user=user,
            schema=schema,
            temperature=temperature,
        )

    # auto
    if GROQ_API_KEY and Groq is not None:
        try:
            return call_groq_json(
                system=system,
                user=user,
                schema_name=schema_name,
                schema=schema,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception:
            try:
                return call_groq_json_fallback(
                    system=system,
                    user=user,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception:
                pass

    if ollama_chat is not None:
        return call_ollama_json(
            system=system,
            user=user,
            schema=schema,
            temperature=temperature,
        )

    raise RuntimeError(
        "No AI provider is available. Add GROQ_API_KEY to .env "
        "or install/configure Ollama."
    )


# ============================================================
# STORY PIPELINE
# ============================================================

def build_story_bible(prompt: str, language: str) -> Dict[str, Any]:
    system = f"""
You are the story architect for an enterprise AI storytelling platform.

Language: {language}

Transform the user's idea into a coherent story bible.

Quality requirements:
- Define a protagonist with a concrete goal.
- Define a meaningful but age-appropriate conflict.
- Create a clear emotional arc.
- Make the setting visually specific.
- Give every major character a stable visual identity.
- Avoid random character changes later.
- Prefer original, family-friendly concepts.
- Keep the theme understandable without preaching.
"""
    return llm_json(
        system=system,
        user=clean_prompt(prompt),
        schema_name="story_bible",
        schema=STORY_BIBLE_SCHEMA,
        temperature=0.3,
        max_tokens=2500,
    )


def build_outline(bible: Dict[str, Any], language: str) -> Dict[str, Any]:
    system = f"""
You are a professional narrative planner.

Language: {language}

Build a compact beginning-middle-ending story outline from the story bible.

The outline must:
- Start with a strong hook.
- Establish the protagonist and goal.
- Escalate the conflict.
- Include a meaningful turning point.
- Resolve the central problem.
- End with emotional closure.
- Preserve character motivations and visual identity.

Return only the requested structured data.
"""
    return llm_json(
        system=system,
        user=json.dumps(bible, ensure_ascii=False),
        schema_name="story_outline",
        schema=OUTLINE_SCHEMA,
        temperature=0.35,
        max_tokens=3000,
    )


def draft_story(
    bible: Dict[str, Any],
    outline: Dict[str, Any],
    language: str,
    narrator: str,
) -> Dict[str, Any]:
    narrator_style = NARRATORS[narrator]["description"]

    system = f"""
You are the lead children's/family storyteller for Story Studio.

Language: {language}
Narrator style: {narrator_style}

Write a polished original story from the supplied story bible and outline.

Writing requirements:
- 700-1800 words unless the story clearly needs less.
- Strong opening hook.
- Natural dialogue where useful.
- Show emotion through actions and sensory details.
- Keep character names and traits consistent.
- Do not introduce unexplained major characters.
- Avoid repetitive phrasing.
- Give the protagonist agency.
- Make the ending earned by earlier events.
- No markdown headings, scene labels, or meta commentary.
"""
    user = (
        "STORY BIBLE:\n"
        + json.dumps(bible, ensure_ascii=False)
        + "\n\nOUTLINE:\n"
        + json.dumps(outline, ensure_ascii=False)
    )

    return llm_json(
        system=system,
        user=user,
        schema_name="story_draft",
        schema=DRAFT_SCHEMA,
        temperature=0.72,
        max_tokens=5500,
    )


def edit_story(
    bible: Dict[str, Any],
    draft: Dict[str, Any],
    language: str,
) -> Dict[str, Any]:
    system = f"""
You are the senior story editor for a commercial storytelling product.

Language: {language}

Perform a silent editorial pass.

Check:
1. Character consistency.
2. Cause and effect.
3. Beginning, escalation and resolution.
4. Emotional continuity.
5. Age-appropriate language.
6. Repetition.
7. Awkward or confusing sentences.
8. Unnecessary exposition.
9. Whether the ending pays off the central theme.

Return the improved complete story.
Do not add meta commentary inside the story.
"""
    user = (
        "BIBLE:\n"
        + json.dumps(bible, ensure_ascii=False)
        + "\n\nDRAFT:\n"
        + draft.get("story", "")
    )

    result = llm_json(
        system=system,
        user=user,
        schema_name="story_editor",
        schema=EDIT_SCHEMA,
        temperature=0.18,
        max_tokens=6000,
    )

    result["story"] = str(result.get("story", "")).strip()
    result["quality_score"] = max(0, min(100, int(result.get("quality_score", 80))))
    return result


def plan_scenes(
    bible: Dict[str, Any],
    story: str,
    style_name: str,
) -> Dict[str, Any]:
    style = ART_STYLES.get(style_name, ART_STYLES["Illustrated"])

    system = f"""
You are the visual director for a story illustration engine.

Preferred visual style:
{style}

Create 3-{MAX_SCENES} visually distinct scenes from the story.

Hard requirements:
- Character appearance must exactly follow the story bible.
- Repeat stable visual traits in every scene where the character appears.
- Each visual prompt must describe subject, action, setting, lighting and composition.
- No text, captions, logos, watermarks or UI elements.
- Avoid vague prompts.
- Scene excerpts must correspond to real parts of the story.
"""
    user = (
        "CHARACTER BIBLE:\n"
        + json.dumps(bible.get("characters", []), ensure_ascii=False)
        + "\n\nSETTING:\n"
        + str(bible.get("setting", ""))
        + "\n\nSTORY:\n"
        + story
    )

    result = llm_json(
        system=system,
        user=user,
        schema_name="scene_plan",
        schema=SCENES_SCHEMA,
        temperature=0.28,
        max_tokens=4500,
    )

    scenes = result.get("scenes", [])
    normalized: List[Dict[str, Any]] = []

    for scene in scenes[:MAX_SCENES]:
        if not isinstance(scene, dict):
            continue
        visual = str(scene.get("visual_prompt", "")).strip()
        if not visual:
            continue

        normalized.append({
            "title": str(scene.get("title", "Scene")).strip()[:120],
            "story_excerpt": str(scene.get("story_excerpt", "")).strip()[:600],
            "visual_prompt": visual[:1200],
            "characters": [
                str(x)[:80] for x in scene.get("characters", [])
                if str(x).strip()
            ],
            "location": str(scene.get("location", ""))[:160],
            "time_of_day": str(scene.get("time_of_day", ""))[:80],
            "camera": str(scene.get("camera", ""))[:160],
        })

    if not normalized:
        raise ValueError("The visual planner returned no usable scenes.")

    return {"scenes": normalized}


def run_story_pipeline(
    prompt: str,
    language: str,
    narrator: str,
    art_style: str,
) -> Dict[str, Any]:
    """
    Full quality pipeline. The stages are intentionally separate so each
    result can later be persisted and evaluated independently.
    """
    clean = clean_prompt(prompt)
    if not clean:
        raise ValueError("Story idea cannot be empty.")

    cache_key = stable_hash(clean, language, narrator, art_style, GROQ_MODEL, OLLAMA_MODEL)

    if cache_key in st.session_state.text_cache:
        return st.session_state.text_cache[cache_key]

    bible = build_story_bible(clean, language)
    outline = build_outline(bible, language)
    draft = draft_story(bible, outline, language, narrator)
    edited = edit_story(bible, draft, language)

    story_text = str(edited.get("story", "")).strip()
    if not story_text:
        raise ValueError("Story editor returned empty content.")

    scenes = plan_scenes(bible, story_text, art_style)

    result = {
        "title": str(bible.get("title", "Untitled Story")).strip()[:120],
        "description": str(bible.get("logline", "")).strip()[:300],
        "mood": str(bible.get("tone", "warm")).strip()[:60],
        "story": story_text[:MAX_STORY_CHARS],
        "characters": bible.get("characters", []),
        "story_bible": bible,
        "outline": outline,
        "scenes": scenes["scenes"],
        "editor_notes": edited.get("editor_notes", [])[:8],
        "quality_score": int(edited.get("quality_score", 80)),
        "prompt": clean,
        "language": language,
        "style": art_style,
        "narrator": narrator,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pipeline": [
            "Brief",
            "Story Bible",
            "Outline",
            "Draft",
            "Continuity Edit",
            "Scene Plan",
        ],
    }

    st.session_state.text_cache[cache_key] = result
    return result


# ============================================================
# IMAGE SERVICE
# ============================================================

def fetch_image(scene_prompt: str, style_name: str) -> Optional[bytes]:
    key = stable_hash(scene_prompt, style_name)

    if key in st.session_state.image_cache:
        return st.session_state.image_cache[key]

    style = ART_STYLES.get(style_name, ART_STYLES["Illustrated"])
    prompt = (
        f"{scene_prompt}. "
        f"{style}. "
        "Consistent character design, professional storybook composition, "
        "clear subject separation, expressive faces, coherent environment, "
        "no text, no captions, no logos, no watermark."
    )

    encoded = urllib.parse.quote(prompt[:1500])
    seed = int(key[:8], 16) % 1_000_000

    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1024&height=576&nologo=true&seed={seed}&model=flux"
    )

    for attempt in range(IMAGE_RETRIES):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "StoryStudio/4.0"},
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
# NARRATION SERVICE
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

        if not data:
            raise RuntimeError("Narration provider returned an empty audio file.")

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
# STORY STORAGE / NAVIGATION
# ============================================================

def save_story(story_data: Dict[str, Any], story_id: Optional[str] = None) -> str:
    sid = story_id or stable_hash(
        story_data.get("title", "story"),
        story_data.get("story", ""),
        str(time.time()),
    )

    record = dict(story_data)
    record["id"] = sid
    record["description"] = (
        record.get("description")
        or record.get("story", "")[:180]
    )[:300]

    st.session_state.stories[sid] = record
    return sid


def open_story(story_id: str) -> bool:
    story = st.session_state.stories.get(story_id)
    if not story or not story.get("story"):
        return False

    st.session_state.current_story_id = story_id
    st.session_state.pending_story = story
    st.session_state.selected_scene = 0
    st.session_state.view = "Reader"
    return True


def create_story_from_starter(story_id: str) -> bool:
    return open_story(story_id)


def clear_workspace():
    st.session_state.history = []
    st.session_state.pending_story = None
    st.session_state.current_story_id = None
    st.session_state.view = "Library"
    st.session_state.selected_scene = 0
    st.session_state.last_error = None


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-mark">S</div> Story Studio</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Enterprise Storytelling · v{APP_VERSION}")

    st.markdown("---")
    st.markdown("#### Workspace")

    nav = st.radio(
        "Navigate",
        ["Library", "Create", "Reader"],
        index=["Library", "Create", "Reader"].index(st.session_state.view),
        label_visibility="collapsed",
    )
    if nav != st.session_state.view:
        st.session_state.view = nav

    st.markdown("---")
    st.markdown("#### Creation settings")

    st.session_state.language = st.selectbox(
        "Language",
        LANGUAGES,
        index=LANGUAGES.index(st.session_state.language),
    )

    st.session_state.art_style = st.selectbox(
        "Illustration style",
        list(ART_STYLES.keys()),
        index=list(ART_STYLES.keys()).index(st.session_state.art_style),
    )

    st.session_state.narrator = st.selectbox(
        "Narrator",
        list(NARRATORS.keys()),
        index=list(NARRATORS.keys()).index(st.session_state.narrator),
    )

    st.session_state.generate_images = st.toggle(
        "Create illustrations",
        value=st.session_state.generate_images,
    )

    active_narrator = NARRATORS[st.session_state.narrator]
    st.markdown(
        f"""
        <div class="character">
            <div class="avatar">{safe_html(active_narrator["avatar"])}</div>
            <div class="character-name">{safe_html(st.session_state.narrator)}</div>
            <div class="character-role">{safe_html(active_narrator["description"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    status = provider_status()
    if status == "Unavailable":
        st.markdown(
            '<div class="status-warn">AI provider not configured</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="status-ok">AI provider: {safe_html(status)}</div>',
            unsafe_allow_html=True,
        )

    st.caption(
        "Groq key is read from .env and never rendered in the UI."
    )

    if st.button("Clear workspace", use_container_width=True):
        clear_workspace()
        st.rerun()


# ============================================================
# TOP BAR / HERO
# ============================================================

st.markdown(
    """
<div class="topbar">
    <div class="brand">
        <div class="brand-mark">S</div>
        Story Studio
    </div>
    <div class="small-note">Create · Read · Illustrate · Listen</div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
    <span class="eyebrow">ENTERPRISE AI STORYTELLING</span>
    <div class="hero-title">Stories that feel alive.</div>
    <div class="hero-copy">
        Turn a simple idea into a structured story, consistent characters,
        illustrated scenes and professional narration.
    </div>
    <div class="pills">
        <span class="pill">Structured generation</span>
        <span class="pill">Character consistency</span>
        <span class="pill">Scene planning</span>
        <span class="pill">AI narration</span>
        <span class="pill">Open-source fallback</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# METRICS
# ============================================================

m1, m2, m3, m4 = st.columns(4)
metric_values = [
    (len(st.session_state.stories), "Stories"),
    (len(st.session_state.image_cache), "Images cached"),
    (len(st.session_state.audio_cache), "Narrations cached"),
    (provider_status(), "AI engine"),
]

for col, (value, label) in zip((m1, m2, m3, m4), metric_values):
    with col:
        st.markdown(
            f"""
            <div class="metric">
                <div class="metric-number">{safe_html(value)}</div>
                <div class="metric-label">{safe_html(label)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# LIBRARY VIEW
# ============================================================

if st.session_state.view == "Library":
    st.markdown("### Your story library")
    st.caption("Starter stories are immediately readable. Generated stories are added to this workspace.")

    stories = list(st.session_state.stories.values())

    cols = st.columns(3)
    for idx, item in enumerate(stories):
        with cols[idx % 3]:
            st.markdown(
                f"""
                <div class="story-tile">
                    <div class="story-icon">📖</div>
                    <div class="story-title">{safe_html(item.get("title", "Untitled"))}</div>
                    <div class="story-description">
                        {safe_html(item.get("description", ""))[:220]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "Open story",
                key=f"open_{item['id']}",
                use_container_width=True,
            ):
                if open_story(item["id"]):
                    st.rerun()

    st.markdown("---")
    st.markdown("### What happens after you create a story")

    p1, p2, p3, p4 = st.columns(4)
    steps = [
        ("01", "Story Bible", "Characters, setting, goal and conflict are defined first."),
        ("02", "Narrative", "Outline, draft and continuity editing happen as separate stages."),
        ("03", "Visuals", "Scenes inherit the same character descriptions for consistency."),
        ("04", "Narrator", "Read the story or generate narration for the complete story or a scene."),
    ]

    for col, (num, title, body) in zip((p1, p2, p3, p4), steps):
        with col:
            st.markdown(
                f"""
                <div class="card">
                    <div style="color:#2563eb;font-weight:850;">{num}</div>
                    <div style="font-weight:800;margin-top:7px;">{safe_html(title)}</div>
                    <div class="small-note" style="margin-top:5px;">{safe_html(body)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# CREATE VIEW
# ============================================================

elif st.session_state.view == "Create":
    st.markdown("### Create a story")
    st.caption("The engine uses a multi-stage pipeline instead of asking one model call to do everything.")

    st.markdown(
        """
        <div class="pipeline">
            <div class="pipeline-step"><div class="pipeline-dot">1</div>Story brief</div>
            <div style="height:8px;"></div>
            <div class="pipeline-step"><div class="pipeline-dot">2</div>Story bible</div>
            <div style="height:8px;"></div>
            <div class="pipeline-step"><div class="pipeline-dot">3</div>Outline</div>
            <div style="height:8px;"></div>
            <div class="pipeline-step"><div class="pipeline-dot">4</div>Draft</div>
            <div style="height:8px;"></div>
            <div class="pipeline-step"><div class="pipeline-dot">5</div>Continuity edit</div>
            <div style="height:8px;"></div>
            <div class="pipeline-step"><div class="pipeline-dot">6</div>Scene director</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")

    prompt = st.text_area(
        "Story idea",
        height=150,
        placeholder=(
            "Example: Create a warm adventure about a little robot "
            "who helps a lost child find the way home. Make it "
            "funny, emotional and suitable for children."
        ),
    )

    c1, c2, c3 = st.columns([1.1, 1.1, 1])
    with c1:
        st.caption(f"Language: {st.session_state.language}")
    with c2:
        st.caption(f"Style: {st.session_state.art_style}")
    with c3:
        st.caption(f"Narrator: {st.session_state.narrator}")

    generate_clicked = st.button(
        "Create professional story",
        type="primary",
        use_container_width=True,
    )

    if generate_clicked:
        clean = clean_prompt(prompt)

        if not clean:
            st.warning("Describe the story you want to create.")
        else:
            progress = st.progress(0, text="Preparing story brief...")
            try:
                progress.progress(8, text="Building story bible...")
                # Run pipeline with stage messaging. The individual functions
                # remain separately testable and can later become background jobs.
                bible = build_story_bible(clean, st.session_state.language)

                progress.progress(24, text="Planning narrative structure...")
                outline = build_outline(bible, st.session_state.language)

                progress.progress(42, text="Writing the first draft...")
                draft = draft_story(
                    bible,
                    outline,
                    st.session_state.language,
                    st.session_state.narrator,
                )

                progress.progress(62, text="Running continuity and quality edit...")
                edited = edit_story(
                    bible,
                    draft,
                    st.session_state.language,
                )

                progress.progress(80, text="Directing illustrated scenes...")
                scenes = plan_scenes(
                    bible,
                    edited["story"],
                    st.session_state.art_style,
                )

                result = {
                    "title": str(bible.get("title", "Untitled Story")).strip()[:120],
                    "description": str(bible.get("logline", "")).strip()[:300],
                    "mood": str(bible.get("tone", "warm")).strip()[:60],
                    "story": str(edited["story"]).strip()[:MAX_STORY_CHARS],
                    "characters": bible.get("characters", []),
                    "story_bible": bible,
                    "outline": outline,
                    "scenes": scenes["scenes"],
                    "editor_notes": edited.get("editor_notes", [])[:8],
                    "quality_score": int(edited.get("quality_score", 80)),
                    "prompt": clean,
                    "language": st.session_state.language,
                    "style": st.session_state.art_style,
                    "narrator": st.session_state.narrator,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "pipeline": [
                        "Brief", "Story Bible", "Outline",
                        "Draft", "Continuity Edit", "Scene Plan"
                    ],
                }

                progress.progress(100, text="Story ready.")
                story_id = save_story(result)

                st.session_state.current_story_id = story_id
                st.session_state.pending_story = st.session_state.stories[story_id]
                st.session_state.selected_scene = 0
                st.session_state.history.extend([
                    {"role": "user", "content": clean},
                    {"role": "assistant", "content": result["story"]},
                ])
                st.session_state.history = st.session_state.history[-MAX_HISTORY:]
                st.session_state.view = "Reader"
                time.sleep(0.15)
                st.rerun()

            except Exception as exc:
                st.error(f"Story creation failed: {safe_error(exc)}")
                st.caption(
                    "If using Groq, verify GROQ_API_KEY in .env and the configured GROQ_MODEL. "
                    "The app also supports an optional local Ollama provider."
                )


# ============================================================
# READER VIEW
# ============================================================

elif st.session_state.view == "Reader":
    active = st.session_state.pending_story

    if not active or not active.get("story"):
        st.info("No story is open. Choose a story from the Library or create a new one.")
        if st.button("Go to Library", type="primary"):
            st.session_state.view = "Library"
            st.rerun()
    else:
        title = active.get("title", "Untitled Story")
        narrator_name = active.get("narrator", st.session_state.narrator)
        narrator = NARRATORS.get(narrator_name, NARRATORS["Story Guide"])

        top1, top2 = st.columns([4, 1])
        with top1:
            st.markdown(f"### {safe_html(title)}")
            st.caption(
                f"{safe_html(active.get('language', 'English'))} · "
                f"{safe_html(active.get('style', 'Illustrated'))} · "
                f"Quality pass: {active.get('quality_score', '—')}/100"
            )
        with top2:
            if st.button("← Library", use_container_width=True):
                st.session_state.view = "Library"
                st.rerun()

        left, right = st.columns([3.2, 1])

        with left:
            st.markdown(
                f"""
                <div class="reader">
                    <div class="reader-title">{safe_html(title)}</div>
                    <div class="reader-copy">{safe_html(active.get("story", ""))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with right:
            st.markdown(
                f"""
                <div class="character">
                    <div class="avatar">{safe_html(narrator["avatar"])}</div>
                    <div class="character-name">{safe_html(narrator_name)}</div>
                    <div class="character-role">AI Story Narrator</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "▶ Tell full story",
                type="primary",
                use_container_width=True,
                key=f"tell_full_{active['id']}",
            ):
                with st.spinner("Preparing narration..."):
                    audio = generate_audio(active["story"], narrator_name)
                if audio:
                    st.audio(audio, format="audio/mp3")
                else:
                    st.error("Narration could not be generated.")

            if st.button(
                "Create / refresh story visuals",
                use_container_width=True,
                key=f"refresh_visuals_{active['id']}",
            ):
                # Cache is deterministic. This action simply moves the user
                # back through the scene cards; failed images can be retried.
                st.rerun()

        st.markdown("---")
        st.markdown("### Characters")

        characters = active.get("characters", [])
        if characters:
            char_cols = st.columns(min(3, len(characters)))
            for idx, character in enumerate(characters):
                with char_cols[idx % len(char_cols)]:
                    st.markdown(
                        f"""
                        <div class="card">
                            <div style="font-weight:800;color:#123f82;">
                                {safe_html(character.get("name", "Character"))}
                            </div>
                            <div class="small-note" style="margin-top:5px;">
                                {safe_html(character.get("description", ""))}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        scenes = active.get("scenes", [])

        if scenes:
            st.markdown("---")
            st.markdown("### Illustrated scenes")

            scene_titles = [
                f"{i + 1}. {scene.get('title', 'Scene')}"
                for i, scene in enumerate(scenes)
            ]

            selected = st.selectbox(
                "Scene",
                list(range(len(scenes))),
                index=min(
                    st.session_state.selected_scene,
                    max(0, len(scenes) - 1),
                ),
                format_func=lambda i: scene_titles[i],
            )
            st.session_state.selected_scene = selected

            scene = scenes[selected]

            st.markdown(
                f"""
                <div class="scene-card">
                    <div class="scene-label">Scene {selected + 1}</div>
                    <h3>{safe_html(scene.get("title", "Scene"))}</h3>
                    <div class="small-note">
                        {safe_html(scene.get("story_excerpt", ""))}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.session_state.generate_images:
                with st.spinner("Preparing illustration..."):
                    image = fetch_image(
                        scene.get("visual_prompt", ""),
                        active.get("style", st.session_state.art_style),
                    )

                if image:
                    st.image(image, use_container_width=True)
                else:
                    st.warning(
                        "The illustration service did not return an image. "
                        "The story itself is still available."
                    )

            s1, s2 = st.columns([1, 1])
            with s1:
                if st.button(
                    "▶ Narrate this scene",
                    use_container_width=True,
                    key=f"scene_audio_{active['id']}_{selected}",
                ):
                    text = scene.get("story_excerpt", "").strip()
                    if not text:
                        text = active["story"]

                    with st.spinner("Preparing scene narration..."):
                        audio = generate_audio(text, narrator_name)

                    if audio:
                        st.audio(audio, format="audio/mp3")
                    else:
                        st.error("Scene narration could not be generated.")

            with s2:
                if st.button(
                    "Next scene →",
                    use_container_width=True,
                    disabled=selected >= len(scenes) - 1,
                    key=f"next_{active['id']}_{selected}",
                ):
                    st.session_state.selected_scene = min(
                        selected + 1,
                        len(scenes) - 1,
                    )
                    st.rerun()

        with st.expander("Story architecture"):
            st.write(
                {
                    "provider": provider_status(),
                    "model": GROQ_MODEL if provider_status() == "Groq" else OLLAMA_MODEL,
                    "pipeline": active.get("pipeline", []),
                    "created_at": active.get("created_at", ""),
                    "editor_notes": active.get("editor_notes", []),
                }
            )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.caption(
    "Story Studio Enterprise · Structured AI generation · "
    "Character-aware scene planning · Cached media · Provider abstraction"
)
