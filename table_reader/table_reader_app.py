import importlib
import subprocess
import sys
from pathlib import Path

import streamlit as st

# Add table_reader directory to path so reader_utils can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import play_engine

play_engine = importlib.reload(play_engine)
from reader_utils import (
    assign_table_positions,
    build_preflop_hand_rank,
    capture_screen,
    extract_player_sections,
    process_positions_parallel,
)

import json
import time

_TRACKER_STATE_PATH = Path(__file__).resolve().parent / "last_table_state.json"

# Initialize tracker state in session if not present
if "tracker_state" not in st.session_state:
    try:
        with open(_TRACKER_STATE_PATH, "r") as _f:
            st.session_state["tracker_state"] = json.load(_f)
    except Exception:
        st.session_state["tracker_state"] = {}

DCIM_DIR = Path(__file__).resolve().parent / "DCIM"
PLAYERS_DIR = DCIM_DIR / "players"
SCREEN_IMAGE = DCIM_DIR / "screen.png"
MAIN_RIGHT_IMAGE = DCIM_DIR / "main_right.png"

_DB_PATH = Path(__file__).resolve().parent.parent / "players_database.json"
try:
    with open(_DB_PATH, "r") as _f:
        PLAYERS_DB: dict = json.load(_f)
except Exception:
    PLAYERS_DB = {}

_STATS_PATH = Path(__file__).resolve().parent.parent / "players_hand_stats.json"
try:
    with open(_STATS_PATH, "r") as _f:
        PLAYER_STATS = json.load(_f)
except Exception:
    PLAYER_STATS = {}

ALL_POSITIONS = [
    "top_left", "top_middle", "top_right",
    "bottom_left", "bottom_middle", "bottom_right",
]

st.set_page_config(page_title="Table Reader", layout="wide")
st.title("Poker Table Reader")

if st.button("Analyze Current Screen", use_container_width=True):
    with st.spinner("Capturing screenshot and processing..."):
        # capture_screen(SCREEN_IMAGE, display_index=2)  # Capture external monitor (disabled temporarily)
        extract_player_sections(DCIM_DIR)
        results = process_positions_parallel(PLAYERS_DIR, ALL_POSITIONS, max_workers=6)

    # Use tracker state from session
    _tracker_state = st.session_state["tracker_state"]

    # Auto-tracker logic: compare and update only if action changed
    changed = False
    for pos, pdata in results.items():
        name = (pdata.get("name") or "").strip()
        action = (pdata.get("action") or "").strip()
        prev_action = (_tracker_state.get(pos, {}).get("action") or "").strip()
        if name and action and action != prev_action:
            changed = True
    if changed:
        st.session_state["tracker_state"] = results
        _tracker_state = results

    # Update player stats
    for pos, data in results.items():
        name = (data.get("name") or "").strip()
        action = (data.get("action") or "").strip().upper()
        if not name:
            continue
        stats = PLAYER_STATS.setdefault(name, {"hands_seen": 0, "not_folded": 0, "vpip": 0})
        stats["hands_seen"] += 1
        if action and action != "FOLD":
            stats["not_folded"] += 1
        if action in {"RAISE", "CALL"}:
            stats["vpip"] += 1
    with open(_STATS_PATH, "w") as _f:
        json.dump(PLAYER_STATS, _f, indent=2)

    st.session_state["position_warning"] = assign_table_positions(results)
    st.session_state["results"] = results


if "results" in st.session_state:
    results = st.session_state["results"]

    # ── Hero hand confirmation ────────────────────────────────────────────
    st.subheader("🃏 Your Hand")

    hero = results.get("bottom_middle", {})
    detected_left_rank  = hero.get("hero_card_left", "")
    detected_left_color  = hero.get("hero_card_left_color", "")
    detected_right_rank = hero.get("hero_card_right", "")
    detected_right_color = hero.get("hero_card_right_color", "")
    detected_hand = hero.get("hand_rank", "")

    RANKS  = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
    COLORS = ["red", "green", "blue", "black"]

    def _safe_index(lst, val, fallback=0):
        try:
            return lst.index(val)
        except ValueError:
            return fallback

    # Seed session state with detected values so dropdowns reflect the detection.
    # Always update when a fresh capture produces new results.
    last_detected = st.session_state.get("_last_detected_hand", "")
    if detected_hand != last_detected:
        st.session_state["hero_left_rank"]  = detected_left_rank  or RANKS[0]
        st.session_state["hero_left_color"] = detected_left_color or COLORS[0]
        st.session_state["hero_right_rank"] = detected_right_rank or RANKS[0]
        st.session_state["hero_right_color"]= detected_right_color or COLORS[0]
        st.session_state["confirmed_hand"] = ""
        st.session_state["confirmed_hand_parts"] = {}
        st.session_state["_last_detected_hand"] = detected_hand

    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
    with col1:
        left_rank = st.selectbox(
            "Left rank",
            options=RANKS,
            index=_safe_index(RANKS, st.session_state["hero_left_rank"]),
            key="hero_left_rank",
        )
    with col2:
        left_color = st.selectbox(
            "Left color",
            options=COLORS,
            index=_safe_index(COLORS, st.session_state["hero_left_color"]),
            key="hero_left_color",
        )
    with col3:
        right_rank = st.selectbox(
            "Right rank",
            options=RANKS,
            index=_safe_index(RANKS, st.session_state["hero_right_rank"]),
            key="hero_right_rank",
        )
    with col4:
        right_color = st.selectbox(
            "Right color",
            options=COLORS,
            index=_safe_index(COLORS, st.session_state["hero_right_color"]),
            key="hero_right_color",
        )
    with col5:
        st.write("&nbsp;", unsafe_allow_html=True)  # vertical spacer to align button
        confirm_clicked = st.button("✅ Confirm Hand", use_container_width=True)

    effective_hand = build_preflop_hand_rank(left_rank, right_rank, left_color, right_color)

    if confirm_clicked:
        st.session_state["confirmed_hand"] = effective_hand
        st.session_state["confirmed_hand_parts"] = {
            "left_rank": left_rank, "left_color": left_color,
            "right_rank": right_rank, "right_color": right_color,
        }
        st.rerun()

    if st.session_state.get("confirmed_hand"):
        st.success(f"Confirmed hand: **{st.session_state['confirmed_hand']}**")

    hero_position = str(hero.get("table_position", "")).upper()
    prior_actions = play_engine.infer_prior_actions_from_results(results, hero_seat="bottom_middle")
    prior_action_labels = [
        f"{entry['position']} {entry['action']}"
        for entry in prior_actions
        if entry.get("action") != "Fold"
    ]
    displayed_hand = st.session_state.get("confirmed_hand") or effective_hand

    st.divider()
    st.subheader("Plays")

    context_cols = st.columns([1, 2])
    with context_cols[0]:
        st.caption(f"Hero position: {hero_position or '—'}")
        st.caption(f"Hand: {displayed_hand or '—'}")
    with context_cols[1]:
        if prior_action_labels:
            st.caption(f"Prior actions: {' -> '.join(prior_action_labels)}")
        else:
            st.caption("Prior actions: unopened pot")

    evaluated_plays = play_engine.evaluate_plays_for_spot(
        displayed_hand or None,
        hero_position,
        [entry["action"] for entry in prior_actions],
    )

    play_idx = 0
    for _ in range(3):
        cols = st.columns(4, gap="small")
        for col in cols:
            if play_idx >= len(evaluated_plays):
                continue

            item = evaluated_plays[play_idx]
            play_idx += 1

            play = item["play"]
            possible = item["possible"]
            blocked_by_context = item["blocked_by_context"]
            reason = item["reason"]

            with col:
                other_names = play.get("other_names", [])
                if other_names:
                    title = f"{play['name']} ({', '.join(other_names)})"
                else:
                    title = play["name"]

                color_marker = play_engine.status_color_marker(possible, blocked_by_context)
                with st.expander(f"{color_marker} {title}", expanded=False):
                    st.write(play["description"])
                    st.caption(reason)

    st.divider()
    st.subheader("Results")

    if st.session_state.get("position_warning"):
        st.warning(st.session_state["position_warning"])

    def classify_player(vpip, pfr):
        gap = vpip - pfr
        if vpip >= 35 and pfr >= 25 and gap <= 15:
            return "Maniac"
        if vpip >= 25 and pfr >= 18 and gap <= 10:
            return "LAG"
        if 17 <= vpip <= 24 and 13 <= pfr <= 20 and gap <= 7:
            return "TAG"
        if vpip <= 16 and pfr <= 12:
            return "NIT"
        if vpip <= 20 and pfr <= 8 and gap >= 8:
            return "Tight Passive"
        if vpip >= 30 and pfr <= 12 and gap >= 12:
            return "Loose Passive (Calling Station)"
        if vpip >= 25 and pfr <= 15 and gap >= 10:
            return "Loose Passive (Fold a lot)"
        return "Unclassified / Mixed"

    def player_card(position: str) -> None:
        data = results.get(position, {})
        name = data.get('name', '') or ''
        db_entry = PLAYERS_DB.get(name.strip()) if name.strip() else None
        in_db = db_entry is not None
        stats = PLAYER_STATS.get(name.strip()) if name.strip() else None

        st.markdown(f"**{position.replace('_', ' ').title()}**")
        if data.get("is_dealer", False):
            st.caption("🟠 Dealer")

        table_pos = data.get('table_position', '') or '—'
        pot_size  = data.get('pot_size', '') or '—'
        action    = data.get('action', '') or '—'

        if in_db:
            vpip         = db_entry.get("VPIP", 0) or 0
            pfr          = db_entry.get("PFR", 0) or 0
            gap          = vpip - pfr
            three_bet    = db_entry.get("3-BET", "—")
            fold_to_3bet = db_entry.get("Fold to 3-Bet", "—")
            player_type  = classify_player(vpip, pfr)
            st.write(f"📍 `{table_pos}` &nbsp;&nbsp;&nbsp; VPIP: **{vpip}** | PFR: **{pfr}**", unsafe_allow_html=True)
            st.write(f"🧑 `{name or '—'}` &nbsp;&nbsp;&nbsp; GAP: **{gap}**", unsafe_allow_html=True)
            st.write(f"💰 `{pot_size}` &nbsp;&nbsp;&nbsp; 3-Bet: **{three_bet}** | Fold to 3-Bet: **{fold_to_3bet}**", unsafe_allow_html=True)
            st.write(f"🃏 `{action}` &nbsp;&nbsp;&nbsp; Type: **{player_type}**", unsafe_allow_html=True)
        else:
            st.write(f"📍 `{table_pos}`")
            st.write(f"🧑 `{name or '—'}`" + (" &nbsp;&nbsp;&nbsp; ❌ HUD: False" if name.strip() else ""), unsafe_allow_html=True)
            st.write(f"💰 `{pot_size}`")
            st.write(f"🃏 `{action}`")

        if stats:
            st.caption(f"Hands: {stats['hands_seen']} | Not Folded: {stats['not_folded']} | VPIP: {stats['vpip']}")

    # Row 1: top_middle in center
    r1 = st.columns(3)
    with r1[1]:
        player_card("top_middle")

    # Row 2: top_left and top_right on sides
    r2 = st.columns(3)
    with r2[0]:
        player_card("top_left")
    with r2[2]:
        player_card("top_right")

    # Row 3: bottom_left and bottom_right on sides
    r3 = st.columns(3)
    with r3[0]:
        player_card("bottom_left")
    with r3[2]:
        player_card("bottom_right")

    # Row 4: bottom_middle in center
    r4 = st.columns(3)
    with r4[1]:
        player_card("bottom_middle")

# ── Add New Player to Archive ─────────────────────────────────────────────────

PLAYER_FIELDS_DB = ["VPIP", "PFR", "3-BET", "Fold to 3-Bet", "C-BET", "Fold to C-Bet", "Steal", "Check/Raise"]

st.divider()
st.subheader("Add Player to Archive")

draft_name_key = "new_player_name"
if draft_name_key not in st.session_state:
    st.session_state[draft_name_key] = ""
for field in PLAYER_FIELDS_DB:
    k = f"new_player_{field}"
    if k not in st.session_state:
        st.session_state[k] = ""

if st.session_state.get("_reset_new_player", False):
    st.session_state[draft_name_key] = ""
    for field in PLAYER_FIELDS_DB:
        st.session_state[f"new_player_{field}"] = ""
    st.session_state["_reset_new_player"] = False

name_col, _ = st.columns([3, 5])
with name_col:
    st.text_input("Player Name", key=draft_name_key)

stat_cols = st.columns(len(PLAYER_FIELDS_DB))
for idx, field in enumerate(PLAYER_FIELDS_DB):
    with stat_cols[idx]:
        st.text_input(field, key=f"new_player_{field}")

if st.button("Save to Archive", use_container_width=True):
    new_name = st.session_state[draft_name_key].strip()
    if not new_name:
        st.warning("Player name is required.")
    else:
        entry = {}
        for field in PLAYER_FIELDS_DB:
            raw = st.session_state[f"new_player_{field}"].strip()
            try:
                entry[field] = float(raw) if "." in raw else int(raw)
            except ValueError:
                entry[field] = raw
        PLAYERS_DB[new_name] = entry
        with open(_DB_PATH, "w") as _out:
            json.dump(PLAYERS_DB, _out, indent=2)
        st.success(f"'{new_name}' saved to archive.")
        st.session_state["_reset_new_player"] = True
        st.rerun()

# Show tracker state at the top
if st.session_state.get("tracker_state"):
    st.divider()
    st.subheader("[DEBUG] Last Tracked Table State")
    for pos, pdata in st.session_state["tracker_state"].items():
        st.caption(f"{pos}: {pdata.get('name','')} - {pdata.get('action','')}")
# Show last tracked actions (for debug)
_TRACKER_STATE_PATH = Path(__file__).resolve().parent / "last_table_state.json"
try:
    with open(_TRACKER_STATE_PATH, "r") as _f:
        _tracker_state = json.load(_f)
except Exception:
    _tracker_state = {}

if st.button("Auto-Capture Until My Turn", use_container_width=True):
    st.warning("Auto-capturing... The app will block until it's your turn.")
    session_statuses = []
    while True:
        # Optionally capture a new screenshot here if needed
        extract_player_sections(DCIM_DIR)
        # Use the main_right image for button detection
        turn_status = False
        try:
            from reader_utils import button_crop_and_check_turn
            turn_status = button_crop_and_check_turn(MAIN_RIGHT_IMAGE)
        except Exception as e:
            st.error(f"Error during button OCR: {e}")
            break
        session_statuses.append(turn_status)
        st.info(f"Button crop/turn status: {'My turn' if turn_status else 'Not my turn'} (capture {len(session_statuses)})")
        if turn_status is True:
            st.success("It's your turn! Auto-capture stopped.")
            break
        time.sleep(2)
    st.subheader("Session Turn Statuses")
    for idx, status in enumerate(session_statuses, 1):
        st.write(f"Capture {idx}: {'My turn' if status else 'Not my turn'}")

# --- Auto-Capture Until My Turn with Manual Stop (side by side, only one set of buttons) ---
if "auto_capture_running" not in st.session_state:
    st.session_state["auto_capture_running"] = False
if "auto_capture_stop" not in st.session_state:
    st.session_state["auto_capture_stop"] = False

col_auto, col_stop = st.columns([2, 1])
with col_auto:
    start_auto = st.button("Auto-Capture Until My Turn", use_container_width=True, key="auto_capture_start")
with col_stop:
    stop_auto = st.button("Stop Auto-Capture", use_container_width=True, key="auto_capture_stop_btn", disabled=not st.session_state["auto_capture_running"])

if start_auto and not st.session_state["auto_capture_running"]:
    st.session_state["auto_capture_running"] = True
    st.session_state["auto_capture_stop"] = False
    st.session_state["session_statuses"] = []  # Reset session captures on new start
    st.rerun()
if stop_auto and st.session_state["auto_capture_running"]:
    st.session_state["auto_capture_stop"] = True
    st.session_state["auto_capture_running"] = False
    st.rerun()

if st.session_state.get("auto_capture_running", False):
    st.warning("Auto-capturing... The app will block until it's your turn or you stop it.")
    if "session_statuses" not in st.session_state:
        st.session_state["session_statuses"] = []
    session_statuses = st.session_state["session_statuses"]
    while st.session_state.get("auto_capture_running", False):
        # --- Capture a new screenshot (like Analyze Current Screen) ---
        try:
            capture_screen(SCREEN_IMAGE, display_index=2)
        except Exception as e:
            st.error(f"Error capturing screenshot: {e}")
            st.session_state["auto_capture_running"] = False
            break
        extract_player_sections(DCIM_DIR)
        results = process_positions_parallel(PLAYERS_DIR, ALL_POSITIONS, max_workers=6)
        _tracker_state = st.session_state["tracker_state"]
        changed = False
        for pos, pdata in results.items():
            name = (pdata.get("name") or "").strip()
            action = (pdata.get("action") or "").strip()
            prev_action = (_tracker_state.get(pos, {}).get("action") or "").strip()
            if name and action and action != prev_action:
                changed = True
        if changed:
            st.session_state["tracker_state"] = results
            _tracker_state = results
        for pos, data in results.items():
            name = (data.get("name") or "").strip()
            action = (data.get("action") or "").strip().upper()
            if not name:
                continue
            stats = PLAYER_STATS.setdefault(name, {"hands_seen": 0, "not_folded": 0, "vpip": 0})
            stats["hands_seen"] += 1
            if action and action != "FOLD":
                stats["not_folded"] += 1
            if action in {"RAISE", "CALL"}:
                stats["vpip"] += 1
        with open(_STATS_PATH, "w") as _f:
            json.dump(PLAYER_STATS, _f, indent=2)
        st.session_state["position_warning"] = assign_table_positions(results)
        st.session_state["results"] = results
        # --- Button OCR ---
        turn_status = False
        ocr_text = ""
        try:
            from reader_utils import button_crop_and_check_turn
            turn_status, ocr_text = button_crop_and_check_turn(MAIN_RIGHT_IMAGE)
        except Exception as e:
            st.error(f"Error during button OCR: {e}")
            st.session_state["auto_capture_running"] = False
            break
        session_statuses.append({
            "turn_status": turn_status,
            "ocr_text": ocr_text,
            "results": results,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        st.session_state["session_statuses"] = session_statuses
        st.info(f"Button crop/turn status: {'My turn' if turn_status else 'Not my turn'} | OCR text: '{ocr_text}' (capture {len(session_statuses)})")
        # Print what changed between this and previous session for each player, right after each capture
        if len(session_statuses) > 1:
            prev_results = session_statuses[-2]["results"]
            curr_results = session_statuses[-1]["results"]
            st.write("**Changes since last capture:**")
            for pos in ALL_POSITIONS:
                prev = prev_results.get(pos, {})
                curr = curr_results.get(pos, {})
                changes = []
                for k in set(prev.keys()).union(curr.keys()):
                    if prev.get(k) != curr.get(k):
                        changes.append(f"{k}: '{prev.get(k, '')}' → '{curr.get(k, '')}'")
                if changes:
                    st.write(f"- {pos}: {curr.get('name', '')} [{' | '.join(changes)}]")
        if turn_status is True:
            st.success("It's your turn! Auto-capture stopped.")
            st.session_state["auto_capture_running"] = False
            break
        if st.session_state.get("auto_capture_stop", False):
            st.info("Manual stop requested. Auto-capture stopped.")
            st.session_state["auto_capture_running"] = False
            break
        # time.sleep(2)
    st.subheader("Session Turn Statuses")
    for idx, entry in enumerate(session_statuses, 1):
        st.write(f"Capture {idx}: {'My turn' if entry['turn_status'] else 'Not my turn'} | OCR text: '{entry['ocr_text']}'")


