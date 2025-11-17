import json, time, threading, uuid
from pathlib import Path
import statistics
import streamlit as st

ROOMS_LOCK = threading.Lock()
ROOMS_FILE = Path("rooms_state.json")

DEFAULT_SCALE = {
    "XS": 1,
    "S": 2,
    "M": 3,
    "L": 5,
    "XL": 8,
}

def load_rooms():
    if not ROOMS_FILE.exists():
        return {}
    try:
        with ROOMS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_rooms(rooms):
    with ROOMS_FILE.open("w", encoding="utf-8") as f:
        json.dump(rooms, f, ensure_ascii=False, indent=2)

def init_room(rooms, room_code):
    if room_code not in rooms:
        rooms[room_code] = {
            "created": time.time(),
            "story": "",
            "scale": DEFAULT_SCALE.copy(),
            "votes": {},  # player_name -> value
            "revealed": False,
            "timer": {
                "end": None,
                "duration": 0,
            },
            "players": set(),
            "last_update": time.time(),
        }

def update_room(room_code, mutate_fn):
    with ROOMS_LOCK:
        rooms = load_rooms()
        init_room(rooms, room_code)
        mutate_fn(rooms[room_code])
        rooms[room_code]["last_update"] = time.time()
        # Convert set to list for JSON
        rooms[room_code]["players"] = list(rooms[room_code]["players"])
        save_rooms(rooms)

def get_room(room_code):
    rooms = load_rooms()
    return rooms.get(room_code)

# --- UI Helpers ---
@st.cache_data(ttl=5)
def cached_room(room_code, _ts):  # _ts to bust cache
    return get_room(room_code)

CSS = """
<style>
body { overflow-x: hidden; }
.card-grid { display: flex; flex-wrap: wrap; gap: 1rem; }
.card { position: relative; width: 100px; height: 140px; perspective: 800px; cursor: pointer; }
.card-inner { position: absolute; width: 100%; height: 100%; transition: transform 0.8s; transform-style: preserve-3d; }
.card.flip .card-inner { transform: rotateY(180deg); }
.card-face { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 10px; display:flex; align-items:center; justify-content:center; font-weight:600; font-size:1.4rem; letter-spacing:1px; }
.card-front { background: linear-gradient(135deg, #202431 0%, #2b2f3b 60%, #343948 100%); box-shadow:0 0 8px rgba(108,93,211,0.5); }
.card-back { background: linear-gradient(135deg, #6C5DD3, #8E7BFF); transform: rotateY(180deg); box-shadow:0 0 12px rgba(120,80,255,0.6); }
.card:hover .card-front { animation: rgbPulse 2s linear infinite; }
@keyframes rgbPulse { 0% { box-shadow:0 0 8px #ff004c; } 33% { box-shadow:0 0 8px #00e1ff; } 66% { box-shadow:0 0 8px #7dff00; } 100% { box-shadow:0 0 8px #ff004c; } }
.reveal-badge { background:#6C5DD3; padding:0.4rem 0.8rem; border-radius:6px; font-size:0.8rem; margin-left:0.5rem; }
.consensus { color:#7dff00; font-weight:600; }
.warning { color:#ffcc00; }
.timer { font-size:1.2rem; font-weight:600; }
</style>
"""

st.set_page_config(page_title="Scrum Poker", page_icon="🃏", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

st.title("🃏 Scrum Poker")
st.caption("Mörkt tema • Flip-kort • Live-röstning")

# --- Sidebar setup ---
st.sidebar.header("Inställningar")
room_code = st.sidebar.text_input("Rumskod", value=st.session_state.get("room_code", "TEAM1"))
if room_code != st.session_state.get("room_code"):
    st.session_state["room_code"] = room_code
player_name = st.sidebar.text_input("Ditt namn", value=st.session_state.get("player_name", ""))
if player_name != st.session_state.get("player_name"):
    st.session_state["player_name"] = player_name

scale_cols = st.sidebar.columns(2)
custom_scale_expander = st.sidebar.expander("Anpassa skala")
with custom_scale_expander:
    st.write("Standardvärden kan ändras här.")
    new_scale = {}
    for label, default in DEFAULT_SCALE.items():
        new_scale[label] = st.number_input(label, value=default, step=1, min_value=0)
    if st.button("Spara skala"):
        update_room(room_code, lambda r: r.update(scale=new_scale))

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
        update_room(room_code, lambda r: r.update(revealed=True))
    if col_r2.button("Reset"):
        def do_reset(r):
            r["votes"] = {}
            r["revealed"] = False
        update_room(room_code, do_reset)

# --- Main content ---
room = get_room(room_code)
if not room:
    # ensure room exists
    update_room(room_code, lambda r: r)
    room = get_room(room_code)

# Ensure player registered
if player_name:
    update_room(room_code, lambda r: r["players"].append(player_name) if player_name not in r["players"] else None)

# Story input (only updates on change)
story_text = st.text_area("Användarberättelse", value=room.get("story", ""), placeholder="Som <roll> vill jag <mål> så att <nytta>...")
if story_text != room.get("story"):
    update_room(room_code, lambda r: r.update(story=story_text))
    room = get_room(room_code)

# Refresh button
st.button("🔄 Uppdatera", type="secondary")

# Timer display
room = get_room(room_code)  # refresh
end = room["timer"]["end"]
if end:
    remaining = int(end - time.time())
    if remaining <= 0:
        remaining = 0
        if not room["revealed"]:
            update_room(room_code, lambda r: r.update(revealed=True))
        st.success("⏱️ Tid slut - reveal!")
    st.markdown(f"<div class='timer'>⏱️ {remaining}s kvar</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='timer'>⏱️ Ingen timer aktiv</div>", unsafe_allow_html=True)

# Voting interface
st.subheader("Rösta")
current_scale = room.get("scale", DEFAULT_SCALE)
vote_placeholder = st.empty()
player_vote = None
if player_name:
    player_vote = room["votes"].get(player_name)
    card_cols = st.columns(len(current_scale))
    idx = 0
    for label, val in current_scale.items():
        with card_cols[idx]:
            vote_btn = st.button(label, key=f"vote_{label}")
            if vote_btn:
                def set_vote(r):
                    r["votes"][player_name] = val
                update_room(room_code, set_vote)
                room = get_room(room_code)
        idx += 1
else:
    st.info("Ange namn i sidopanelen för att rösta.")

room = get_room(room_code)
all_votes = room["votes"]
revealed = room["revealed"]

st.subheader("Kort")
card_container = st.container()
with card_container:
    card_grid_html = ["<div class='card-grid'>"]
    for p in sorted(room.get("players", [])):
        has_vote = p in all_votes
        val = all_votes.get(p, "?")
        card_classes = "card flip" if revealed and has_vote else "card"
        front_content = p if not revealed else p
        back_content = val if revealed and has_vote else "?"
        card_html = f"<div class='{card_classes}'><div class='card-inner'>" \
                    f"<div class='card-face card-front'>{front_content}</div>" \
                    f"<div class='card-face card-back'>{back_content}</div>" \
                    f"</div></div>"
        card_grid_html.append(card_html)
    card_grid_html.append("</div>")
    st.markdown("".join(card_grid_html), unsafe_allow_html=True)

# Stats once revealed
if revealed and all_votes:
    values = list(all_votes.values())
    mean_val = statistics.mean(values)
    try:
        stdev_val = statistics.pstdev(values)
    except statistics.StatisticsError:
        stdev_val = 0
    consensus = len(set(values)) == 1
    cols_stats = st.columns(3)
    cols_stats[0].metric("Medel", f"{mean_val:.2f}")
    cols_stats[1].metric("Stdavvikelse", f"{stdev_val:.2f}")
    cols_stats[2].metric("Röster", f"{len(values)}")
    if consensus:
        st.markdown("<span class='consensus'>✅ Konsensus uppnådd!</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='warning'>⚠️ Ingen konsensus ännu</span>", unsafe_allow_html=True)

st.caption(f"Rum: {room_code} • Spelare: {len(room.get('players', []))} • Röster: {len(all_votes)}")
