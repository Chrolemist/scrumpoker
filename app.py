import json, time, threading, uuid
from pathlib import Path
import statistics
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOMS_LOCK = threading.Lock()
ROOMS_FILE = Path("rooms_state.json")

DEFAULT_TSHIRT = ["XS", "S", "M", "L", "XL"]
DEFAULT_SCALE = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}

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
    with ROOMS_LOCK:
        rooms = load_rooms()
        init_room(rooms, room_code)
        # migrate before mutation
        if migrate_room(rooms[room_code]):
            pass
        mutate_fn(rooms[room_code])
        # bumpa en enkel versionsräknare vid varje ändring
        rooms[room_code]["last_update"] = time.time()
        # Ensure players is a unique list
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
/* Stories UI */
@keyframes rgbBorder { 0% { box-shadow:0 0 0 2px #ff004c; } 33% { box-shadow:0 0 0 2px #00e1ff; } 66% { box-shadow:0 0 0 2px #7dff00; } 100% { box-shadow:0 0 0 2px #ff004c; } }
.story-anchor { display:none; }
div[data-testid='stVerticalBlock']:has(> .story-anchor) {
    background:#1B1F29;
    border:2px solid #2b2f3b;
    border-radius:14px;
    padding:0.7rem 0.9rem;
    margin-bottom:0.75rem;
}
div[data-testid='stVerticalBlock']:has(> .story-anchor.active) {
    border-color:transparent;
    animation: rgbBorder 2s linear infinite;
}
div[data-testid='stVerticalBlock']:has(> .story-anchor.empty) textarea {
    opacity:0.65;
    font-style:italic;
}
div[data-testid='stVerticalBlock']:has(> .story-anchor) textarea {
    background:#11131a;
    border:1px solid #2b2f3b;
    border-radius:10px;
    color:#f0f0f4;
    min-height:100px;
}
div[data-testid='stVerticalBlock']:has(> .story-anchor) button {
    width:100%;
    height:40px;
}
</style>
"""

st.set_page_config(page_title="Scrum Poker", page_icon="🃏", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

st.title("Scrum Poker")

# --- Sidebar setup ---
st.sidebar.header("Inställningar")
room_code = st.sidebar.text_input("Rumskod", value=st.session_state.get("room_code", "TEAM1"))
if room_code != st.session_state.get("room_code"):
    st.session_state["room_code"] = room_code
_prev_name = st.session_state.get("player_name", "")
player_name = st.sidebar.text_input("Ditt namn", value=_prev_name)
if player_name != _prev_name:
    # update local state immediately
    st.session_state["player_name"] = player_name
    # propagate rename in room (autosave)
    def apply_rename(r):
        # players list
        if _prev_name and _prev_name in r["players"]:
            r["players"] = [player_name if n == _prev_name else n for n in r["players"]]
        if player_name and player_name not in r["players"]:
            r["players"].append(player_name)
        # votes across all stories
        for sid, pv in r.get("votes", {}).items():
            if _prev_name and _prev_name in pv:
                val = pv.pop(_prev_name)
                pv[player_name] = val
    update_room(room_code, apply_rename)

# --- Room bootstrap ---
room = get_room(room_code)
if not room:
    update_room(room_code, lambda r: r)
    room = get_room(room_code)

# Enkel ändringsindikator i session_state för att trigga omritning vid behov
st.session_state.setdefault("_room_version", 0)

# --- Scale settings ---
scale_section = st.sidebar.expander("Skala")
with scale_section:
    current_mode = room.get("scale_mode", "points")
    mode = st.radio("Välj skala", ["T-shirt", "Poäng"], index=0 if current_mode == "tshirt" else 1, horizontal=True)
    if (mode == "T-shirt" and current_mode != "tshirt") or (mode == "Poäng" and current_mode != "points"):
        update_room(room_code, lambda r: r.update(scale_mode=("tshirt" if mode == "T-shirt" else "points")))
        room = get_room(room_code)

    if mode == "T-shirt":
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

# --- Main content ---
# Ensure player registered
if player_name:
    def ensure_player(r):
        if player_name not in r["players"]:
            r["players"].append(player_name)
    update_room(room_code, ensure_player)

# Stories UI
st.subheader("User stories")
stories = room.get("stories", [])
active_sid = room.get("active_story_id")

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

# Stories display – cards med RGB highlight och inline-editing
stories = room.get("stories", [])
active_sid = room.get("active_story_id")
for idx, s in enumerate(stories):
    sid = s["id"]
    is_active = sid == active_sid
    raw_text = s.get("text", "")
    story_container = st.container()
    anchor_classes = ["story-anchor"]
    if is_active:
        anchor_classes.append("active")
    if not raw_text.strip():
        anchor_classes.append("empty")
    story_container.markdown(f"<span class='{' '.join(anchor_classes)}'></span>", unsafe_allow_html=True)

    with story_container:
        cols = st.columns([7,1,1,1,1])

        # Inline text area editing
        text_val = cols[0].text_area(
            "",
            value=raw_text,
            key=f"story_text_{sid}",
            label_visibility="collapsed",
            height=120,
            placeholder="Beskriv user story...",
        )

        if cols[1].button("Välj", key=f"select_{sid}"):
            # uppdatera aktiv story både i rummet och lokalt så RGB-rammen syns direkt
            update_room(room_code, lambda r, sid=sid: r.update(active_story_id=sid))
            st.session_state["active_story_id"] = sid
            room = get_room(room_code)
            active_sid = room.get("active_story_id")

        # ta bort pilarna, behåll bara delete-knappen längst till höger
        if cols[4].button("✖", key=f"del_{sid}"):
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
            room = get_room(room_code)
            stories = room.get("stories", [])
            active_sid = room.get("active_story_id")

    if text_val != raw_text:
        def update_text(r, sid=sid, text_val=text_val):
            for obj in r["stories"]:
                if obj["id"] == sid:
                    obj["text"] = text_val
                    break
            r["active_story_id"] = sid
        update_room(room_code, update_text)
        # uppdatera lokal active_story_id direkt för tydlig RGB-markering
        st.session_state["active_story_id"] = sid
        room = get_room(room_code)
        stories = room.get("stories", [])
        active_sid = room.get("active_story_id")

# No manual refresh needed; auto-refresh is enabled.

# Timer display
room = get_room(room_code)  # refresh
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
        st.success("⏱️ Tid slut - reveal!")
    # uppdatera bara när timer är aktiv så nedräkningen syns
    st_autorefresh(interval=1000, key=f"timer_refresh_{room_code}")
    st.markdown(f"<div class='timer'>⏱️ {remaining}s kvar</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='timer'>⏱️ Ingen timer aktiv</div>", unsafe_allow_html=True)

# Voting interface
st.subheader("Rösta")
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

room = get_room(room_code)
active_sid = room.get("active_story_id")
all_votes = room.get("votes", {}).get(active_sid, {})
revealed = room.get("revealed_for", {}).get(active_sid, False)

st.subheader("Kort")
card_container = st.container()
with card_container:
    card_grid_html = ["<div class='card-grid'>"]
    for p in sorted(room.get("players", [])):
        has_vote = p in all_votes
        val = all_votes.get(p, "?")
        card_classes = "card flip" if revealed and has_vote else "card"
        front_content = p
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
