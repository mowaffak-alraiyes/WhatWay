"""
Pip voice helpers — patterned after Vera (drdavidl/pad Vera.py).

TTS backends (first available wins):
1. ElevenLabs  — if elevenlabs_api_key in secrets (Vera default)
2. OpenAI TTS  — if OPENAI_API_KEY in secrets (Vera fallback talk_stream)
3. Browser Web Speech API — free, no key (Aidr default for demo)

Also: optional mic via st.audio_input + Whisper when OpenAI key exists.
"""

from __future__ import annotations

import base64
import html
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components


def _secret(key: str) -> Optional[str]:
    val = os.environ.get(key)
    if val:
        return val
    try:
        return st.secrets.get(key)
    except Exception:
        return None


def strip_markdown_for_speech(text: str) -> str:
    """Keep TTS natural — drop markdown chrome."""
    if not text:
        return ""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    t = re.sub(r"[*_`#]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Keep Pip intros short for voice
    if len(t) > 280:
        t = t[:277].rsplit(" ", 1)[0] + "…"
    return t


def autoplay_local_audio(filepath: str) -> None:
    """Vera-style: base64 MP3 + autoplaying <audio> tag."""
    try:
        with open(filepath, "rb") as f:
            data = f.read()
    except OSError:
        return
    b64 = base64.b64encode(data).decode()
    components.html(
        f"""
        <audio autoplay="true" controls style="width:100%;margin:0.25rem 0;">
          <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """,
        height=56,
    )


def speak_browser(text: str) -> None:
    """Free TTS via Web Speech API (no API key)."""
    safe = html.escape(strip_markdown_for_speech(text)).replace("\n", " ")
    if not safe:
        return
    components.html(
        f"""
        <script>
        (function() {{
          const text = {repr(strip_markdown_for_speech(text))};
          try {{
            if (!window.speechSynthesis) return;
            window.speechSynthesis.cancel();
            const u = new SpeechSynthesisUtterance(text);
            u.rate = 1.02;
            u.pitch = 1.05;
            // Prefer a clear English voice when available
            const voices = window.speechSynthesis.getVoices();
            const pick = voices.find(v => /en(-|_)US/i.test(v.lang) && /female|samantha|karen|google/i.test(v.name))
              || voices.find(v => /^en/i.test(v.lang));
            if (pick) u.voice = pick;
            window.speechSynthesis.speak(u);
          }} catch (e) {{}}
        }})();
        </script>
        <p style="font-size:0.8rem;color:#5a7368;margin:0;">🔊 Pip speaking…</p>
        """,
        height=28,
    )


def text_to_speech_elevenlabs(text: str) -> Optional[str]:
    """Vera's ElevenLabs path — returns mp3 path or None."""
    api_key = _secret("elevenlabs_api_key") or _secret("ELEVENLABS_API_KEY")
    if not api_key:
        return None
    try:
        from elevenlabs import VoiceSettings
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=api_key)
        voice_id = _secret("ELEVENLABS_VOICE_ID") or "9BWtsMINqrJLrRacOk9x"  # Aria
        response = client.text_to_speech.convert(
            voice_id=voice_id,
            output_format="mp3_22050_32",
            text=strip_markdown_for_speech(text),
            model_id="eleven_multilingual_v2",
            voice_settings=VoiceSettings(
                stability=0.35,
                similarity_boost=0.85,
                style=0.2,
                use_speaker_boost=True,
            ),
        )
        path = Path(tempfile.gettempdir()) / "aidr_pip_last.mp3"
        with open(path, "wb") as f:
            for chunk in response:
                if chunk:
                    f.write(chunk)
        return str(path)
    except Exception as e:
        print(f"ElevenLabs TTS error: {e}")
        return None


def text_to_speech_openai(text: str) -> Optional[str]:
    """Vera's OpenAI talk_stream path — returns mp3 path or None."""
    api_key = _secret("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        path = Path(tempfile.gettempdir()) / "aidr_pip_last.mp3"
        response = client.audio.speech.create(
            model=_secret("OPENAI_TTS_MODEL") or "tts-1",
            voice=_secret("OPENAI_TTS_VOICE") or "nova",
            input=strip_markdown_for_speech(text),
        )
        response.stream_to_file(str(path))
        return str(path)
    except Exception as e:
        print(f"OpenAI TTS error: {e}")
        return None


def speak_pip(text: str, force: bool = False) -> None:
    """
    Speak Pip's line (Vera-style after each answer).
    Honors sidebar toggle `pip_voice_enabled` unless force=True.
    """
    if not text:
        return
    if not force and not st.session_state.get("pip_voice_enabled", True):
        return

    # Prefer paid keys when present (Vera parity), else free browser TTS
    path = text_to_speech_elevenlabs(text) or text_to_speech_openai(text)
    if path:
        autoplay_local_audio(path)
        return
    speak_browser(text)


def whisper_transcribe(audio_bytes: bytes, filename: str = "clip.wav") -> Optional[str]:
    """Transcribe mic audio with OpenAI Whisper when keyed."""
    api_key = _secret("OPENAI_API_KEY")
    if not api_key or not audio_bytes:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        suffix = Path(filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as audio_file:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
            return (result.text or "").strip()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as e:
        print(f"Whisper error: {e}")
        return None


def render_voice_toggle(lang: str = "en") -> None:
    """Prominent sidebar on/off for Pip speech (default off)."""
    st.session_state.setdefault("pip_voice_enabled", False)
    st.markdown(
        '<p class="aidr-side-title">Voice</p>',
        unsafe_allow_html=True,
    )
    st.toggle(
        "Pip speaks replies",
        key="pip_voice_enabled",
        help="When on, Pip reads short answers aloud. Turn off anytime.",
    )
    if st.session_state.get("pip_voice_enabled"):
        backend = "Browser (free)"
        if _secret("elevenlabs_api_key") or _secret("ELEVENLABS_API_KEY"):
            backend = "ElevenLabs"
        elif _secret("OPENAI_API_KEY"):
            backend = "OpenAI TTS"
        st.caption(f"On · {backend}")
    else:
        st.caption("Off")


def render_voice_mic(lang: str = "en") -> None:
    """Optional mic input (Whisper when OpenAI key exists)."""
    audio = st.audio_input("Talk to Pip", key="pip_mic_clip")
    if audio is not None:
        raw = audio.getvalue()
        text = whisper_transcribe(raw, getattr(audio, "name", "clip.wav"))
        if text:
            st.session_state["voice_prompt_pending"] = text
            st.success(f"Heard: {text}")
        elif not _secret("OPENAI_API_KEY"):
            st.caption("Mic needs OPENAI_API_KEY for Whisper — or type below.")
        else:
            st.caption("Couldn’t transcribe that clip — try again.")


def render_voice_controls(lang: str = "en") -> None:
    """Full voice block: toggle + optional mic."""
    render_voice_toggle(lang)
    render_voice_mic(lang)
