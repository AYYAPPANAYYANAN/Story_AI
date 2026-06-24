# ✨ NEURAL-GRID // Story Engine

![Python](https://img.shields.io/badge/Python-3.9+-00FFCC?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF007F?style=flat-square&logo=streamlit)
![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203.3-orange?style=flat-square)

An ultra-futuristic, interactive HUD-driven narrative orchestration layer. **NEURAL-GRID // Story Engine** generates immersive multi-page text stories, synthetically formats visual scene queues using the Flux architecture, tracks state sequences, and leverages advanced text-to-speech matrixes accompanied by dynamic, mood-reactive backing tracks.

---

WEBPAGE 
"https://storyai-1-v-0-1.streamlit.app/"
## ⚡ Key Features

* **🎭 Dual Narrative Mechanics**:
  * **Main Timeline**: Generates episodic, multi-paragraph stories containing embedded contextual `[SCENE: ...]` image prompts.
  * **Neural Voice Uplink**: Generates tight, emotionally punctuated audio dramatizations accompanied by an automated, mood-reactive background music injector (`suspense`, `action`, `emotional`, `ambient`).
* **👁️ Visual Cortex Integration**: Automated background regex splitting translates text-based `[SCENE]` descriptors into real-time visual transmissions powered by the `flux` engine model via Pollinations AI. Includes sequence paging mechanics (`NEXT SEQUENCE` / `RESTART FEED`).
* **💻 PromptPilot OS (Dynamic UI Override)**: A localized natural language compilation interpreter. Type an intent (e.g., *"Make background white, change language to Tamil"*), and the system dynamically updates UI configurations, text strings, and layout styles on the fly via structured JSON compilation.
* **🎵 Ambient-Audio Layering**: Embedded HTML5/JS audio wrapper hooks directly into the browser to handle variable volume balancing (BGM at 15%, Voice Synth at 100%) and clean audio-fading hooks upon clip finalization.

---

## 🛠️ Architecture Stack

* **Frontend Engine**: Streamlit & Streamlit HTML/JS Components v1
* **Cognitive Processing (LLM)**: `llama-3.3-70b-versatile` via **Groq Cloud API**
* **Aural Matrix (TTS)**: `edge-tts` (Microsoft Edge Advanced Neural TTS Engine)
* **Visual Synthesis**: `flux` model endpoints via Pollinations AI API
* **Styling Hierarchy**: Custom injected CSS override containing scoped `@keyframes` scanners, digital linear terminal styling, custom clip-path geometric boxes, and dual-layered color fonts ('Rajdhani' & 'Share Tech Mono').

---
