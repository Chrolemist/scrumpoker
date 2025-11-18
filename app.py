# Lista med roliga anonyma namn
ANONYMOUS_NAMES = [
    "Anonym Älg", "Kod-Katt", "Buggsurfare", "Pixel-Panda", "Fikafantast", "Test-Tiger",
    "Debug-Delfin", "Sprint-Spindel", "Release-Räv", "Commit-Koala", "Merge-Mås",
    "Pull-Pingvin", "Push-Papegoja", "Branch-Björn", "Feature-Får", "Hotfix-Hund",
    "Epic-Ekorre", "Story-Säl", "Task-Tupp", "Retro-Ren"
]

import time, uuid
from html import escape
import statistics
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# All data lagras i minnet under sessionen
ROOMS = {}

DEFAULT_TSHIRT = ["XS", "S", "M", "L", "XL"]
DEFAULT_SCALE = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}

def load_rooms():
    """Returnerar alla rum från minnet."""
    return ROOMS

def save_rooms(rooms):
    """Sparar rum till minnet (ingen disk)."""
    global ROOMS
    ROOMS = rooms

def init_room(rooms, room_code):
    if room_code not in rooms:
        rooms[room_code] = {
            "created": time.time(),
            # Stories
            "stories": [],  # list of {id, title, created}
            "active_story_id": None,
            # scale_mode: 'points' => uses 'scale' mapping; 'tshirt' => uses 'scale_labels'
            "scale_mode": "points",
            "scale": DEFAULT_SCALE.copy(),
            "scale_labels": DEFAULT_TSHIRT[:],
            # votes: story_id -> {player_name -> value}
            "votes": {},
            # revealed_for: story_id -> bool
            "revealed_for": {},
            "timer": {
                "end": None,
                "duration": 0,
            },
            "players": [],
            # transient pings: name -> unix ts
            "pings": {},
            # chat: list of {name, text, ts}
            "chat": [],
            "last_update": time.time(),
        }

def migrate_room(room: dict) -> bool:
    """Migrate older single-story schema to multi-story schema. Returns True if modified."""
    changed = False
    # If single 'story' key exists, migrate it
    if "stories" not in room:
        room["stories"] = []
        changed = True
    if "active_story_id" not in room:
        room["active_story_id"] = None
        changed = True
    # Migrate old single fields
    if "story" in room:
        title = room.get("story") or ""
        sid = uuid.uuid4().hex[:8]
        room["stories"].append({"id": sid, "text": title, "created": time.time()})
        room["active_story_id"] = sid
        room.pop("story", None)
        changed = True
        # Migrate votes and revealed
        old_votes = room.get("votes", {})
        if isinstance(old_votes, dict) and (not old_votes or all(not isinstance(v, dict) for v in old_votes.values())):
            room["votes"] = {sid: old_votes}
        if "revealed" in room:
            room["revealed_for"] = {sid: bool(room.get("revealed", False))}
            room.pop("revealed", None)
    # Ensure keys exist
    room.setdefault("votes", {})
    room.setdefault("revealed_for", {})
    room.setdefault("players", [])
    room.setdefault("pings", {})
    room.setdefault("chat", [])
    # Ensure active story exists
    if not room["stories"]:
        sid = uuid.uuid4().hex[:8]
        room["stories"].append({"id": sid, "text": "", "created": time.time()})
        room["active_story_id"] = sid
        changed = True
    if room["active_story_id"] not in {s["id"] for s in room["stories"]}:
        room["active_story_id"] = room["stories"][0]["id"]
        changed = True
    # Ensure dicts for current story
    sid = room["active_story_id"]
    room["votes"].setdefault(sid, {})
    room["revealed_for"].setdefault(sid, False)
    # Normalize story items to have 'text' key
    for s in room["stories"]:
        if "text" not in s:
            s["text"] = s.pop("title", "")
    return changed

def update_room(room_code, mutate_fn):
    rooms = load_rooms()
    init_room(rooms, room_code)
    # migrate before mutation
    if migrate_room(rooms[room_code]):
        pass
    mutate_fn(rooms[room_code])
    rooms[room_code]["last_update"] = time.time()
    if isinstance(rooms[room_code].get("players"), set):
        rooms[room_code]["players"] = list(rooms[room_code]["players"])
    rooms[room_code]["players"] = list(dict.fromkeys(rooms[room_code]["players"]))
    save_rooms(rooms)

def get_room(room_code):
    rooms = load_rooms()
    room = rooms.get(room_code)
    if room is None:
        return None
    if migrate_room(room):
        rooms[room_code] = room
        save_rooms(rooms)
    return room

# --- UI Helpers ---
@st.cache_data(ttl=2)
def cached_room(room_code, last_update):
    """Cachad läsning av rum som kan invalidieras med last_update."""
    return get_room(room_code)

CSS = """
<style>
body { overflow-x: hidden; }
.block-container { padding-top: 1rem !important; }
.card-grid { display: flex; flex-wrap: wrap; gap: 1.25rem; }
.card { position: relative; width: 100px; height: 140px; perspective: 800px; cursor: pointer; }
.card-inner { position: absolute; width: 100%; height: 100%; transition: transform 0.8s; transform-style: preserve-3d; }
.card.flip .card-inner { transform: rotateY(180deg); }
.card-face { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 10px; display:flex; align-items:center; justify-content:center; font-weight:600; font-size:1.4rem; letter-spacing:1px; padding: 8px; overflow-wrap: anywhere; word-break: break-word; line-height: 1.1; text-align: center; }
.card-front .name.long { font-size: 1.0rem; }
.card-front { background: linear-gradient(135deg, #202431 0%, #2b2f3b 60%, #343948 100%); box-shadow:0 0 8px rgba(108,93,211,0.5); }
.card-back { background: linear-gradient(135deg, #6C5DD3, #8E7BFF); transform: rotateY(180deg); box-shadow:0 0 12px rgba(120,80,255,0.6); }
.card:hover .card-front { animation: rgbPulse 2s linear infinite; }
@keyframes rgbPulse { 0% { box-shadow:0 0 8px #ff004c; } 33% { box-shadow:0 0 8px #00e1ff; } 66% { box-shadow:0 0 8px #7dff00; } 100% { box-shadow:0 0 8px #ff004c; } }
.card.pinged .card-front { box-shadow:0 0 14px rgba(255,180,40,0.9); }
@keyframes shake {
    0% { transform: translateX(0) scale(1.06); }
    20% { transform: translateX(-4px) scale(1.06); }
    40% { transform: translateX(4px) scale(1.06); }
    60% { transform: translateX(-3px) scale(1.06); }
    80% { transform: translateX(3px) scale(1.06); }
    100% { transform: translateX(0) scale(1.06); }
}
.card.pinged .card-inner { animation: shake 0.5s ease-in-out infinite; }
.reveal-badge { background:#6C5DD3; padding:0.4rem 0.8rem; border-radius:6px; font-size:0.8rem; margin-left:0.5rem; }
.consensus { color:#7dff00; font-weight:600; }
.warning { color:#ffcc00; }
.timer { font-size:1rem; font-weight:600; display:inline-block; padding:0.3rem 0.6rem; background:rgba(108,93,211,0.15); border-radius:6px; white-space:nowrap; }
/* Stories UI – tabell/lista utan extra kort */
@keyframes rgbBorder { 
    0% { border-color: #ff004c; box-shadow: 0 0 10px rgba(255,0,76,0.5); } 
    33% { border-color: #00e1ff; box-shadow: 0 0 10px rgba(0,225,255,0.5); } 
    66% { border-color: #7dff00; box-shadow: 0 0 10px rgba(125,255,0,0.5); } 
    100% { border-color: #ff004c; box-shadow: 0 0 10px rgba(255,0,76,0.5); } 
}

/* Active story badge inline in expander header using pseudo-element */
.active-expander-marker ~ * [data-testid="stExpander"] summary::after {
    content: "Aktiv";
    display: inline-block;
    margin-left: 8px;
    padding: 2px 8px;
    border-radius: 6px;
    border: 1px solid #6C5DD3;
    background: rgba(108,93,211,0.12);
    color: #cfcff7;
    font-size: 0.8rem;
    line-height: 1.2;
}

/* Make expander titles wrap and show full text */
[data-testid="stExpander"] summary {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: unset !important;
    word-break: break-word;
}

/* Sidebar chat styles */
.sidebar-chat-box { max-height: 260px; overflow-y: auto; padding-right: 6px; margin-bottom: 8px; }
.chat-msg { margin: 8px 0; }
.chat-name { font-size: 0.75rem; color: #9aa0b3; margin-bottom: 2px; }
.chat-row { display: block; }
.chat-row.right { text-align: right; }
.chat-bubble { display: inline-block; padding: 8px 10px; border-radius: 12px; background: #2b2f3b; color: #e6e8f0; box-shadow: 0 0 6px rgba(0,0,0,0.2); max-width: 100%; word-wrap: break-word; }
.chat-bubble.mine { background: #6C5DD3; color: #ffffff; }

/* Active select button RGB glow */


.story-arrow {
    display:none;
    position:absolute;
    left:-20px;
    top:50%;
    transform:translateY(-50%);
    font-size:1.2rem;
    color:#6C5DD3;
    animation:arrowGlow 2s ease-in-out infinite alternate;
}
.story-row.active-story .story-arrow {
    display:block;
}
@keyframes arrowGlow {
    0% { text-shadow:0 0 5px #6C5DD3, 0 0 10px #6C5DD3; }
    100% { text-shadow:0 0 10px #6C5DD3, 0 0 20px #6C5DD3, 0 0 30px #6C5DD3; }
}
</style>
"""

st.set_page_config(page_title="Scrum Poker", page_icon="🃏", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

st.title("Scrum Poker")

# Lightweight global sync so all clients see latest stories without manual refresh
st_autorefresh(interval=4000, key="room_sync_refresh")

# --- Sidebar setup ---
st.sidebar.header("Inställningar")
room_code = st.sidebar.text_input("Rumskod", value=st.session_state.get("room_code", "TEAM1"))
if room_code != st.session_state.get("room_code"):
    st.session_state["room_code"] = room_code



# Tilldela alltid anonymt namn direkt vid start om inget finns
if "player_name" not in st.session_state or not st.session_state["player_name"]:
    import random
    st.session_state["player_name"] = random.choice(ANONYMOUS_NAMES)

_prev_name = st.session_state.get("player_name", "")
player_name_input = st.sidebar.text_input(
    "Ditt namn",
    value=_prev_name,
    help="Du kan byta namn – röster följer med.",
)
player_name = player_name_input.strip()

if player_name != _prev_name:
    # uppdatera lokalt
    st.session_state["player_name"] = player_name

    def apply_rename(r):
        # ta bort tomma namn ur players-listan
        r["players"] = [n for n in r.get("players", []) if n]

        # byt namn i players-listan
        if _prev_name and _prev_name in r["players"]:
            r["players"] = [player_name if n == _prev_name else n for n in r["players"]]

        # lägg till nytt namn om det inte redan finns och inte är tomt
        if player_name and player_name not in r["players"]:
            r["players"].append(player_name)

        # flytta röster från gammalt namn till nytt
        if _prev_name and player_name:
            for sid, pv in r.get("votes", {}).items():
                if _prev_name in pv and player_name not in pv:
                    pv[player_name] = pv.pop(_prev_name)
                elif _prev_name in pv:
                    # om nya namnet redan hade en röst, ta bort den gamla för att undvika dubblett
                    pv.pop(_prev_name, None)

    update_room(room_code, apply_rename)

# --- Room bootstrap ---
room = get_room(room_code)
if not room:
    update_room(room_code, lambda r: r)
    room = get_room(room_code)

# Enkel ändringsindikator i session_state för att trigga omritning vid behov
st.session_state.setdefault("_room_version", 0)
st.session_state.setdefault("chat_expanded", False)

# --- Scale settings ---
scale_section = st.sidebar.expander("Skala")
with scale_section:
    current_mode = room.get("scale_mode", "points")
    default_label = "T-shirt" if current_mode == "tshirt" else "Poäng"
    if "scale_mode_radio" not in st.session_state:
        st.session_state["scale_mode_radio"] = default_label

    st.radio("Välj skala", ["T-shirt", "Poäng"], key="scale_mode_radio", horizontal=True)
    selected_label = st.session_state["scale_mode_radio"]
    selected_mode = "tshirt" if selected_label == "T-shirt" else "points"

    if selected_mode != current_mode:
        update_room(room_code, lambda r, m=selected_mode: r.update(scale_mode=m))
        room = get_room(room_code)
        if not room:
            update_room(room_code, lambda r: r)
            room = get_room(room_code)
        current_mode = room.get("scale_mode", selected_mode)

    if selected_mode == "tshirt":
        labels = room.get("scale_labels") or DEFAULT_TSHIRT[:]
        st.caption("T-shirt-läge visar endast valda etiketter – inga poäng.")
        # Optional: allow editing labels
        with st.popover("Redigera etiketter"):
            new_labels = []
            for i, lab in enumerate(labels):
                nl = st.text_input(f"Etikett {i+1}", value=lab, key=f"lab_{i}")
                if nl:
                    new_labels.append(nl)
            col_add, col_save = st.columns(2)
            if col_add.button("+ Lägg till etikett"):
                new_labels.append(f"E{i+2}")
            if col_save.button("Spara etiketter") and new_labels:
                update_room(room_code, lambda r: r.update(scale_labels=new_labels))
                room = get_room(room_code)
    else:
        # Custom points builder with dynamic components
        st.caption("Bygg eget poängsystem. Lägg till valfria kort.")
        if "custom_points" not in st.session_state:
            # seed from room scale
            scale_map = room.get("scale", DEFAULT_SCALE)
            st.session_state.custom_points = [
                {"label": k, "value": v} for k, v in scale_map.items()
            ]
        cp = st.session_state.custom_points
        col_add, col_reset = st.columns(2)
        if col_add.button("+ Lägg till poängkort"):
            cp.append({"label": f"{len(cp)+1}", "value": 0})
        if col_reset.button("Återställ till standard"):
            st.session_state.custom_points = [{"label": k, "value": v} for k, v in DEFAULT_SCALE.items()]
            cp = st.session_state.custom_points
        remove_indices = []
        for i, item in enumerate(cp):
            c1, c2, c3 = st.columns([2,2,1])
            item["label"] = c1.text_input("Etikett", value=str(item.get("label", "")), key=f"cp_label_{i}")
            item["value"] = c2.number_input("Värde", value=float(item.get("value", 0)), step=1.0, key=f"cp_value_{i}")
            if c3.button("✖", key=f"cp_del_{i}"):
                remove_indices.append(i)
        if remove_indices:
            for idx in sorted(remove_indices, reverse=True):
                cp.pop(idx)
        if st.button("Spara poängsystem"):
            new_scale = {str(it["label"]): float(it["value"]) for it in cp if str(it["label"]).strip() != ""}
            if new_scale:
                update_room(room_code, lambda r: r.update(scale=new_scale))
                room = get_room(room_code)



# Timer controls (facilitator)
with st.sidebar.expander("Timer"):
    duration = st.number_input("Sekunder", min_value=10, max_value=3600, value=90, step=5)
    col_t1, col_t2 = st.columns(2)
    if col_t1.button("Starta timer"):
        end_time = time.time() + duration
        update_room(room_code, lambda r: r.update(timer={"end": end_time, "duration": duration}))
    if col_t2.button("Stoppa timer"):
        update_room(room_code, lambda r: r.update(timer={"end": None, "duration": 0}))

# Reveal / reset controls
with st.sidebar.expander("Omröstning"):
    col_r1, col_r2 = st.columns(2)
    if col_r1.button("Reveal"):
        def set_reveal(r):
            sid = r.get("active_story_id")
            r["revealed_for"][sid] = True
        update_room(room_code, set_reveal)
    if col_r2.button("Reset"):
        def do_reset(r):
            sid = r.get("active_story_id")
            r["votes"][sid] = {}
            r["revealed_for"][sid] = False
        update_room(room_code, do_reset)

# --- Chat (sidebar, bottom) ---
with st.sidebar.expander("Chat", expanded=st.session_state.get("chat_expanded", False)):
    # Always live-refresh chat at a light interval
    st_autorefresh(interval=2000, key="chat_live_refresh")
    room = get_room(room_code)  # refresh to include any new messages
    # Hämta om rummet direkt efter att meddelande skickats
    if st.session_state.get("_clear_chat_input", False):
        room = get_room(room_code)
    # Hämta rumschat först
    room_chat = list(room.get("chat") or [])
    # Lokalt klient-historik (meddelanden skickade i denna session)
    local_key = f"chat_history_{room_code}"
    local_hist = list(st.session_state.get(local_key, []))
    # Snapshot från senast skickade
    snap = list(st.session_state.get("_last_sent_chat_snapshot") or [])

    # Combined key per room - beständig ackumulering i session_state
    combined_key = f"chat_combined_{room_code}"
    combined = st.session_state.get(combined_key, [])

    # Candidates: server chat, local history, snapshot
    candidates = room_chat + local_hist + snap
    # Sortera kandidater efter timestamp så order blir kronologisk
    candidates_sorted = sorted(candidates, key=lambda x: float(x.get("ts") or 0))

    # Bygg unik lista utan dubbletter och bevara tidigare combined där möjligt
    seen = {(m.get("ts"), m.get("name"), m.get("text")) for m in combined}
    new_combined = list(combined)
    for c in candidates_sorted:
        key = (c.get("ts"), c.get("name"), c.get("text"))
        if key not in seen:
            new_combined.append(c)
            seen.add(key)

    # Trim till senaste 500 för sessionen
    if len(new_combined) > 500:
        new_combined = new_combined[-500:]

    st.session_state[combined_key] = new_combined
    # Efter att ha ackumulerat i combined, rensa lokala temporära snapshots så
    # de inte läggs till igen vid nästa rerun.
    st.session_state[local_key] = []
    if "_last_sent_chat_snapshot" in st.session_state:
        st.session_state["_last_sent_chat_snapshot"] = None
    msgs = new_combined[-200:]
    me = (st.session_state.get("player_name") or "").strip()

    # Messages list
    chat_html = ["<div class='sidebar-chat-box'>"]
    for m in msgs:
        name = (m.get("name") or "Anonym").strip() or "Anonym"
        text = escape(str(m.get("text", "")))
        mine = (me != "" and name == me)
        align_cls = "right" if mine else "left"
        bubble_cls = "chat-bubble mine" if mine else "chat-bubble"
        chat_html.append(
            f"<div class='chat-msg chat-row {align_cls}'>"
            f"<div class='chat-name'>{escape(name)}</div>"
            f"<div class='{bubble_cls}'>{text}</div>"
            f"</div>"
        )
    chat_html.append("</div>")
    st.markdown("\n".join(chat_html), unsafe_allow_html=True)

    # Clear or set input/select on next run if flagged (safe updates before widgets)
    if st.session_state.pop("_clear_chat_input", False):
        st.session_state["chat_input"] = ""
    if "_set_chat_input" in st.session_state:
        st.session_state["chat_input"] = st.session_state.pop("_set_chat_input")
    if st.session_state.pop("_reset_chat_emoji", False):
        st.session_state["chat_emoji_select"] = "—"

    # Emoji selector outside form so it updates immediately
    def _chat_append_emoji():
        e = st.session_state.get("chat_emoji_select")
        if e and e != "—":
            st.session_state["_set_chat_input"] = (st.session_state.get("chat_input") or "") + e
            st.session_state["_reset_chat_emoji"] = True

    col_emoji, _sp = st.columns([1, 1])
    with col_emoji:
        emoji_options = ["—", "😀", "😅", "😂", "🙌", "👍", "🎉", "❤️", "🔥", "🙏", "🚀", "🤔"]
        st.selectbox("Emoji", options=emoji_options, index=0, key="chat_emoji_select", label_visibility="collapsed", on_change=_chat_append_emoji)

    # Debug checkbox to help troubleshoot chat updates
    chat_debug = st.checkbox("Visa chat-debug (rå data)", value=False, key="chat_debug")

    # Input and send (Enter submits the form)
    with st.form(key="chat_form", clear_on_submit=True):
        chat_text = st.text_input("Skriv ett meddelande", key="chat_input", placeholder="Skriv ett meddelande…")
        sent = st.form_submit_button("Skicka")
        if sent:
            msg = (chat_text or "").strip()
            if not me:
                st.warning("Ange ditt namn i sidopanelen innan du chattar.")
            elif msg:
                def append_msg(r):
                    lst = r.setdefault("chat", [])
                    lst.append({"name": me, "text": msg, "ts": time.time()})
                    # Trim to last 500 msgs to keep file small
                    if len(lst) > 500:
                        del lst[:-500]
                update_room(room_code, append_msg)
                # Expand chat so user sees the message
                st.session_state["chat_expanded"] = True
                # Fetch room immediately and save a persistent snapshot in session_state
                _r2 = get_room(room_code)
                st.session_state["_last_sent_chat_snapshot"] = _r2.get("chat", [])[-20:]
                # Also append the server's last message to a per-session local chat history
                # so we reuse the server timestamp and avoid duplicates.
                local_key = f"chat_history_{room_code}"
                last_msgs = _r2.get("chat", [])
                if last_msgs:
                    last_msg = last_msgs[-1]
                    hist = st.session_state.setdefault(local_key, [])
                    hist.append(last_msg)
                    st.session_state[local_key] = hist
                st.rerun()

    # If debug enabled, show raw chat data or the last sent snapshot so it doesn't blink
    if st.session_state.get("chat_debug"):
        st.markdown("**DEBUG: senaste meddelanden (rå data / snapshot)**")
        snap = st.session_state.get("_last_sent_chat_snapshot")
        if snap is not None:
            st.write(snap)
        else:
            st.write(room.get("chat", [])[-20:])
        # Extra debug: visa nycklar och duplicat-räkning i kombinerad lista
        combined_key = f"chat_combined_{room_code}"
        combined = st.session_state.get(combined_key, [])
        keys = [(m.get("ts"), m.get("name"), m.get("text")) for m in combined]
        from collections import Counter
        cnt = Counter(keys)
        dupes = {k: v for k, v in cnt.items() if v > 1}
        st.markdown("**DEBUG: combined keys (count) — dubbletter:**")
        st.write(dupes)

# --- Main content ---
# Ensure player registered (lägg alltid till namnet, även anonymt)
if player_name:
    def ensure_player(r):
        if player_name not in r["players"]:
            r["players"].append(player_name)
    update_room(room_code, ensure_player)

# Stories UI
stories = room.get("stories", [])
active_sid = room.get("active_story_id")

# Control which story expander is open
if "expanded_story_id" not in st.session_state:
    st.session_state["expanded_story_id"] = active_sid

# New story button (no title required)
if st.button("+ Ny story"):
    def add_story(r):
        sid = uuid.uuid4().hex[:8]
        r["stories"].append({"id": sid, "text": "", "created": time.time()})
        r["votes"].setdefault(sid, {})
        r["revealed_for"].setdefault(sid, False)
    update_room(room_code, add_story)
    room = get_room(room_code)
    stories = room.get("stories", [])
    active_sid = room.get("active_story_id")

# Om aktiv story är tom och det finns en icke-tom, välj en med text
stories = room.get("stories", [])
active_sid = room.get("active_story_id")
active_obj = next((s for s in stories if s["id"] == active_sid), None)
if active_obj and not (active_obj.get("text", "").strip()):
    non_empty = next((s for s in stories if s.get("text", "").strip()), None)
    if non_empty and non_empty["id"] != active_sid:
        update_room(room_code, lambda r: r.update(active_story_id=non_empty["id"]))
        room = get_room(room_code)
        stories = room.get("stories", [])
        active_sid = room.get("active_story_id")

# Stories display – expanderbara kort som sidomenyn
stories = room.get("stories", [])
active_sid = room.get("active_story_id")

# Visa alla stories som expanderbara kort
for idx, story in enumerate(stories):
    sid = story["id"]
    is_active = sid == active_sid
    raw_text = story.get("text", "")
    
    # Visa story som expanderbar sektion (som sidomenyn)
    story_title = (raw_text or "").strip() or f"User Story {idx+1}"
    
    # Insert a marker so CSS can add an inline badge in the header
    if is_active:
        st.markdown('<div class="active-expander-marker"></div>', unsafe_allow_html=True)

    with st.expander(story_title, expanded=(sid == st.session_state.get("expanded_story_id", active_sid))):
        col1, col2, col3 = st.columns([4, 1, 1])
        
        with col1:
            text_val = st.text_area(
                "Story text:",
                value=raw_text,
                key=f"story_text_{sid}",
                height=100,
                placeholder="Beskriv user story...",
            )
            # Save button saves the text and collapses the expander
            if st.button("Spara", key=f"save_{sid}", use_container_width=True):
                def save_text(r, sid=sid, text_val=text_val):
                    for obj in r["stories"]:
                        if obj["id"] == sid:
                            obj["text"] = text_val
                            break
                # Debugging: show current state before save in sidebar if enabled
                if st.sidebar.checkbox("Debug: story save", key=f"dbg_save_{sid}"):
                    st.sidebar.write("DEBUG before save_text:")
                    st.sidebar.write(get_room(room_code).get("stories", []))
                    st.sidebar.write("Saving text for:", sid)
                    st.sidebar.write(text_val)
                update_room(room_code, save_text)
                if st.sidebar.checkbox("Debug: story save", key=f"dbg_save_{sid}"):
                    st.sidebar.write("DEBUG after save_text:")
                    st.sidebar.write(get_room(room_code).get("stories", []))
                st.session_state["expanded_story_id"] = None
                st.rerun()
        
        with col2:
            if is_active:
                st.button("Vald ✓", key=f"selected_{sid}", use_container_width=True, disabled=True)
            else:
                if st.button("Välj för röstning", key=f"select_{sid}", use_container_width=True):
                    update_room(room_code, lambda r, sid=sid: r.update(active_story_id=sid))
                    st.session_state["active_story_id"] = sid
                    st.session_state["expanded_story_id"] = sid
                    st.rerun()
        
        with col3:
            if st.button("✖ Ta bort", key=f"del_{sid}", use_container_width=True):
                def delete_story(r, sid=sid):
                    r["stories"] = [o for o in r["stories"] if o["id"] != sid]
                    r.get("votes", {}).pop(sid, None)
                    r.get("revealed_for", {}).pop(sid, None)
                    if r.get("active_story_id") == sid:
                        if r["stories"]:
                            r["active_story_id"] = r["stories"][0]["id"]
                        else:
                            new_sid = uuid.uuid4().hex[:8]
                            r["stories"].append({"id": new_sid, "text": "", "created": time.time()})
                            r["votes"].setdefault(new_sid, {})
                            r["revealed_for"].setdefault(new_sid, False)
                            r["active_story_id"] = new_sid
                update_room(room_code, delete_story)
                st.rerun()
        
        # Spara endast via "Spara"-knappen för tydligare UX
    
    # No closing needed; marker styles the immediate next expander
# Debug: visa stories-data om flagga är satt
if st.sidebar.checkbox("Visa story-debug (rå data)", value=False, key="story_debug"):
    st.sidebar.markdown("**DEBUG: stories för rummet**")
    st.sidebar.write(get_room(room_code).get("stories", []))
    st.sidebar.markdown("**DEBUG: session keys för story-textarea**")
    keys = {k: v for k, v in st.session_state.items() if k.startswith("story_text_")}
    st.sidebar.write(keys)
# No manual refresh needed; auto-refresh is enabled.
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)
st.divider()
# Timer display
room = get_room(room_code)  # refresh
if not room:
    update_room(room_code, lambda r: r)
    room = get_room(room_code)
active_sid = room.get("active_story_id")
end = room["timer"]["end"]
if end:
    remaining = int(end - time.time())
    if remaining <= 0:
        remaining = 0
        if not room["revealed_for"].get(active_sid, False):
            def auto_reveal(r):
                sid = r.get("active_story_id")
                r["revealed_for"][sid] = True
            update_room(room_code, auto_reveal)
        st.success("Tid slut!")
    # uppdatera bara när timer är aktiv så nedräkningen syns
    st_autorefresh(interval=1000, key=f"timer_refresh_{room_code}")
    st.markdown(f"<span class='timer'>⏱️ {remaining}s</span>", unsafe_allow_html=True)

# Voting interface

scale_mode = room.get("scale_mode", "points")
current_scale = room.get("scale", DEFAULT_SCALE)
current_labels = room.get("scale_labels", DEFAULT_TSHIRT)
vote_placeholder = st.empty()
player_vote = None
votes_for_active = room.get("votes", {}).get(active_sid, {})
if player_name:
    player_vote = votes_for_active.get(player_name)
    if scale_mode == "tshirt":
        card_cols = st.columns(len(current_labels))
        for idx, label in enumerate(current_labels):
            with card_cols[idx]:
                vote_btn = st.button(label, key=f"vote_t_{label}")
                if vote_btn:
                    def set_vote(r):
                        sid = r.get("active_story_id")
                        r["votes"].setdefault(sid, {})
                        r["votes"][sid][player_name] = str(label)
                    update_room(room_code, set_vote)
                    room = get_room(room_code)
                    votes_for_active = room.get("votes", {}).get(active_sid, {})
    else:
        # points mode
        items = list(current_scale.items())
        card_cols = st.columns(len(items))
        for idx, (label, val) in enumerate(items):
            with card_cols[idx]:
                vote_btn = st.button(label, key=f"vote_p_{label}")
                if vote_btn:
                    def set_vote(r):
                        sid = r.get("active_story_id")
                        r["votes"].setdefault(sid, {})
                        r["votes"][sid][player_name] = float(val)
                    update_room(room_code, set_vote)
                    room = get_room(room_code)
                    votes_for_active = room.get("votes", {}).get(active_sid, {})
else:
    st.info("Ange namn i sidopanelen för att rösta.")
    
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)
st.divider()

room = get_room(room_code)
if not room:
    update_room(room_code, lambda r: r)
    room = get_room(room_code)
active_sid = room.get("active_story_id")
all_votes = room.get("votes", {}).get(active_sid, {})
revealed = room.get("revealed_for", {}).get(active_sid, False)


card_container = st.container()
with card_container:
    players_list = sorted(room.get("players", []))
    # Clean out expired pings (older than 3s)
    def _clean_pings(r):
        now = time.time()
        r["pings"] = {k: v for k, v in (r.get("pings", {}) or {}).items() if now - float(v) < 1}
    update_room(room_code, _clean_pings)
    room = get_room(room_code)
    pings = room.get("pings", {})

    # Render cards in a grid with 9 columns per row
    if players_list:
        cols_per_row = 9
        num_rows = (len(players_list) + cols_per_row - 1) // cols_per_row
        for i in range(num_rows):
            row_players = players_list[i*cols_per_row:(i+1)*cols_per_row]
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if j < len(row_players):
                    p = row_players[j]
                    has_vote = p in all_votes
                    val = all_votes.get(p, "?")
                    is_pinged = False
                    try:
                        ts = float(pings.get(p, 0))
                        is_pinged = (time.time() - ts) < 1
                    except Exception:
                        is_pinged = False
                    base_cls = "card flip" if revealed and has_vote else "card"
                    card_classes = (base_cls + (" pinged" if is_pinged else "")).strip()
                    display_name = escape(str(p))
                    name_class = "name long" if len(str(p)) > 12 else "name"
                    front_content = f"<span class='{name_class}'>{display_name}</span>"
                    back_content = val if revealed and has_vote else "?"
                    card_html = (
                        f"<div class='{card_classes}'><div class='card-inner'>"
                        f"<div class='card-face card-front'>{front_content}</div>"
                        f"<div class='card-face card-back'>{back_content}</div>"
                        f"</div></div>"
                    )
                    with cols[j]:
                        st.markdown(card_html, unsafe_allow_html=True)
                        if st.button("🔔", key=f"ping_{p}", help=f"Pingga {p}", use_container_width=False):
                            def _set_ping(r, who=p):
                                r.setdefault("pings", {})[who] = time.time()
                            update_room(room_code, _set_ping)
                            st.rerun()
                else:
                    with cols[j]:
                        st.markdown("", unsafe_allow_html=True)

# Stats once revealed
if revealed and all_votes:
    values = list(all_votes.values())
    consensus = len(set(values)) == 1
    if scale_mode == "points":
        try:
            num_vals = [float(v) for v in values]
            mean_val = statistics.mean(num_vals)
            try:
                stdev_val = statistics.pstdev(num_vals)
            except statistics.StatisticsError:
                stdev_val = 0
            cols_stats = st.columns(3)
            cols_stats[0].metric("Medel", f"{mean_val:.2f}")
            cols_stats[1].metric("Stdavvikelse", f"{stdev_val:.2f}")
            cols_stats[2].metric("Röster", f"{len(values)}")
        except Exception:
            st.write("Kan inte beräkna statistik för dessa värden.")
    else:
        # Label frequency for T-shirt mode
        from collections import Counter
        counts = Counter([str(v) for v in values])
        st.write("Frekvens:")
        for lab, cnt in counts.items():
            st.write(f"- {lab}: {cnt}")
    if consensus:
        st.markdown("<span class='consensus'>✅ Konsensus uppnådd!</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='warning'>⚠️ Ingen konsensus ännu</span>", unsafe_allow_html=True)

_tm = {s["id"]: s.get("text", "") for s in room.get("stories", [])}
st.caption(f"Rum: {room_code} • Story: {_tm.get(active_sid, '')} • Spelare: {len(room.get('players', []))} • Röster: {len(all_votes)}")
