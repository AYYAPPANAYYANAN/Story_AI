import os
import re
import json
import time
import urllib.parse
import requests  
import random
import asyncio
import edge_tts
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(page_title="Story Engine", page_icon="✨", layout="centered")
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "gsk_placeholder_key"))

# --- 2. STATE MANAGEMENT (HISTORY & UI) --- 
if "history" not in st.session_state: st.session_state.history = []
if "dynamic_css" not in st.session_state: st.session_state.dynamic_css = ""  
if "ui_accent" not in st.session_state: st.session_state.ui_accent = "#00FFCC" # Neon Cyan
if "ui_accent_2" not in st.session_state: st.session_state.ui_accent_2 = "#FF007F" # Neon Pink
if "ui_bg_color" not in st.session_state: st.session_state.ui_bg_color = "#030508" # Abyss black
if "ui_text_color" not in st.session_state: st.session_state.ui_text_color = "#E0E6ED" 
if "language" not in st.session_state: st.session_state.language = "English"
if "image_cache" not in st.session_state: st.session_state.image_cache = {}

# Dynamic UI Text
if "ui_title" not in st.session_state: st.session_state.ui_title = "NEURAL-GRID // Story Engine"
if "ui_caption" not in st.session_state: st.session_state.ui_caption = "ARCHITECT INTERACTIVE NARRATIVES WITH AI."
if "ui_placeholder" not in st.session_state: st.session_state.ui_placeholder = "Input sequence..."
if "ui_settings_title" not in st.session_state: st.session_state.ui_settings_title = "⟁ SYSTEM OVERRIDES" 
if "ui_voice_label" not in st.session_state: st.session_state.ui_voice_label = "Narrator Voice Matrix"
if "ui_clear_btn" not in st.session_state: st.session_state.ui_clear_btn = "⚠️ PURGE MEMORY"
if "ui_toggle_label" not in st.session_state: st.session_state.ui_toggle_label = "👁️ Enable Visual Cortex"

# --- 3. ULTRA-FUTURISTIC HUD CSS INJECTION ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Share+Tech+Mono&display=swap');
    
    /* Global Base */
    .stApp {{ 
        background-color: {st.session_state.ui_bg_color}; 
        color: {st.session_state.ui_text_color}; 
        font-family: 'Rajdhani', sans-serif; 
        background-image: 
            radial-gradient(circle at 50% 50%, rgba(0, 255, 204, 0.05) 0%, rgba(0, 0, 0, 0.8) 100%),
            linear-gradient(rgba(0, 255, 204, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 204, 0.03) 1px, transparent 1px);
        background-size: 100% 100%, 40px 40px, 40px 40px;
        background-attachment: fixed;
    }}
    
    /* Glitch Title Effect */
    h1 {{
        background: linear-gradient(90deg, {st.session_state.ui_accent}, {st.session_state.ui_accent_2});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        text-align: center;
        letter-spacing: 4px;
        text-transform: uppercase;
        margin-bottom: 0px;
        position: relative;
    }}
    h1::after {{
        content: "NEURAL-GRID // Story Engine";
        position: absolute; left: 0; top: 0; width: 100%; height: 100%;
        background: linear-gradient(90deg, {st.session_state.ui_accent_2}, {st.session_state.ui_accent});
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        opacity: 0.5; filter: blur(4px); z-index: -1;
        animation: glitchPulse 2s infinite;
    }}
    @keyframes glitchPulse {{ 0%, 100% {{ opacity: 0.2; transform: translate(2px, 2px); }} 50% {{ opacity: 0.6; transform: translate(-2px, -2px); }} }}
    
    /* Hacker Terminal Input Boxes */
    div[data-baseweb="input"] {{
        background-color: rgba(0, 0, 0, 0.6) !important;
        border: none !important;
        border-bottom: 2px solid {st.session_state.ui_accent} !important;
        border-radius: 0 !important;
        box-shadow: 0 10px 15px -10px {st.session_state.ui_accent} !important;
        transition: all 0.3s ease;
    }}
    div[data-baseweb="input"]:focus-within {{ border-bottom: 2px solid {st.session_state.ui_accent_2} !important; box-shadow: 0 10px 20px -5px {st.session_state.ui_accent_2} !important; }}
    div[data-baseweb="input"] input {{
        color: {st.session_state.ui_accent} !important;
        font-family: 'Share Tech Mono', monospace !important;
        letter-spacing: 1px;
    }}
    
    /* Cyber-Cut Expanders (Angled Corners) */
    div[data-testid="stExpander"] {{
        background: rgba(5, 10, 15, 0.8) !important;
        border: 1px solid rgba(0, 255, 204, 0.3) !important;
        border-radius: 0 !important;
        clip-path: polygon(15px 0, 100% 0, 100% calc(100% - 15px), calc(100% - 15px) 100%, 0 100%, 0 15px);
        box-shadow: inset 0 0 20px rgba(0, 255, 204, 0.1) !important;
        backdrop-filter: blur(10px);
    }}
    
    /* Audio Player Glowing HUD Container */
    audio {{
        width: 100%;
        border-radius: 0;
        border: 1px solid {st.session_state.ui_accent};
        box-shadow: 0 0 15px rgba(0, 255, 204, 0.2);
        filter: invert(1) hue-rotate(180deg) brightness(1.5) contrast(1.2); /* Hacks standard audio player to look dark/neon */
        margin-top: 10px;
    }}
    
    .block-container {{ padding-top: 2rem; }}
    {st.session_state.dynamic_css}
    </style>
""", unsafe_allow_html=True)

# --- 4. SEQUENTIAL IMAGE ENGINE ---
def fetch_image(prompt_text, style_choice):
    cache_key = f"{prompt_text}_{style_choice}"
    if cache_key in st.session_state.image_cache: return st.session_state.image_cache[cache_key]

    if style_choice == "Comic Book": style_modifier = "comic book style, graphic novel ink, vibrant colors, halftone"
    elif style_choice == "Hyper-Realistic": style_modifier = "hyper-realistic, 8k resolution, cinematic lighting, photorealistic"
    else: style_modifier = "3D printed template style, octane render, unreal engine 5, smooth plastic"
        
    clean_prompt = prompt_text.replace('\n', ' ').strip()
    clean_prompt = re.sub(r'[^a-zA-Z0-9\s,]', '', clean_prompt)
    short_prompt = clean_prompt[:150] 
    
    safe_prompt = urllib.parse.quote(f"{short_prompt}, {style_modifier}")
    seed = random.randint(1, 1000000)
    image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=512&nologo=true&seed={seed}&model=flux"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    for attempt in range(3):
        try:
            response = requests.get(image_url, headers=headers, timeout=15)
            if response.status_code == 200:
                st.session_state.image_cache[cache_key] = response.content
                return response.content
        except Exception:
            time.sleep(1.5)
    return image_url

def render_story_and_images(full_text, current_style, message_id, should_generate_images):
    parts = re.split(r"\[SCENE:\s*(.*?)\]", full_text)
    pages = [{"prompt": parts[i+1].strip()} for i in range(0, len(parts) - 1, 2)]

    clean_story = re.sub(r"\[SCENE:\s*(.*?)\]", "\n\n", full_text).strip()
    st.markdown(f"<div style='font-size: 1.15em; line-height: 1.8; text-shadow: 0 0 5px rgba(255,255,255,0.2);'>{clean_story}</div>", unsafe_allow_html=True)
    
    if not should_generate_images or not pages:
        if pages: st.info("💡 VISUAL CORTEX OFFLINE. ENABLE IN SYSTEM OVERRIDES.")
        return 

    st.markdown(f"""
        <div style='border: 1px solid {st.session_state.ui_accent}; padding: 20px; 
                    margin-top: 20px; background: rgba(0,255,204,0.05); 
                    clip-path: polygon(20px 0, 100% 0, 100% calc(100% - 20px), calc(100% - 20px) 100%, 0 100%, 0 20px);
                    box-shadow: 0 0 20px rgba(0,255,204,0.1) inset;'>
            <h3 style='text-align: center; color: {st.session_state.ui_accent}; font-family: "Share Tech Mono", monospace; letter-spacing: 3px;'>
                [ VISUAL FEED ACTIVE ]
            </h3>
    """, unsafe_allow_html=True)
    
    state_key = f"scene_idx_{message_id}"
    if state_key not in st.session_state: st.session_state[state_key] = 0
    current_idx = st.session_state[state_key]
    total_images = len(pages)
    
    st.caption(f"**SCENE {current_idx + 1} // {total_images}** | *{pages[current_idx]['prompt']}*")
    
    with st.spinner("PROCESSING VISUAL DATA..."):
        img_bytes = fetch_image(pages[current_idx]["prompt"], current_style)
        if isinstance(img_bytes, bytes): st.image(img_bytes, use_container_width=True, clamp=True)
        elif isinstance(img_bytes, str): st.image(img_bytes, use_container_width=True, clamp=True)
            
    cols = st.columns([1, 1, 1])
    with cols[1]:
        if current_idx < total_images - 1:
            if st.button(f"NEXT SEQUENCE ⏭️", key=f"next_{message_id}_{current_idx}", use_container_width=True):
                st.session_state[state_key] += 1
                st.rerun()
        else:
            st.success("TRANSMISSION COMPLETE.")
            if st.button("⏪ RESTART FEED", key=f"reset_{message_id}", use_container_width=True):
                st.session_state[state_key] = 0
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# --- 5. MAIN INTERFACE ---
st.title(st.session_state.ui_title)
st.caption(st.session_state.ui_caption)

# HUD Settings Panel
with st.expander(st.session_state.ui_settings_title, expanded=False):
    col1, col2, col3, col4 = st.columns([1.5, 2, 2, 1.5])
    with col1:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_images = st.toggle(st.session_state.ui_toggle_label, value=True)
    with col2:
        art_style = st.selectbox("Render Engine", ["Comic Book", "Hyper-Realistic", "3D Render Template"])
    with col3:
        voice_type = st.selectbox(st.session_state.ui_voice_label, ["Cinematic Deep", "Anime Energetic", "Hyper-realistic Neural", "Lo-Fi Chill"])
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(st.session_state.ui_clear_btn, use_container_width=True):
            st.session_state.history = []
            st.session_state.image_cache = {}
            st.rerun()

# --- HOLOGRAPHIC LIVE AGENT (PURE PYTHON HACK) ---
st.markdown("---")
st.markdown("<h3 style='text-align: center; color: #00FFCC; font-family: \"Share Tech Mono\", monospace; letter-spacing: 2px;'>[ NEURAL VOICE UPLINK ]</h3>", unsafe_allow_html=True)

col1, col2 = st.columns([1, 3])

with col1:
    # 💥 UPGRADED HOLOGRAPHIC SCANNER 💥
    st.markdown("""
        <style>
            .holo-container {
                position: relative; width: 140px; height: 140px; margin: 0 auto;
                perspective: 1000px; transform-style: preserve-3d;
                overflow: hidden; border-radius: 50%; border: 1px solid rgba(0,255,204,0.2);
            }
            .holo-ring-1 {
                position: absolute; top: 5px; left: 5px; right: 5px; bottom: 5px;
                border: 2px solid rgba(0, 255, 204, 0.5); border-radius: 50%;
                box-shadow: 0 0 15px rgba(0, 255, 204, 0.3), inset 0 0 10px rgba(0, 255, 204, 0.3);
                animation: spinX 6s linear infinite;
            }
            .holo-ring-2 {
                position: absolute; top: 15px; left: 15px; right: 15px; bottom: 15px;
                border: 2px dashed rgba(255, 0, 127, 0.6); /* Neon Pink accent */
                border-radius: 50%;
                animation: spinY 4s linear infinite reverse;
            }
            .holo-core {
                position: absolute; top: 30px; left: 30px; right: 30px; bottom: 30px;
                background: radial-gradient(circle, rgba(0,255,204,1) 0%, rgba(0,255,204,0.2) 60%, transparent 80%);
                border-radius: 50%; box-shadow: 0 0 40px #00FFCC, inset 0 0 20px #00FFCC;
                animation: pulseCore 1.5s infinite alternate, microGlitch 3s infinite;
            }
            .laser-scan {
                position: absolute; top: 0; left: 0; width: 100%; height: 2px;
                background: #00FFCC; box-shadow: 0 0 15px 3px #00FFCC;
                animation: scan 2.5s ease-in-out infinite alternate; z-index: 10;
            }
            .eq-container { display: flex; justify-content: center; align-items: flex-end; height: 35px; margin-top: 15px; gap: 5px; }
            .eq-bar { width: 5px; background: #00FFCC; border-radius: 1px; animation: eq 0.6s infinite ease-in-out alternate; box-shadow: 0 0 10px #00FFCC;}
            .eq-bar:nth-child(1) { animation-delay: 0.1s; background: #FF007F; box-shadow: 0 0 10px #FF007F; }
            .eq-bar:nth-child(2) { animation-delay: 0.4s; }
            .eq-bar:nth-child(3) { animation-delay: 0.2s; }
            .eq-bar:nth-child(4) { animation-delay: 0.5s; }
            .eq-bar:nth-child(5) { animation-delay: 0.3s; background: #FF007F; box-shadow: 0 0 10px #FF007F; }

            @keyframes spinX { 100% { transform: rotateX(360deg) rotateY(180deg) rotateZ(90deg); } }
            @keyframes spinY { 100% { transform: rotateY(360deg) rotateX(180deg); } }
            @keyframes pulseCore { 0% { transform: scale(0.8); opacity: 0.7; } 100% { transform: scale(1.15); opacity: 1; filter: brightness(1.8); } }
            @keyframes scan { 0% { top: -10%; opacity: 0; } 10% { opacity: 1; } 90% { opacity: 1; } 100% { top: 110%; opacity: 0; } }
            @keyframes eq { 0% { height: 5px; opacity: 0.4;} 100% { height: 35px; opacity: 1;} }
            @keyframes microGlitch {
                0%, 96%, 98%, 100% { transform: translate(0,0) scale(1); filter: hue-rotate(0deg); opacity: 1; }
                97% { transform: translate(-4px, 3px) scale(1.05); filter: hue-rotate(90deg); opacity: 0.6; }
                99% { transform: translate(4px, -3px) scale(0.95); filter: hue-rotate(-90deg); opacity: 0.8; }
            }
        </style>

        <div class="holo-container">
            <div class="laser-scan"></div>
            <div class="holo-ring-1"></div>
            <div class="holo-ring-2"></div>
            <div class="holo-core"></div>
        </div>
        <div class="eq-container">
            <div class="eq-bar"></div><div class="eq-bar"></div><div class="eq-bar"></div><div class="eq-bar"></div><div class="eq-bar"></div>
        </div>
        <p style='text-align: center; color: #00FFCC; font-weight: bold; margin-top: 10px; font-family: "Share Tech Mono", monospace; letter-spacing: 3px; text-shadow: 0 0 10px #00FFCC;'>ONLINE</p>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("<p style='color: #8E9BAE; font-family: \"Share Tech Mono\", monospace; font-size: 0.9rem; text-transform: uppercase;'>Transmit secure narrative prompt. Audio synthesis engaged.</p>", unsafe_allow_html=True)
    
    commlink_input = st.text_input(">", placeholder="e.g., 'Agent, tell me the story of the space boy.'", key="commlink")
    
    if commlink_input:
        with st.spinner("TRANSMITTING ENCRYPTED SIGNAL..."):
            
            # 1. The Emotion & Mood Prompt
            voice_prompt = f"""
            You are NEURAL-GRID, a cinematic AI Storyteller.
            The user requested: "{commlink_input}"
            
            1. Write a thrilling, highly emotional story in {st.session_state.language}.
            2. Use heavy dramatic punctuation! Use ellipses (...) for deep pauses, exclamation marks (!) for shouting/action, and commas for breath. The TTS engine will use these to inject raw emotion into the voice.
            3. Analyze the story and pick ONE mood: "suspense", "emotional", "action", or "ambient".
            
            Output ONLY valid JSON in this exact format:
            {{
                "mood": "suspense",
                "story": "Your highly dramatic text here..."
            }}
            """
            try:
                # Get the JSON response from Groq
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": voice_prompt}],
                    temperature=0.7
                )
                
                # Parse the JSON
                raw_reply = response.choices[0].message.content.strip()
                if raw_reply.startswith("```json"):
                    raw_reply = raw_reply.replace("```json", "").replace("```", "").strip()
                
                import json
                data = json.loads(raw_reply)
                mood = data.get("mood", "ambient").lower()
                ai_reply = data.get("story", "Error parsing narrative sequence.")
                
                # 2. Dynamic Background Music Library (Royalty-Free Placeholders)
                bgm_tracks = {
                    "suspense": "[https://www.soundhelix.com/examples/mp3/SoundHelix-Song-16.mp3](https://www.soundhelix.com/examples/mp3/SoundHelix-Song-16.mp3)",
                    "emotional": "[https://www.soundhelix.com/examples/mp3/SoundHelix-Song-13.mp3](https://www.soundhelix.com/examples/mp3/SoundHelix-Song-13.mp3)",
                    "action": "[https://www.soundhelix.com/examples/mp3/SoundHelix-Song-14.mp3](https://www.soundhelix.com/examples/mp3/SoundHelix-Song-14.mp3)",
                    "ambient": "[https://www.soundhelix.com/examples/mp3/SoundHelix-Song-15.mp3](https://www.soundhelix.com/examples/mp3/SoundHelix-Song-15.mp3)"
                }
                selected_bgm = bgm_tracks.get(mood, bgm_tracks["ambient"])
                
                # 3. Generate the TTS Audio
                audio_file = "voice_response.mp3"
                target_voice = "en-US-ChristopherNeural" if st.session_state.language == "English" else "en-GB-SoniaNeural"
                
                async def generate_audio():
                    communicate = edge_tts.Communicate(ai_reply, target_voice)
                    await communicate.save(audio_file)
                
                # 3. Generate the TTS Audio (CLOUD SAFE VERSION)
                import tempfile
                import asyncio
                import base64
                
                target_voice = "en-US-ChristopherNeural" if st.session_state.language == "English" else "en-GB-SoniaNeural"
                
                # Create a secure temporary file that cloud servers allow
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                    temp_audio_path = tmp_file.name
                
                async def generate_audio():
                    communicate = edge_tts.Communicate(ai_reply, target_voice)
                    await communicate.save(temp_audio_path)
                
                # Safely hook into the cloud server's event loop
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                loop.run_until_complete(generate_audio())
                
                # 4. Embed Both Audio Tracks using custom HTML/JS
                with open(temp_audio_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode()
                
                st.success(f"✅ AUDIO SYNTHESIS COMPLETE. MOOD LOCKED: [{mood.upper()}]")
                
                # This script plays the music at 15% volume and the voice at 100%
                st.markdown(f"""
                    <audio id="bgm-player" src="{selected_bgm}" autoplay loop></audio>
                    <audio id="voice-player" src="data:audio/mp3;base64,{audio_b64}" autoplay></audio>
                    <script>
                        var bgm = document.getElementById("bgm-player");
                        var voice = document.getElementById("voice-player");
                        bgm.volume = 0.15; 
                        voice.volume = 1.0;
                        
                        // Automatically fade out background music when the voice finishes
                        voice.onended = function() {{
                            var fadeAudio = setInterval(function () {{
                                if ((bgm.volume - 0.05) > 0) {{
                                    bgm.volume -= 0.05;
                                }} else {{
                                    clearInterval(fadeAudio);
                                    bgm.pause();
                                }}
                            }}, 200);
                        }};
                    </script>
                """, unsafe_allow_html=True)
                
                with st.expander("👁️ DECRYPT TEXT TRANSCRIPT"):
                    st.write(ai_reply)
                    
            except Exception as e:
                st.error(f"UPLINK FAILED: {e}")
                
st.markdown("---")

# --- PROMPTPILOT AI TERMINAL ---
with st.expander("💻 [PROMPTPILOT_OS] :: AI_ORCHESTRATION_LAYER", expanded=False):
    st.markdown("<div class='promptpilot-box'>Awaiting natural language UI intent...</div>", unsafe_allow_html=True)
    with st.form("pilot_form", clear_on_submit=True):
        pilot_command = st.text_input(">", placeholder="e.g., 'Make background white, change language to Tamil'")
        submitted = st.form_submit_button("EXECUTE OVERRIDE ⚡")
    
    if submitted and pilot_command:
        with st.spinner("COMPILING OVERRIDES..."):
            ui_controller_prompt = f"""
            You are PromptPilot AI. Output ONLY a valid JSON object. Do not use markdown blocks.
            Intent: "{pilot_command}"
            Return ONLY this JSON format:
            {{ 
                "ui_bg_color": "<Hex color>", 
                "ui_text_color": "<Hex color>", 
                "ui_accent": "<Hex color>", 
                "dynamic_css": "<CSS or blank>", 
                "language": "<Target language>", 
                "ui_title": "<Translate 'NEURAL-GRID // Story Engine'>", 
                "ui_caption": "<Translate 'ARCHITECT INTERACTIVE NARRATIVES WITH AI.'>", 
                "ui_placeholder": "<Translate 'Input sequence...'>", 
                "ui_settings_title": "<Translate 'SYSTEM OVERRIDES'>", 
                "ui_voice_label": "<Translate 'Narrator Voice Matrix'>", 
                "ui_clear_btn": "<Translate 'PURGE MEMORY'>", 
                "ui_toggle_label": "<Translate 'Enable Visual Cortex'>", 
                "status_msg": "<Translated success message>" 
            }}
            """
            try:
                response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": ui_controller_prompt}], temperature=0.1)
                raw_output = response.choices[0].message.content.strip()
                json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
                ui_config = json.loads(json_match.group(0)) if json_match else json.loads(raw_output)
                st.session_state.update({k: ui_config.get(k, st.session_state.get(k)) for k in ui_config})
                st.rerun()
            except Exception as e:
                st.error(f"SYSTEM FAILURE: {e}")

# --- 6. CORE STORY LOGIC ---
system_prompt = f"""
You are a Master Storyteller. Write a complete, captivating story based on the user's prompt. 
Narrative voice: {voice_type}. Language: {st.session_state.language}.
CRITICAL RULES:
1. Write the full story text. Break it into clear paragraphs.
2. At the end of every major paragraph/page, insert a [SCENE: <visual description>] tag.
"""

# Render History
for idx, msg in enumerate(st.session_state.history):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant": render_story_and_images(msg["content"], art_style, idx, generate_images)
        else: st.markdown(msg["content"])

# Generate New Story
if prompt := st.chat_input(st.session_state.ui_placeholder):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend([{"role": m["role"], "content": m["content"]} for m in st.session_state.history])
        try:
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile", messages=messages, temperature=0.7, stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    clean_stream = re.sub(r"\[SCENE:.*?\]", "\n\n*(Visualizing sequence...)*\n\n", full_response)
                    message_placeholder.markdown(clean_stream + "▌")
            
            message_placeholder.empty()
            current_msg_idx = len(st.session_state.history)
            
            render_story_and_images(full_response, art_style, current_msg_idx, generate_images)
            st.session_state.history.append({"role": "assistant", "content": full_response})
        except Exception as e: st.error(f"SYSTEM ERROR: {e}")
