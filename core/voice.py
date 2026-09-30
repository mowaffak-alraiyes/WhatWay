"""
Pip voice helpers  -  patterned after Vera (drdavidl/pad Vera.py).

TTS (Pip speaks replies):
1. ElevenLabs / OpenAI TTS  -  if keys present
2. Browser Web Speech API  -  free default (uses UI language when set)
"""

from __future__ import annotations

import base64
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

# BCP-47 tags for browser speechSynthesis
SPEECH_LANG = {
    "en": "en-US",
    "es": "es-ES",
    "ar": "ar-SA",
    "fr": "fr-FR",
    "pl": "pl-PL",
    "zh": "zh-CN",
    "ur": "ur-PK",
    "hi": "hi-IN",
    "uk": "uk-UA",
    "sw": "sw-KE",
}


def _secret(key: str) -> Optional[str]:
    val = os.environ.get(key)
    if val:
        return val
    try:
        return st.secrets.get(key)
    except Exception:
        return None


def strip_markdown_for_speech(text: str) -> str:
    """Keep TTS natural  -  drop markdown chrome."""
    if not text:
        return ""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    t = re.sub(r"[*_`#]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
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


def speak_browser(text: str, lang: str = "en") -> None:
    """Free TTS via Web Speech API. Falls back to English with a gentle note if needed."""
    if not text:
        return
    import core.i18n as i18n

    spoken = strip_markdown_for_speech(text)
    code = (lang or "en").lower()[:2]
    bcp = SPEECH_LANG.get(code, "en-US")
    want_lang = code != "en"
    note = i18n.t("voice_fallback_note", code) if want_lang else ""
    components.html(
        f"""
<div id="ww-voice-wrap" style="font-family:system-ui,sans-serif;margin:0;">
  <p id="ww-voice-status" style="font-size:0.8rem;color:#4A5F55;margin:0;">🔊 Pip speaking…</p>
  <p id="ww-voice-note" style="display:none;font-size:0.75rem;color:#4A5F55;margin:0.2rem 0 0 0;"></p>
</div>
<script>
(function () {{
  const text = {repr(spoken)};
  const lang = {repr(bcp)};
  const wantLang = {str(want_lang).lower()};
  const fallbackNote = {repr(note)};
  const status = document.getElementById("ww-voice-status");
  const noteEl = document.getElementById("ww-voice-note");

  function run(voices) {{
    try {{
      if (!window.speechSynthesis) {{
        if (status) status.textContent = "Voice isn’t available in this browser.";
        return;
      }}
      window.speechSynthesis.cancel();
      const prefix = lang.slice(0, 2).toLowerCase();
      const match = voices.find(v => (v.lang || "").toLowerCase().startsWith(prefix));
      const en = voices.find(v => /^en/i.test(v.lang || ""));
      const pick = match || en || voices[0];
      const missing = wantLang && !match;

      if (missing && noteEl && fallbackNote) {{
        noteEl.style.display = "block";
        noteEl.textContent = fallbackNote;
      }}
      if (!pick) {{
        if (status) status.textContent = "No voices installed  -  you can still read Pip’s reply.";
        return;
      }}

      const u = new SpeechSynthesisUtterance(text);
      u.voice = pick;
      u.lang = match ? lang : (pick.lang || "en-US");
      u.rate = 1.02;
      u.pitch = 1.05;
      window.speechSynthesis.speak(u);
    }} catch (e) {{
      if (status) status.textContent = "Couldn’t play voice  -  you can still read the reply.";
    }}
  }}

  function start() {{
    const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
    if (voices && voices.length) {{ run(voices); return; }}
    if (window.speechSynthesis) {{
      window.speechSynthesis.onvoiceschanged = function () {{
        run(window.speechSynthesis.getVoices() || []);
      }};
      // Some browsers need a tick
      setTimeout(function () {{
        const v = window.speechSynthesis.getVoices() || [];
        if (v.length) run(v);
      }}, 250);
    }}
  }}
  start();
}})();
</script>
        """,
        height=52,
    )


def text_to_speech_elevenlabs(text: str) -> Optional[str]:
    api_key = _secret("elevenlabs_api_key") or _secret("ELEVENLABS_API_KEY")
    if not api_key:
        return None
    try:
        from elevenlabs import VoiceSettings
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=api_key)
        voice_id = _secret("ELEVENLABS_VOICE_ID") or "9BWtsMINqrJLrRacOk9x"
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
        path = Path(tempfile.gettempdir()) / "ww_pip_last.mp3"
        with open(path, "wb") as f:
            for chunk in response:
                if chunk:
                    f.write(chunk)
        return str(path)
    except Exception as e:
        print(f"ElevenLabs TTS error: {e}")
        return None


def text_to_speech_openai(text: str) -> Optional[str]:
    api_key = _secret("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        path = Path(tempfile.gettempdir()) / "ww_pip_last.mp3"
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


def speak_pip(text: str, force: bool = False, lang: str = "en") -> None:
    """Speak Pip's line in the UI language when using browser TTS."""
    if not text:
        return
    if not force and not st.session_state.get("pip_voice_enabled", True):
        return
    path = text_to_speech_elevenlabs(text) or text_to_speech_openai(text)
    if path:
        autoplay_local_audio(path)
        return
    speak_browser(text, lang=lang)


def render_voice_toggle(lang: str = "en") -> None:
    """Pip reads answers aloud (free browser TTS by default)."""
    st.session_state.setdefault("pip_voice_enabled", False)
    st.markdown('<p class="ww-side-title">Voice</p>', unsafe_allow_html=True)
    st.toggle(
        "Pip speaks replies",
        key="pip_voice_enabled",
        help="When on, Pip reads short answers aloud (free in the browser).",
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
