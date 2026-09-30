"""
WhatWay mascot "Pip": 8-bit teal square with eyes.
"""

from __future__ import annotations

import html
import json as _json
from pathlib import Path
from typing import List, Optional

import streamlit as st
import streamlit.components.v1 as components

_ROOT = Path(__file__).resolve().parent.parent
_PIP_PNG = _ROOT / "assets" / "pip_avatar.png"
_USER_PNG = _ROOT / "assets" / "user_dots.png"
# Prefer real Pip face for chat avatar; emoji fallback
PIP_AVATAR = str(_PIP_PNG) if _PIP_PNG.exists() else "🟩"
# User messages: teal ⋯ (message / conversation), not Streamlit’s red person or a map pin
USER_AVATAR = str(_USER_PNG) if _USER_PNG.exists() else "⋯"

# Pixel square face (32×32), WhatWay teal
PIP_BALL_SVG = """
<svg class="pip-sprite" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg" aria-label="Pip" shape-rendering="crispEdges">
  <!-- body -->
  <rect x="4" y="4" width="24" height="24" fill="#0E6B54"/>
  <!-- highlight edge -->
  <rect x="4" y="4" width="24" height="2" fill="#8FD4B8"/>
  <rect x="4" y="4" width="2" height="24" fill="#8FD4B8"/>
  <!-- shadow edge -->
  <rect x="4" y="26" width="24" height="2" fill="#0A4B3A"/>
  <rect x="26" y="4" width="2" height="24" fill="#0A4B3A"/>
  <!-- eyes -->
  <rect class="eye" x="10" y="12" width="4" height="4" fill="#10221B"/>
  <rect class="eye" x="18" y="12" width="4" height="4" fill="#10221B"/>
  <rect class="eye" x="11" y="13" width="1" height="1" fill="#E8FFF5"/>
  <rect class="eye" x="19" y="13" width="1" height="1" fill="#E8FFF5"/>
  <!-- smile -->
  <rect x="12" y="20" width="2" height="2" fill="#10221B"/>
  <rect x="14" y="21" width="4" height="2" fill="#10221B"/>
  <rect x="18" y="20" width="2" height="2" fill="#10221B"/>
</svg>
"""


def pip_say(text: str, *, name: str = "Pip") -> None:
    """Render a Pip speech bubble (single Pip face: hides Streamlit’s duplicate avatar)."""
    if not text:
        return
    import re

    def boldify(s: str) -> str:
        parts = re.split(r"(\*\*[^*]+\*\*)", s)
        out = []
        for p in parts:
            if p.startswith("**") and p.endswith("**"):
                out.append(f"<strong>{html.escape(p[2:-2])}</strong>")
            else:
                out.append(html.escape(p).replace("\n", "<br>"))
        return "".join(out)

    body = boldify(text)
    st.markdown(
        f"""
<style>
/* Hide Streamlit chat avatar when Pip bubble is present (avoid double Pip) */
div[data-testid="stChatMessage"]:has(.pip-chat) [data-testid="stChatMessageAvatar"],
div[data-testid="stChatMessage"]:has(.pip-chat) img[alt="assistant avatar"],
div[data-testid="stChatMessage"]:has(.pip-chat) > div:first-child:has(img) {{
  display: none !important;
}}
div[data-testid="stChatMessage"]:has(.pip-chat) {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding-left: 0 !important;
}}
.pip-chat {{
  display: flex; align-items: flex-start; gap: 0.75rem;
  margin: 0.1rem 0 0.75rem 0;
  font-family: 'DM Sans', system-ui, sans-serif;
}}
.pip-chat .pip-sprite {{
  width: 48px; height: 48px; flex-shrink: 0;
  image-rendering: pixelated;
  animation: pip-bob 2.6s ease-in-out infinite;
}}
.pip-chat-bubble {{
  background: #fff;
  border: 2px solid #0E6B54;
  border-radius: 16px 16px 16px 4px;
  padding: 0.7rem 1rem;
  box-shadow: 0 4px 14px rgba(14, 107, 84,0.16);
  max-width: min(48rem, 100%);
}}
.pip-chat-name {{
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em;
  text-transform: uppercase; color: #0A4B3A; margin-bottom: 0.25rem;
}}
.pip-chat-text {{
  color: #10221B; font-size: 0.98rem; line-height: 1.45; font-weight: 500;
}}
</style>
<div class="pip-chat">
  {PIP_BALL_SVG}
  <div class="pip-chat-bubble">
    <div class="pip-chat-name">{html.escape(name)}</div>
    <div class="pip-chat-text">{body}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

def render_pip(
    lang: str = "en",
    greeting: str = "",
    ask_prefix: str = "Ask about ",
    phrases: List[str] | None = None,
) -> None:
    phrases = phrases or [
        "dental care",
        "ESL classes",
        "legal help",
        "shelter tonight",
        "a clinic nearby",
    ]
    phrases_json = _json.dumps(phrases, ensure_ascii=False)
    greeting_esc = html.escape(greeting)
    prefix_esc = html.escape(ask_prefix)

    st.markdown(
        f"""
<style>
@keyframes pip-bob {{
  0%, 100% {{ transform: translateY(0); }}
  50% {{ transform: translateY(-4px); }}
}}
@keyframes pip-blink {{
  0%, 88%, 100% {{ transform: scaleY(1); }}
  90%, 94% {{ transform: scaleY(0.15); }}
}}
.pip-wrap {{
  display: flex;
  align-items: center;
  gap: 0.9rem;
  margin: 0.15rem 0 1.1rem 0;
  font-family: 'DM Sans', system-ui, sans-serif;
}}
.pip-sprite {{
  width: 56px;
  height: 56px;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  animation: pip-bob 2.6s ease-in-out infinite;
  flex-shrink: 0;
}}
.pip-sprite .eye {{
  transform-origin: center;
  animation: pip-blink 3.8s step-end infinite;
}}
.pip-bubble {{
  background: #fff;
  border: 2px solid #0E6B54;
  border-radius: 20px;
  padding: 0.85rem 1.1rem;
  box-shadow: 0 6px 18px rgba(14, 107, 84, 0.18);
  max-width: min(48rem, 100%);
  min-width: min(100%, 18rem);
  position: relative;
  font-family: 'DM Sans', system-ui, sans-serif;
}}
.pip-bubble:before {{
  content: "";
  position: absolute;
  left: -7px;
  top: 50%;
  margin-top: -6px;
  width: 12px;
  height: 12px;
  background: #fff;
  border-left: 2px solid #0E6B54;
  border-bottom: 2px solid #0E6B54;
  transform: rotate(45deg);
}}
.pip-hi {{
  margin: 0 0 0.35rem 0;
  color: #2d6b54;
  font-weight: 700;
  font-size: 1rem;
}}
.pip-ask {{
  margin: 0;
  font-size: 0.98rem;
  font-weight: 500;
  min-height: 1.4em;
}}
.pip-ask .prefix {{ color: #4A5F55; font-weight: 500; }}
.pip-ask .typed {{ color: #8FD4B8; font-weight: 600; }}
.pip-ask .cursor {{
  display: inline-block;
  width: 2px;
  height: 1em;
  background: #8FD4B8;
  margin-left: 2px;
  vertical-align: -2px;
  animation: blink-caret 0.9s step-end infinite;
}}
@keyframes blink-caret {{ 50% {{ opacity: 0; }} }}
</style>
<div class="pip-wrap">
  {PIP_BALL_SVG}
  <div class="pip-bubble">
    <p class="pip-hi">{greeting_esc}</p>
    <p class="pip-ask" id="ww-ask-line">
      <span class="prefix">{prefix_esc}</span><span class="typed" id="ww-typed"></span><span class="cursor"></span>
    </p>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    components.html(
        f"""
<script>
(function() {{
  const phrases = {phrases_json};
  function findEl() {{
    try {{
      for (const d of [document, window.parent.document]) {{
        const el = d.getElementById('ww-typed');
        if (el) return el;
      }}
    }} catch (e) {{}}
    return null;
  }}
  let pi = 0, ci = 0, deleting = false;
  const typeMs = 58, holdMs = 2400, delMs = 30;
  function tick() {{
    const el = findEl();
    if (!el) {{ setTimeout(tick, 200); return; }}
    const word = phrases[pi % phrases.length];
    if (!deleting) {{
      ci++;
      el.textContent = word.slice(0, ci);
      if (ci >= word.length) {{ deleting = true; setTimeout(tick, holdMs); return; }}
      setTimeout(tick, typeMs);
    }} else {{
      ci--;
      el.textContent = word.slice(0, Math.max(0, ci));
      if (ci <= 0) {{ deleting = false; pi++; setTimeout(tick, 320); return; }}
      setTimeout(tick, delMs);
    }}
  }}
  setTimeout(tick, 450);
}})();
</script>
""",
        height=0,
    )
