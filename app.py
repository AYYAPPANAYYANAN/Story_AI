        )

        if st.button(
            "▶ Tell this story",
            key=f"tell_existing_{active.get('id', 'active')}",
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
        st.markdown("#### Illustrations")

        for scene_idx, scene in enumerate(scenes):
            with st.container(border=True):
                st.markdown(
                    f'<div class="scene-header">SCENE {scene_idx + 1} · {scene.get("title", "Scene")}</div>',
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
                        "Illustration unavailable. The story remains available."
                    )


# ============================================================
# New story creation
# ============================================================
st.markdown("---")
st.markdown("### Create a new story")

prompt = st.chat_input(
    "Describe the story you want to create..."
)

if prompt:
    prompt = clean_prompt(prompt)

    if not prompt:
        st.warning("Please enter a story request.")
        st.stop()

    if not GROQ_API_KEY:
        st.error("GROQ_API_KEY is not configured.")
        st.stop()

    with st.spinner("Creating story, characters and scenes..."):
        try:
            result = generate_story(
                prompt,
                st.session_state.language,
                st.session_state.narrator,
            )

            story_id = save_story(
                result["title"],
                result,
            )

            # Store the original prompt too.
            st.session_state.stories[story_id]["prompt"] = prompt
            st.session_state.current_story_id = story_id
            st.session_state.pending_story = st.session_state.stories[story_id]

            st.session_state.history.append(
                {"role": "user", "content": prompt}
            )
            st.session_state.history.append(
                {"role": "assistant", "content": result["story"]}
            )

            if len(st.session_state.history) > MAX_HISTORY:
                st.session_state.history = st.session_state.history[-MAX_HISTORY:]

            st.rerun()

        except Exception as exc:
            st.session_state.last_error = safe_error(exc)
            st.error(f"Story generation failed: {st.session_state.last_error}")


# ============================================================
# Footer
# ============================================================
st.markdown("---")
st.caption(
    "Story Studio • Enterprise architecture • "
    "Structured story generation • Persistent scene cache • Character narration"
)
