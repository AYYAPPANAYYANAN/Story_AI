
"""
Story Studio Enterprise v8
---------------------------
A production-oriented Streamlit storytelling workspace using Groq as the
single AI engine.

Key improvements over v3:
- Groq API key is configured directly in this source file.
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
- No Ollama dependency or local-model server required.
- Deterministic caching for AI text, images and audio.
- Character consistency instructions shared across scenes.
- Scene-level narration instead of one giant opaque audio job.
- Reader progress, scene selection and per-scene narration.
- Safer HTML escaping for generated text.
- No LLM-controlled CSS or Streamlit state.
- Single-provider architecture keeps deployment simple and predictable.

Run:
    pip install -r requirements.txt
    # Paste your Groq key into GROQ_API_KEY below.
    streamlit run story_studio_enterprise_blue_green_v8.py
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
import streamlit as st

try:
    from groq import Groq
except Exception:
    Groq = None


# ============================================================
# PRODUCT CONFIG
# ============================================================

st.set_page_config(
    page_title="Story Studio",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "8.0.0"

# ============================================================
# PUT YOUR GROQ API KEY HERE
# ============================================================
# Example: GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxx"
# Keep this private. Do NOT commit the real key to GitHub or publish it.
GROQ_API_KEY = "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".strip()
GROQ_MODEL = "openai/gpt-oss-20b"

# Temporary Supabase + ElevenLabs configuration requested for this build.
# IMPORTANT: rotate these credentials before publishing or committing this file.
SUPABASE_URL = "https://almmvgiimkftvgdsiiko.supabase.co".rstrip("/")
SUPABASE_KEY = "sb_secret_GVrHEtq81zPn3igjH-Yk_Q_bIF2MV4c".strip()
ELEVENLABS_API_KEY = "sk_ebcaba1e9e4156175eabeb87eafc5276fc546bc999594046".strip()
SUPABASE_TABLE = "stories"

ELEVENLABS_VOICES = {
    "Story Guide": "pNInz6obpgDQGcFmaJgB",
    "Emma": "EXAVITQu4vr4xnSDxMaL",
    "Sofia": "21m00Tcm4TlvDq8ikWAM",
    "Indian English": "AZnzlk1XvdvUeBnXmlld",
}

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

# Load previously persisted stories once per browser session.
if "cloud_loaded" not in st.session_state:
    st.session_state.cloud_loaded = True
    for cloud_story in load_stories_from_supabase():
        if cloud_story.get("id") and cloud_story.get("story"):
            st.session_state.stories[cloud_story["id"]] = cloud_story


# ============================================================
# ENTERPRISE BLUE + GREEN UI / UX
# ============================================================

st.markdown(
    """
<style>
:root {
    --blue-950:#063b73;
    --blue-900:#0756a6;
    --blue-800:#0b6fc5;
    --blue-700:#1683d8;
    --blue-600:#1473d4;
    --blue-500:#2b91e6;
    --green-700:#087443;
    --green-600:#0a8f55;
    --green-500:#18a866;
    --green-100:#dff7ea;
    --green-50:#effcf5;
    --blue-100:#d9ebfb;
    --blue-50:#eef7ff;
    --text:#092f52;
    --muted:#55718a;
    --line:#cfe1ef;
    --page:#f4f9fc;
    --card:#ffffff;
    --success:#087443;
}

.stApp { background:linear-gradient(180deg,#f8fbfd 0%,#f2f8fc 100%); color:var(--text); }
.block-container { max-width:1380px; padding:1.15rem 2rem 4rem; }
h1,h2,h3,h4,h5,h6 { color:var(--text)!important; letter-spacing:-.025em; }
p,label { color:var(--text)!important; }
[data-testid="stHeader"] { background:rgba(255,255,255,.96)!important; }
[data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
[data-testid="stSidebar"] .block-container { padding:1.05rem 1rem 2rem; }

/* Brand */
.ss-brand { display:flex; align-items:center; gap:11px; padding:4px 3px 18px; }
.ss-logo { width:40px;height:40px; display:grid;place-items:center; border-radius:12px; background:linear-gradient(135deg,var(--blue-600),var(--green-600)); color:#fff; font-weight:900; box-shadow:0 8px 20px rgba(20,115,212,.18); }
.ss-brand-name { color:var(--blue-950); font-weight:900; font-size:1.05rem; }
.ss-brand-sub { color:var(--green-700); font-size:.67rem; font-weight:800; letter-spacing:.07em; margin-top:2px; }
.nav-label { color:var(--blue-800); font-size:.67rem; font-weight:850; text-transform:uppercase; letter-spacing:.1em; margin:15px 0 7px; }
.sidebar-card { border:1px solid var(--line); border-radius:14px; padding:13px; background:#fff; box-shadow:0 5px 18px rgba(9,47,82,.035); }
.status-line { display:flex; align-items:center; gap:7px; color:var(--green-700); font-size:.78rem; font-weight:800; }
.status-dot { width:8px;height:8px;border-radius:50%;background:var(--green-600); box-shadow:0 0 0 4px var(--green-100); }

/* Application header */
.appbar { height:58px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); margin-bottom:25px; }
.appbar-title { color:var(--blue-950); font-size:.96rem; font-weight:850; }
.appbar-meta { color:var(--green-700); font-size:.75rem; font-weight:750; }

/* Hero */
.hero { position:relative; overflow:hidden; background:linear-gradient(135deg,#fff 0%,#eef7ff 66%,#effcf5 100%); border:1px solid var(--line); border-radius:24px; padding:40px; margin-bottom:20px; box-shadow:0 16px 45px rgba(9,47,82,.07); }
.hero:after { content:""; position:absolute; right:-80px; top:-90px; width:260px;height:260px;border-radius:50%; border:35px solid rgba(10,143,85,.08); }
.eyebrow { display:inline-block; padding:6px 10px; border-radius:999px; background:var(--green-50); border:1px solid #bfead2; color:var(--green-700); font-size:.72rem; font-weight:850; letter-spacing:.04em; }
.hero-title { font-size:2.75rem; line-height:1.04; font-weight:900; letter-spacing:-.055em; color:var(--blue-950); margin-top:14px; max-width:800px; }
.hero-copy { max-width:760px; color:var(--muted); line-height:1.68; font-size:1rem; margin-top:13px; }
.pills { display:flex; gap:8px; flex-wrap:wrap; margin-top:20px; }
.pill { padding:6px 10px; border:1px solid var(--line); background:#fff; border-radius:999px; color:var(--blue-800); font-size:.73rem; font-weight:700; }

/* Enterprise cards */
.card,.story-tile,.reader,.character,.metric,.pipeline,.scene-card { background:#fff; border:1px solid var(--line); border-radius:16px; box-shadow:0 7px 25px rgba(9,47,82,.045); }
.card { padding:20px; }
.story-tile { padding:19px; min-height:168px; transition:.18s ease; }
.story-tile:hover { transform:translateY(-2px); border-color:#a9cfe9; box-shadow:0 12px 30px rgba(9,47,82,.08); }
.reader { padding:34px; }
.character { padding:20px; text-align:center; }
.metric { padding:15px; min-height:92px; }
.pipeline { padding:15px; }
.story-icon { width:43px;height:43px;display:grid;place-items:center;border-radius:12px;background:linear-gradient(135deg,var(--blue-50),var(--green-50));margin-bottom:12px; }
.story-title { font-weight:850; color:var(--blue-950); }
.story-description { color:var(--muted); font-size:.82rem; line-height:1.52; margin-top:5px; }
.reader-title { font-size:2.05rem; font-weight:900; color:var(--blue-950); }
.reader-copy { margin-top:18px; color:#234760; line-height:1.98; font-size:1.04rem; white-space:pre-line; }
.avatar { width:80px;height:80px;display:grid;place-items:center;margin:0 auto 12px;border-radius:50%;background:linear-gradient(135deg,var(--blue-50),var(--green-50));border:1px solid var(--line);font-size:36px; }
.character-name { font-weight:850; color:var(--blue-950); }
.character-role { color:var(--muted); font-size:.8rem; margin-top:4px; }
.metric-number { font-size:1.38rem; font-weight:900; color:var(--blue-950); }
.metric-label { color:var(--muted); font-size:.73rem; }
.metric-accent { color:var(--green-700)!important; }
.scene-label { color:var(--green-700); font-weight:850; font-size:.77rem; text-transform:uppercase; letter-spacing:.06em; }
.scene-card { padding:19px; margin-bottom:14px; }
.pipeline-step { display:flex; align-items:center; gap:10px; color:#42647c; font-size:.82rem; }
.pipeline-dot { width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:var(--blue-50);color:var(--blue-700);border:1px solid var(--blue-100);font-weight:850; }

/* Controls */
.stButton > button, .stFormSubmitButton > button { min-height:43px; border-radius:10px!important; font-weight:800!important; border:1px solid var(--line)!important; transition:.16s ease!important; }
.stButton > button:hover, .stFormSubmitButton > button:hover { border-color:var(--green-500)!important; color:var(--green-700)!important; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:linear-gradient(135deg,var(--blue-600),var(--green-600))!important; color:#fff!important; border:0!important; box-shadow:0 8px 20px rgba(20,115,212,.18)!important; }
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover { color:#fff!important; filter:brightness(1.03); }
div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div, div[data-baseweb="select"] > div { background:#fff!important; border-color:var(--line)!important; border-radius:10px!important; }
div[data-baseweb="input"]:focus-within > div, div[data-baseweb="textarea"]:focus-within > div { border-color:var(--blue-500)!important; box-shadow:0 0 0 2px var(--blue-100)!important; }
.stProgress > div > div > div > div { background:linear-gradient(90deg,var(--blue-600),var(--green-600))!important; }
[data-testid="stMetricValue"] { color:var(--blue-950)!important; }
[data-testid="stMetricLabel"] { color:var(--muted)!important; }
hr { border-color:var(--line); }
a { color:var(--blue-800); }
a:hover { color:var(--green-700); }
audio { width:100%; }
.small-note { color:var(--muted); font-size:.78rem; }
.status-ok { color:var(--green-700); font-weight:800; }
.status-warn { color:#9a6700; font-weight:800; }

/* Responsive */
@media (max-width:900px){
  .block-container{padding:1rem 1rem 3rem;}
  .hero{padding:27px 22px;border-radius:18px;}
  .hero-title{font-size:2.15rem;}
  .reader{padding:23px;}
}
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
    for secret in (GROQ_API_KEY, SUPABASE_KEY, ELEVENLABS_API_KEY):
        if secret and len(secret) > 8:
            text = text.replace(secret, "[REDACTED]")
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
    """Return the configured AI engine used by this product."""
    if GROQ_API_KEY and Groq is not None:
        return "Groq"
    return "Not configured"


def supabase_headers() -> Dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def save_story_to_supabase(record: Dict[str, Any]) -> bool:
    """Best-effort cloud persistence. UI generation never fails if the DB is unavailable."""
    if not supabase_enabled():
        return False
    try:
        payload = {
            "id": record.get("id"),
            "title": record.get("title", "Untitled Story"),
            "description": record.get("description", ""),
            "prompt": record.get("prompt", ""),
            "story": record.get("story", ""),
            "language": record.get("language", "English"),
            "style": record.get("style", "Illustrated"),
            "narrator": record.get("narrator", "Story Guide"),
            "quality_score": int(record.get("quality_score", 80) or 80),
            "mood": record.get("mood", "warm"),
            "characters": record.get("characters", []),
            "story_bible": record.get("story_bible", {}),
            "outline": record.get("outline", {}),
            "scenes": record.get("scenes", []),
            "editor_notes": record.get("editor_notes", []),
            "pipeline": record.get("pipeline", []),
            "created_at": record.get("created_at"),
        }
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
            headers=supabase_headers(),
            json=payload,
            timeout=12,
        )
        if r.status_code in (200, 201, 204):
            return True
        # Retry as an update when the deterministic ID already exists.
        if r.status_code in (409, 400):
            r2 = requests.patch(
                f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?id=eq.{urllib.parse.quote(str(record.get('id')))}",
                headers=supabase_headers(),
                json=payload,
                timeout=12,
            )
            return r2.status_code in (200, 204)
    except requests.RequestException:
        pass
    return False


def load_stories_from_supabase() -> List[Dict[str, Any]]:
    if not supabase_enabled():
        return []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=*&order=created_at.desc",
            headers=supabase_headers(),
            timeout=12,
        )
        if r.ok and isinstance(r.json(), list):
            return r.json()
    except (requests.RequestException, ValueError):
        pass
    return []


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


def llm_json(
    *,
    system: str,
    user: str,
    schema_name: str,
    schema: Dict[str, Any],
    temperature: float = 0.35,
    max_tokens: int = 5000,
) -> Dict[str, Any]:
    """Call Groq only, with structured-output compatibility fallback."""
    if not GROQ_API_KEY or GROQ_API_KEY == "PASTE_YOUR_GROQ_API_KEY_HERE":
        raise RuntimeError(
            "Groq API key is not configured. Open this Python file and paste "
            "your key into GROQ_API_KEY near the top of the file."
        )
    if Groq is None:
        raise RuntimeError(
            "The Groq Python package is missing. Run: pip install groq"
        )

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
        try:
            return call_groq_json_fallback(
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as fallback_error:
            raise RuntimeError(
                f"Groq generation failed. Primary error: {safe_error(first_error)} | "
                f"JSON fallback: {safe_error(fallback_error)}"
            ) from fallback_error


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

    cache_key = stable_hash(clean, language, narrator, art_style, GROQ_MODEL)

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

def generate_audio(text: str, narrator: str) -> Optional[bytes]:
    """Generate narration through ElevenLabs with session caching."""
    voice_id = ELEVENLABS_VOICES.get(narrator, ELEVENLABS_VOICES["Story Guide"])
    key = stable_hash(text, voice_id, "elevenlabs")

    if key in st.session_state.audio_cache:
        return st.session_state.audio_cache[key]

    if not ELEVENLABS_API_KEY:
        st.session_state.last_error = "ElevenLabs API key is not configured."
        return None

    try:
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={
                "text": text[:9000],
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.48,
                    "similarity_boost": 0.78,
                    "style": 0.18,
                    "use_speaker_boost": True,
                },
            },
            timeout=90,
        )
        if not response.ok or not response.content:
            detail = response.text[:300] if response.text else "Unknown ElevenLabs error."
            raise RuntimeError(f"ElevenLabs narration failed ({response.status_code}): {detail}")

        data = response.content
        st.session_state.audio_cache[key] = data
        return data
    except Exception as exc:
        st.session_state.last_error = safe_error(exc)
        return None


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
    record["cloud_saved"] = save_story_to_supabase(record)
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
# ============================================================
# ENTERPRISE BLUE + GREEN UI / UX v7
# ============================================================

st.markdown("""
<style>
:root{
 --navy:#063b33;--blue:#1464d2;--blue-2:#2f7de1;--blue-50:#eef6ff;--blue-100:#d9eaff;--blue-200:#b9d7fb;
 --green:#16a36a;--green-50:#edfbf4;--green-100:#d4f5e5;--border:#d7e6f4;--text:#12324a;--muted:#557086;
}
.stApp{background:linear-gradient(180deg,#f7fbff 0%,#fff 42%,#f5fbf8 100%);color:var(--text)}
.block-container{max-width:1440px;padding:1rem 2rem 4rem}
[data-testid="stHeader"]{background:rgba(255,255,255,.94)!important}
[data-testid="stSidebar"]{background:#fff!important;border-right:1px solid var(--border)}
[data-testid="stSidebar"] .block-container{padding:1rem .95rem 2rem}
h1,h2,h3,h4,h5,h6,p,label{color:var(--text)!important}
.ss-brand{display:flex;align-items:center;gap:11px;padding:5px 4px 20px}
.ss-logo{width:40px;height:40px;border-radius:12px;background:linear-gradient(145deg,var(--blue),var(--green));color:#fff;display:grid;place-items:center;font-weight:900;font-size:18px;box-shadow:0 7px 18px rgba(20,100,210,.18)}
.ss-brand-name{font-weight:900;font-size:1.05rem;color:var(--navy)!important;letter-spacing:-.02em}
.ss-brand-sub{color:var(--green)!important;font-size:.67rem;font-weight:800;letter-spacing:.08em;margin-top:1px}
.nav-label{color:var(--muted)!important;font-size:.67rem;font-weight:900;text-transform:uppercase;letter-spacing:.1em;margin:14px 0 7px}
.sidebar-card{border:1px solid var(--border);border-radius:14px;padding:13px;background:linear-gradient(145deg,#fff,#f8fcff);box-shadow:0 4px 16px rgba(18,50,74,.04)}
.status-line{display:flex;align-items:center;gap:7px;color:var(--navy)!important;font-size:.78rem;font-weight:800}
.status-dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 0 4px var(--green-100)}
div[data-testid="stSidebar"] div[role="radiogroup"]{gap:5px!important}
div[data-testid="stSidebar"] div[role="radiogroup"] label{border:1px solid transparent!important;border-radius:10px!important;padding:8px 10px!important;background:#fff!important;color:var(--muted)!important}
div[data-testid="stSidebar"] div[role="radiogroup"] label:hover{background:var(--blue-50)!important;border-color:var(--blue-100)!important;color:var(--blue)!important}
div[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"]{background:linear-gradient(90deg,var(--blue-50),var(--green-50))!important;border-color:var(--blue-200)!important;color:var(--navy)!important;font-weight:900!important}
.appbar{height:58px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);margin-bottom:22px;background:rgba(255,255,255,.55)}
.appbar-title{font-size:.96rem;font-weight:900;color:var(--navy)!important}.appbar-meta{color:var(--muted)!important;font-size:.73rem;font-weight:700}.appbar-meta span{color:var(--green)!important}
.hero{position:relative;overflow:hidden;border:1px solid var(--blue-200);border-radius:24px;padding:40px 44px;background:linear-gradient(115deg,#fff 0%,var(--blue-50) 62%,var(--green-50) 100%);box-shadow:0 10px 30px rgba(18,50,74,.07);margin-bottom:18px}
.hero:before{content:"";position:absolute;right:-85px;top:-105px;width:290px;height:290px;border-radius:50%;background:linear-gradient(135deg,rgba(20,100,210,.12),rgba(22,163,106,.15))}.hero:after{content:"";position:absolute;right:55px;bottom:-95px;width:180px;height:180px;border-radius:50%;border:22px solid rgba(22,163,106,.12)}
.hero-eyebrow{color:var(--green)!important;font-size:.68rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase;position:relative;z-index:1}.hero-title{color:var(--navy)!important;font-size:2.85rem;line-height:1.04;font-weight:950;letter-spacing:-.06em;max-width:800px;margin-top:10px;position:relative;z-index:1}.hero-copy{color:var(--muted)!important;max-width:740px;line-height:1.65;font-size:.96rem;margin-top:13px;position:relative;z-index:1}
.kpi{border:1px solid var(--border);border-radius:15px;background:#fff;padding:17px;min-height:94px;box-shadow:0 5px 18px rgba(18,50,74,.04)}.kpi-value{color:var(--navy)!important;font-size:1.4rem;font-weight:950}.kpi-label{color:var(--muted)!important;font-size:.71rem;margin-top:3px;font-weight:700}.kpi-green{border-top:3px solid var(--green)}.kpi-blue{border-top:3px solid var(--blue)}
.section{margin-top:30px;margin-bottom:13px}.section-title{color:var(--navy)!important;font-size:1.23rem;font-weight:900;letter-spacing:-.025em}.section-subtitle{color:var(--muted)!important;font-size:.78rem;margin-top:3px}
.card,.story-card,.create-shell,.reader-panel,.scene-selector,.character-card{border:1px solid var(--border);border-radius:18px;background:rgba(255,255,255,.96);box-shadow:0 7px 24px rgba(18,50,74,.045)}
.story-card{padding:20px;min-height:180px;transition:.16s ease}.story-card:hover{transform:translateY(-2px);border-color:var(--blue-2);box-shadow:0 12px 32px rgba(20,100,210,.10)}
.story-badge{display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:11px;background:linear-gradient(145deg,var(--blue),var(--green));color:#fff;font-size:.8rem;font-weight:950;margin-bottom:14px}.story-title{color:var(--navy)!important;font-size:1rem;font-weight:900}.story-description{color:var(--muted)!important;font-size:.77rem;line-height:1.55;margin-top:6px;min-height:50px}.create-shell{padding:28px;background:linear-gradient(180deg,#fff,#fbfdff)}.create-label{color:var(--navy)!important;font-size:1rem;font-weight:900;margin-bottom:6px}.create-help{color:var(--muted)!important;font-size:.78rem;line-height:1.5;margin-bottom:16px}
.pipeline{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:0 0 22px}.pipeline-item{border:1px solid var(--border);border-radius:11px;padding:11px;background:linear-gradient(145deg,var(--blue-50),var(--green-50));text-align:center}.pipeline-num{color:var(--blue)!important;font-size:.67rem;font-weight:950}.pipeline-name{color:var(--navy)!important;font-size:.69rem;font-weight:800;margin-top:3px}
.reader-grid{display:grid;grid-template-columns:minmax(0,1fr) 285px;gap:20px}.reader-panel{padding:32px}.reader-title{color:var(--navy)!important;font-size:2rem;font-weight:950;line-height:1.1}.reader-meta{color:var(--muted)!important;font-size:.75rem;margin-top:7px}.reader-story{color:var(--text)!important;font-size:1rem;line-height:1.95;margin-top:23px;white-space:pre-line}.narrator-panel{border:1px solid var(--green-100);border-radius:20px;background:linear-gradient(145deg,var(--green-50),var(--blue-50));padding:20px;text-align:center}.narrator-avatar{width:72px;height:72px;margin:0 auto 12px;border-radius:50%;background:linear-gradient(145deg,var(--blue),var(--green));color:#fff;display:grid;place-items:center;font-size:27px;font-weight:900;box-shadow:0 8px 22px rgba(22,163,106,.18)}.narrator-name{color:var(--navy)!important;font-weight:900}.narrator-role{color:var(--muted)!important;font-size:.73rem;margin-top:3px}.scene-selector{padding:18px}.scene-label{color:var(--green)!important;font-size:.68rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.scene-title{color:var(--navy)!important;font-size:1.18rem;font-weight:900;margin-top:4px}.scene-copy{color:var(--muted)!important;font-size:.78rem;line-height:1.55;margin-top:7px}.character-card{padding:17px}.character-name{color:var(--navy)!important;font-weight:900}.character-description{color:var(--muted)!important;font-size:.76rem;line-height:1.5;margin-top:5px}
/* Dropdowns: target both the control and the opened menu so no black BaseWeb surface leaks through. */
div[data-baseweb="select"] > div,div[data-baseweb="input"] > div,div[data-baseweb="textarea"] > div,div[data-baseweb="slider"] > div,div[data-baseweb="popover"] > div{background:#fff!important;color:var(--text)!important;border-color:var(--border)!important}div[data-baseweb="select"] > div{min-height:42px;border-radius:11px!important;box-shadow:none!important}div[data-baseweb="select"] span,div[data-baseweb="select"] input,div[data-baseweb="input"] input,textarea{color:var(--text)!important;-webkit-text-fill-color:var(--text)!important}div[data-baseweb="select"] svg{fill:var(--blue)!important}div[data-baseweb="select"]:focus-within > div,div[data-baseweb="input"]:focus-within > div,div[data-baseweb="textarea"]:focus-within > div{border-color:var(--blue-2)!important;box-shadow:0 0 0 3px rgba(20,100,210,.10)!important}
div[data-baseweb="popover"]{background:#fff!important}div[data-baseweb="menu"]{background:#fff!important;border:1px solid var(--blue-100)!important;border-radius:12px!important;box-shadow:0 14px 35px rgba(18,50,74,.13)!important;overflow:hidden!important}ul[role="listbox"]{background:#fff!important;padding:5px!important}li[role="option"]{background:#fff!important;color:var(--text)!important;border-radius:8px!important;margin:2px 0!important}li[role="option"]:hover{background:var(--blue-50)!important;color:var(--blue)!important}li[role="option"][aria-selected="true"]{background:linear-gradient(90deg,var(--blue-50),var(--green-50))!important;color:var(--navy)!important;font-weight:850!important}
div[data-testid="stToggle"] label{color:var(--text)!important}div[data-testid="stToggle"] div[role="switch"]{background:#b9c9d5!important}div[data-testid="stToggle"] div[role="switch"][aria-checked="true"]{background:var(--green)!important}
.stButton > button,.stFormSubmitButton > button{border-radius:10px!important;min-height:42px;border:1px solid var(--blue-200)!important;background:#fff!important;color:var(--blue)!important;font-weight:800!important;box-shadow:none!important;transition:.15s ease}.stButton > button:hover,.stFormSubmitButton > button:hover{border-color:var(--green)!important;background:var(--green-50)!important;color:var(--navy)!important;transform:translateY(-1px)}.stButton > button[kind="primary"],.stFormSubmitButton > button[kind="primary"]{background:linear-gradient(135deg,var(--blue),var(--green))!important;border-color:transparent!important;color:#fff!important;box-shadow:0 8px 18px rgba(20,100,210,.16)!important}.stButton > button[kind="primary"]:hover,.stFormSubmitButton > button[kind="primary"]:hover{filter:brightness(.97);color:#fff!important}hr{border-color:var(--border)}a{color:var(--blue)!important}
.library-toolbar{padding:14px 16px;border:1px solid var(--border);border-radius:15px;background:#fff;margin-bottom:15px}.filter-chip{display:inline-block;padding:5px 9px;border-radius:999px;background:var(--green-50);border:1px solid var(--green-100);color:var(--green)!important;font-size:.67rem;font-weight:850;margin-right:5px}.empty-state{padding:42px;text-align:center;border:1px dashed var(--blue-200);border-radius:18px;background:linear-gradient(145deg,var(--blue-50),var(--green-50))}
@media (max-width:900px){.block-container{padding:1rem 1rem 3rem}.hero{padding:28px 24px}.hero-title{font-size:2rem}.pipeline{grid-template-columns:repeat(3,1fr)}.reader-grid{display:block}.reader-panel{margin-bottom:16px}}
</style>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================
# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        """
        <div class="ss-brand">
            <div class="ss-logo">S</div>
            <div>
                <div class="ss-brand-name">Story Studio</div>
                <div class="ss-brand-sub">AI CREATIVE WORKSPACE</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="nav-label">Workspace</div>', unsafe_allow_html=True)

    nav_options = ["Library", "Create", "Reader"]
    nav = st.radio(
        "Workspace navigation",
        nav_options,
        index=nav_options.index(st.session_state.view),
        label_visibility="collapsed",
    )

    if nav != st.session_state.view:
        st.session_state.view = nav

    st.markdown('<div class="nav-label">Story settings</div>', unsafe_allow_html=True)

    st.session_state.language = st.selectbox(
        "Language",
        LANGUAGES,
        index=LANGUAGES.index(st.session_state.language),
    )

    st.session_state.art_style = st.selectbox(
        "Visual style",
        list(ART_STYLES.keys()),
        index=list(ART_STYLES.keys()).index(st.session_state.art_style),
    )

    st.session_state.narrator = st.selectbox(
        "Narrator",
        list(NARRATORS.keys()),
        index=list(NARRATORS.keys()).index(st.session_state.narrator),
    )

    st.session_state.generate_images = st.toggle(
        "Generate illustrations",
        value=st.session_state.generate_images,
    )

    narrator = NARRATORS[st.session_state.narrator]

    st.markdown(
        f"""
        <div class="sidebar-card">
            <div class="status-line">
                <span class="status-dot"></span>
                Narrator ready
            </div>
            <div style="margin-top:10px;font-weight:850;color:#082f63;">
                {safe_html(st.session_state.narrator)}
            </div>
            <div style="margin-top:3px;color:#155fc2;font-size:.72rem;">
                {safe_html(narrator["description"])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="nav-label">System</div>', unsafe_allow_html=True)

    status = provider_status()

    st.markdown(
        f"""
        <div class="sidebar-card">
            <div class="status-line">
                <span class="status-dot"></span>
                AI engine: {safe_html(status)}
            </div>
            <div style="margin-top:7px;color:#155fc2;font-size:.70rem;">
                API credentials are loaded from .env.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Clear workspace", use_container_width=True):
        clear_workspace()
        st.rerun()


# ============================================================
# APPLICATION HEADER
# ============================================================

st.markdown(
    """
    <div class="appbar">
        <div class="appbar-title">Story Studio</div>
        <div class="appbar-meta"><span>●</span> Create · Illustrate · Narrate · Enterprise workflow</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">
        <div class="hero-eyebrow">AI STORYTELLING PLATFORM</div>
        <div class="hero-title">Create stories people want to keep.</div>
        <div class="hero-copy">
            Build a complete story from one idea. Story Studio develops the
            narrative, characters, scenes and narration through a structured
            AI workflow.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Primary action row
a1, a2, a3 = st.columns([1.2, 1, 1])
with a1:
    if st.button("Create a new story", type="primary", use_container_width=True):
        st.session_state.view = "Create"
        st.rerun()
with a2:
    if st.button("Browse story library", use_container_width=True):
        st.session_state.view = "Library"
        st.rerun()
with a3:
    if st.button("Open current story", use_container_width=True):
        if st.session_state.pending_story:
            st.session_state.view = "Reader"
        else:
            st.session_state.view = "Library"
        st.rerun()


# ============================================================
# KPI BAR
# ============================================================

k1, k2, k3, k4 = st.columns(4)
for col, (value, label) in zip(
    (k1, k2, k3, k4),
    [
        (len(st.session_state.stories), "Stories"),
        (len(st.session_state.image_cache), "Illustrations"),
        (len(st.session_state.audio_cache), "Narrations"),
        (provider_status(), "AI engine"),
    ],
):
    with col:
        st.markdown(
            f"""
            <div class="kpi">
                <div class="kpi-value">{safe_html(value)}</div>
                <div class="kpi-label">{safe_html(label)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# LIBRARY VIEW
# ============================================================

if st.session_state.view == "Library":
    st.markdown("""
    <div class="section">
      <div class="section-title">Story workspace</div>
      <div class="section-subtitle">Find, resume and manage every story created in this session.</div>
    </div>
    """, unsafe_allow_html=True)

    stories = list(st.session_state.stories.values())
    tb1, tb2, tb3 = st.columns([2.2, 1, 1])
    with tb1:
        library_query = st.text_input("Search stories", key="library_query", placeholder="Search by title, description or idea…", label_visibility="collapsed").strip().lower()
    with tb2:
        library_filter = st.selectbox("Filter", ["All stories", "Illustrated", "Narrated"], key="library_filter", label_visibility="collapsed")
    with tb3:
        library_sort = st.selectbox("Sort", ["Newest", "Title A–Z", "Quality"], key="library_sort", label_visibility="collapsed")

    filtered=[]
    for item in stories:
        haystack=" ".join([str(item.get("title","")),str(item.get("description","")),str(item.get("prompt",""))]).lower()
        if library_query and library_query not in haystack: continue
        if library_filter == "Illustrated" and not item.get("scenes"): continue
        if library_filter == "Narrated" and not item.get("narrator"): continue
        filtered.append(item)
    if library_sort == "Title A–Z": filtered.sort(key=lambda x:str(x.get("title","" )).lower())
    elif library_sort == "Quality": filtered.sort(key=lambda x:int(x.get("quality_score",0) or 0), reverse=True)
    else: filtered.sort(key=lambda x:str(x.get("created_at","")), reverse=True)

    st.markdown(f'<div class="library-toolbar"><span class="filter-chip">{len(filtered)} stories</span><span class="filter-chip">{safe_html(library_filter)}</span><span class="filter-chip">Enterprise library</span></div>', unsafe_allow_html=True)
    if not filtered:
        st.markdown('<div class="empty-state"><div style="font-size:1.1rem;font-weight:900;color:#063b33;">No matching stories</div><div style="margin-top:7px;color:#557086;font-size:.8rem;">Try another search or create a new story.</div></div>', unsafe_allow_html=True)
    else:
        cols=st.columns(3)
        for idx,item in enumerate(filtered):
            with cols[idx%3]:
                quality=int(item.get("quality_score",0) or 0)
                st.markdown(f'''<div class="story-card"><div class="story-badge">S</div><div class="story-title">{safe_html(item.get("title","Untitled"))}</div><div class="story-description">{safe_html(item.get("description",""))}</div><div style="margin-top:12px;font-size:.68rem;color:#557086;font-weight:750;">{safe_html(item.get("language","English"))} · {safe_html(item.get("style","Illustrated"))} · Quality {quality}%</div></div>''', unsafe_allow_html=True)
                if st.button("Open story",key=f"library_open_{item['id']}",use_container_width=True):
                    if open_story(item["id"]): st.rerun()

    st.markdown('<div class="section"><div class="section-title">Production workflow</div><div class="section-subtitle">A controlled pipeline from idea to reader-ready experience.</div></div>', unsafe_allow_html=True)
    h1,h2,h3=st.columns(3)
    for col,title,body in [(h1,"01 · Understand","Normalize the idea into a story brief, characters, setting and emotional direction."),(h2,"02 · Produce","Generate, edit and validate the narrative before creating visual scene plans."),(h3,"03 · Deliver","Read, illustrate and narrate scene-by-scene with consistent character direction.")]:
        with col:
            st.markdown(f'<div class="card" style="padding:18px;"><div style="font-weight:900;color:#063b33;">{safe_html(title)}</div><div style="margin-top:6px;color:#557086;font-size:.76rem;line-height:1.55;">{safe_html(body)}</div></div>', unsafe_allow_html=True)


# ============================================================

# CREATE VIEW
# ============================================================

elif st.session_state.view == "Create":

    st.markdown(
        """
        <div class="section">
            <div class="section-title">Create a new story</div>
            <div class="section-subtitle">
                Describe the idea. The studio handles the narrative architecture.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="create-shell">', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="create-label">Your story idea</div>
        <div class="create-help">
            Include a character, situation, lesson, genre or emotion.
            You do not need to write the full story.
        </div>
        """,
        unsafe_allow_html=True,
    )

    prompt = st.text_area(
        "Story idea",
        height=175,
        placeholder=(
            "Example: A small robot gets lost in a city during a power outage "
            "and discovers that helping people is more important than completing "
            "its original mission."
        ),
        label_visibility="collapsed",
    )

    st.markdown(
        """
        <div class="pipeline">
            <div class="pipeline-item"><div class="pipeline-num">01</div><div class="pipeline-name">Brief</div></div>
            <div class="pipeline-item"><div class="pipeline-num">02</div><div class="pipeline-name">Characters</div></div>
            <div class="pipeline-item"><div class="pipeline-num">03</div><div class="pipeline-name">Outline</div></div>
            <div class="pipeline-item"><div class="pipeline-num">04</div><div class="pipeline-name">Draft</div></div>
            <div class="pipeline-item"><div class="pipeline-num">05</div><div class="pipeline-name">Edit</div></div>
            <div class="pipeline-item"><div class="pipeline-num">06</div><div class="pipeline-name">Scenes</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    s1, s2, s3 = st.columns(3)
    with s1:
        st.caption(f"Language · {st.session_state.language}")
    with s2:
        st.caption(f"Visuals · {st.session_state.art_style}")
    with s3:
        st.caption(f"Narrator · {st.session_state.narrator}")

    generate_clicked = st.button(
        "Generate story",
        type="primary",
        use_container_width=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if generate_clicked:
        clean = clean_prompt(prompt)

        if not clean:
            st.warning("Describe the story you want to create.")
        else:
            progress = st.progress(0, text="Starting story studio...")
            try:
                progress.progress(8, text="Building story bible...")
                bible = build_story_bible(clean, st.session_state.language)

                progress.progress(25, text="Planning narrative...")
                outline = build_outline(bible, st.session_state.language)

                progress.progress(43, text="Writing story...")
                draft = draft_story(
                    bible,
                    outline,
                    st.session_state.language,
                    st.session_state.narrator,
                )

                progress.progress(62, text="Running editorial quality pass...")
                edited = edit_story(
                    bible,
                    draft,
                    st.session_state.language,
                )

                progress.progress(82, text="Designing illustrated scenes...")
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


# ============================================================
# READER VIEW
# ============================================================

elif st.session_state.view == "Reader":

    active = st.session_state.pending_story

    if not active or not active.get("story"):
        st.markdown(
            """
            <div class="card">
                <div style="font-size:1.1rem;font-weight:850;color:#082f63;">
                    No story is open
                </div>
                <div style="margin-top:5px;color:#155fc2;font-size:.78rem;">
                    Choose a story from the library or create a new one.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Go to story library", type="primary"):
            st.session_state.view = "Library"
            st.rerun()

    else:
        title = active.get("title", "Untitled Story")
        narrator_name = active.get("narrator", st.session_state.narrator)
        narrator = NARRATORS.get(narrator_name, NARRATORS["Story Guide"])

        rtop1, rtop2 = st.columns([4,1])
        with rtop1:
            st.markdown(
                f"""
                <div class="section" style="margin-top:0;">
                    <div class="section-title">{safe_html(title)}</div>
                    <div class="section-subtitle">
                        {safe_html(active.get("language","English"))}
                        · {safe_html(active.get("style","Illustrated"))}
                        · Quality {active.get("quality_score","—")}/100
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with rtop2:
            if st.button("← Library", use_container_width=True):
                st.session_state.view = "Library"
                st.rerun()

        st.markdown('<div class="reader-grid">', unsafe_allow_html=True)

        left, right = st.columns([3.2, 1])

        with left:
            st.markdown(
                f"""
                <div class="reader-panel">
                    <div class="reader-title">{safe_html(title)}</div>
                    <div class="reader-meta">
                        {safe_html(active.get("description",""))}
                    </div>
                    <div class="reader-story">{safe_html(active.get("story",""))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with right:
            st.markdown(
                f"""
                <div class="narrator-panel">
                    <div class="narrator-avatar">{safe_html(narrator["avatar"])}</div>
                    <div class="narrator-name">{safe_html(narrator_name)}</div>
                    <div class="narrator-role">AI Story Narrator</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("")

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

        st.markdown("</div>", unsafe_allow_html=True)

        # Characters
        characters = active.get("characters", [])
        if characters:
            st.markdown(
                """
                <div class="section">
                    <div class="section-title">Characters</div>
                    <div class="section-subtitle">Visual identities used across the story.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            cc = st.columns(min(3, len(characters)))
            for idx, character in enumerate(characters):
                with cc[idx % len(cc)]:
                    st.markdown(
                        f"""
                        <div class="character-card">
                            <div class="character-name">
                                {safe_html(character.get("name","Character"))}
                            </div>
                            <div class="character-description">
                                {safe_html(character.get("description",""))}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # Scenes
        scenes = active.get("scenes", [])
        if scenes:
            st.markdown(
                """
                <div class="section">
                    <div class="section-title">Scenes</div>
                    <div class="section-subtitle">
                        Explore the story visually one scene at a time.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            scene_titles = [
                f"{i + 1}. {scene.get('title','Scene')}"
                for i, scene in enumerate(scenes)
            ]

            selected = st.selectbox(
                "Choose a scene",
                list(range(len(scenes))),
                index=min(
                    st.session_state.selected_scene,
                    max(0, len(scenes)-1),
                ),
                format_func=lambda i: scene_titles[i],
            )
            st.session_state.selected_scene = selected

            scene = scenes[selected]

            st.markdown(
                f"""
                <div class="scene-selector">
                    <div class="scene-label">Scene {selected + 1}</div>
                    <div class="scene-title">{safe_html(scene.get("title","Scene"))}</div>
                    <div class="scene-copy">{safe_html(scene.get("story_excerpt",""))}</div>
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
                        "The story remains available."
                    )

            b1, b2 = st.columns(2)

            with b1:
                if st.button(
                    "▶ Narrate scene",
                    use_container_width=True,
                    key=f"scene_audio_{active['id']}_{selected}",
                ):
                    text = scene.get("story_excerpt", "").strip() or active["story"]

                    with st.spinner("Preparing scene narration..."):
                        audio = generate_audio(text, narrator_name)

                    if audio:
                        st.audio(audio, format="audio/mp3")
                    else:
                        st.error("Scene narration could not be generated.")

            with b2:
                if st.button(
                    "Next scene →",
                    use_container_width=True,
                    disabled=selected >= len(scenes)-1,
                    key=f"next_{active['id']}_{selected}",
                ):
                    st.session_state.selected_scene = min(
                        selected + 1,
                        len(scenes)-1,
                    )
                    st.rerun()

        with st.expander("Story architecture"):
            st.write({
                "provider": provider_status(),
                "model": GROQ_MODEL,
                "pipeline": active.get("pipeline", []),
                "created_at": active.get("created_at", ""),
                "editor_notes": active.get("editor_notes", []),
            })


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.markdown(
    """
    <div style="text-align:center;color:#155fc2;font-size:.70rem;">
        STORY STUDIO · AI STORYTELLING WORKSPACE
    </div>
    """,
    unsafe_allow_html=True,
)
