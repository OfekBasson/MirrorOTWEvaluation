# streamlit_app.py
# Run: streamlit run streamlit_app.py
# Requirements: streamlit>=1.24, pillow

import os
import io
import csv
import random
import re
from datetime import datetime
from typing import List, Dict, Any
from  pathlib import Path

import streamlit as st
from PIL import Image

# -----------------------------
# Helpers
# -----------------------------
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

# Only allowlisted images
ALLOWED_IMAGES = {
    "Mirror Change Top Layers _ Alpha_ 0_5.png",
    "No Intervension _ Alpha_ 0_5.png",
}

def list_folders(root: str) -> List[str]:
    try:
        entries = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
        entries.sort()
        return entries
    except Exception:
        return []


def list_images(folder_path: str) -> List[str]:
    files = []
    try:
        for f in os.listdir(folder_path):
            ext = os.path.splitext(f)[1].lower()
            if ext in IMG_EXTS and f in ALLOWED_IMAGES:
                files.append(f)
    except Exception:
        pass
    files.sort()
    return files


def load_image(path: str) -> Image.Image:
    try:
        return Image.open(path)
    except Exception:
        # Return a tiny placeholder if image fails to load
        return Image.new("RGB", (32, 32), color=(200, 200, 200))


def slugify(text: str) -> str:
    text = text.strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_\-]", "", text)


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Image Set User Study", layout="wide")


st.title('📊 **Goal:** For each folder (a "question"), view a filtered set of images and select the image with the best reflection')



# Default data folder per your setup (contains Set A / Set B / Set C)
APP_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = APP_DIR / "model_outputs"   # folder lives next to streamlit_app.py

root_dir = st.text_input(
    "Root directory (contains Set folders)",
    value=str(DEFAULT_ROOT),
    disabled=True,  # keeps it fixed to the bundled folder for fastest sharing
)

# # Participant + Set selection
# top_cols = st.columns([2, 2, 1])
# with top_cols[0]:
#     participant_name = st.text_input("Your name *", placeholder="e.g., Ofek").strip()
# with top_cols[1]:
#     available_sets = list_folders(root_dir)
#     # Heuristic: prefer set-like names first
#     ordered_sets = sorted(available_sets, key=lambda s: (not s.lower().startswith("set"), s))
#     selected_set = st.selectbox("Select a Set *", options=ordered_sets if ordered_sets else [""], index=0 if ordered_sets else 0)
# with top_cols[2]:
#     st.write("")
#     st.write("")
#     st.write("")
participant_name = st.text_input("Your name *", placeholder="e.g., Ofek").strip()


col_opts = st.columns(3)
with col_opts[0]:
    shuffle_questions = st.checkbox("Randomize question (folder) order", value=True)
with col_opts[1]:
    shuffle_images = st.checkbox("Randomize image order within a question", value=True)

if "state_initialized" not in st.session_state:
    st.session_state.state_initialized = False

# Start / Refresh is disabled until name & set are provided
# can_start = bool(participant_name) and bool(selected_set)
can_start = bool(participant_name)

if st.button("Start / Refresh", type="primary", disabled=not can_start):
    # base_dir = os.path.join(root_dir, selected_set)
    base_dir = root_dir
    print(f'base_dir: {base_dir}')
    folders = list_folders(base_dir)
    if shuffle_questions:
        rng_q = random.Random(f"{participant_name}|questions")
        rng_q.shuffle(folders)

    # Build question list with image lists cached in state
    questions = []
    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        imgs = list_images(folder_path)
        if shuffle_images:
            rng_i = random.Random(f"{participant_name}|{folder}")
            rng_i.shuffle(imgs)
        if imgs:
            questions.append({
                "folder": folder,
                "path": folder_path,
                "images": imgs,
            })

    st.session_state.questions = questions
    st.session_state.current_idx = 0
    st.session_state.participant_name = participant_name
    # st.session_state.selected_set = selected_set
    # answers: folder -> {"mode": "best"|"worst_equal"|"none", "choice": <str or list[str]>}
    st.session_state.answers: Dict[str, Dict[str, Any]] = {}
    st.session_state.state_initialized = True

# Guard: if not initialized yet
if not st.session_state.state_initialized:
    if not can_start:
        # st.info("Enter your **name** and **select a set**, then click **Start / Refresh**.")
        st.info("Enter your **name**, then click **Start / Refresh**.")
    else:
        st.info("Click **Start / Refresh** to load questions.")
    st.stop()

questions = st.session_state.get("questions", [])
if not questions:
    # st.warning("No questions found. Ensure the selected set has subfolders with images.")
    st.warning("No questions found. Ensure the root directory has subfolders with images.")
    st.stop()

# Navigation state
nq = len(questions)
idx = int(st.session_state.get("current_idx", 0))
idx = max(0, min(idx, nq - 1))
st.session_state.current_idx = idx

# Persisted meta
participant_name = st.session_state.get("participant_name", participant_name)
# selected_set = st.session_state.get("selected_set", selected_set)

# Current question
q = questions[idx]
folder = q["folder"]
folder_path = q["path"]
imgs = q["images"]

st.subheader(f"Participant: {participant_name}")
st.subheader(f"Question {idx+1} / {nq}  —  Folder: {folder}")

# Layout images in a responsive grid (max 4 per row)
cols_per_row = min(4, max(2, len(imgs)))
rows = (len(imgs) + cols_per_row - 1) // cols_per_row

# Keys for per-image checkboxes (best + worst)
best_keys = [f"best::{folder}::{fname}" for fname in imgs]
worst_keys = [f"worst::{folder}::{fname}" for fname in imgs]

# Ensure selection state exists
if "answers" not in st.session_state:
    st.session_state.answers = {}

# ----------
# Initialize widget state BEFORE rendering widgets (no `value=` below)
# to avoid: "widget ... created with a default value but also had its value set via Session State"
for k in best_keys + worst_keys:
    if k not in st.session_state:
        st.session_state[k] = False
none_key = f"none::{folder}"
if none_key not in st.session_state:
    st.session_state[none_key] = False

# Restore previous answer (sets appropriate keys True)
prev = st.session_state.answers.get(folder)
if prev:
    # Reset first
    for k in best_keys + worst_keys:
        st.session_state[k] = False
    st.session_state[none_key] = False

    if prev.get("mode") == "best":
        chosen = prev.get("choice")
        for k, fname in zip(best_keys, imgs):
            st.session_state[k] = (fname == chosen)
    elif prev.get("mode") == "worst_equal":
        # Mark worst (the one not in others)
        worst_of = [f for f in imgs if f not in prev.get("choice", [])]
        worst = worst_of[0] if worst_of else None
        for k, fname in zip(worst_keys, imgs):
            st.session_state[k] = (fname == worst)
    elif prev.get("mode") == "none":
        st.session_state[none_key] = True

# ----------
# Callbacks to maintain exclusivity

def _select_best(chosen_fname: str):
    st.session_state.answers[folder] = {"mode": "best", "choice": chosen_fname}
    for k, fname in zip(best_keys, imgs):
        st.session_state[k] = (fname == chosen_fname)
    for k in worst_keys:
        st.session_state[k] = False
    st.session_state[none_key] = False


def _select_worst(chosen_fname: str):
    others = [f for f in imgs if f != chosen_fname]
    st.session_state.answers[folder] = {"mode": "worst_equal", "choice": others}
    for k, fname in zip(worst_keys, imgs):
        st.session_state[k] = (fname == chosen_fname)
    for k in best_keys:
        st.session_state[k] = False
    st.session_state[none_key] = False


def _select_none():
    st.session_state.answers[folder] = {"mode": "none", "choice": None}
    for k in best_keys + worst_keys:
        st.session_state[k] = False
    st.session_state[none_key] = True

# Render grid: image (no caption/name) + two checkboxes underneath
for r in range(rows):
    cols = st.columns(cols_per_row)
    for c in range(cols_per_row):
        i = r * cols_per_row + c
        if i >= len(imgs):
            continue
        img_file = imgs[i]
        img_path = os.path.join(folder_path, img_file)
        best_key = best_keys[i]
        worst_key = worst_keys[i]
        with cols[c]:
            st.image(load_image(img_path), use_container_width=True)
            st.checkbox(
                "Select",
                key=best_key,
                on_change=_select_best,
                args=(img_file,),
            )

# --- Navigation buttons BELOW the checkboxes ---
nav_prev, nav_spacer, nav_next = st.columns([1, 6, 1])
with nav_prev:
    if st.button("⬅️ Previous", disabled=(idx == 0)):
        st.session_state.current_idx = max(0, idx - 1)
        st.rerun()
with nav_next:
    if st.button("Next ➡️", disabled=(idx >= nq - 1)):
        st.session_state.current_idx = min(nq - 1, idx + 1)
        st.rerun()

st.markdown("---")

# Progress + Export
answered = sum(1 for f in st.session_state.answers if st.session_state.answers[f] is not None)
st.progress(answered / nq)
st.write(f"Answered: **{answered}/{nq}**")

# Prepare results table
results = []
for qd in questions:
    f = qd["folder"]
    ans = st.session_state.answers.get(f)
    if not ans:
        results.append({"participant": participant_name, "folder": f, "selected_file": ""})
        continue
    mode = ans.get("mode")
    if mode == "best":
        results.append({"participant": participant_name, "folder": f, "selected_file": ans.get("choice", "")})
    elif mode == "worst_equal":
        others = ans.get("choice", [])
        if len(others) >= 2:
            msg = f"equal score for {others[0]} and {others[1]}"
        else:
            msg = "equal score for " + " and ".join(others)
        results.append({"participant": participant_name, "folder": f, "selected_file": msg})
    elif mode == "none":
        results.append({"participant": participant_name, "folder": f, "selected_file": none_label})
    else:
        results.append({"participant": participant_name, "folder": f, "selected_file": ""})

# CSV bytes
output = io.StringIO()
writer = csv.DictWriter(output, fieldnames=["participant", "folder", "selected_file"])
writer.writeheader()
writer.writerows(results)
csv_text = output.getvalue()
csv_bytes = csv_text.encode("utf-8")

# Save a copy to disk under root/results
results_dir = os.path.join(root_dir, "results")
os.makedirs(results_dir, exist_ok=True)
fn = f"{slugify(participant_name)}_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
file_path = os.path.join(results_dir, fn)
try:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(csv_text)
    st.success(f"Saved results to: {file_path}")
except Exception as e:
    st.warning(f"Could not save results to disk: {e}")

# Download button
st.download_button(
    label="⬇️ Download results CSV",
    data=csv_bytes,
    file_name=fn,
    mime="text/csv",
)

# Completion message
if answered == nq:
    st.success("All questions answered! You can download the CSV above.")
