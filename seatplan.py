import json
import uuid
from typing import List, Dict
import streamlit as st

# ===============================
# Alignment helpers
# ===============================

def _normalise_to_word(value: str) -> str:
    """
    Map any alignment token to 'left'|'center'|'right'.
    Supports: 'L','R','C','def' and 'left','center','right'.
    Defaults to 'center' for unknown/None.
    """
    if not value:
        return "center"
    v = str(value).strip().lower()
    if v in ("left", "l"):
        return "left"
    if v in ("right", "r"):
        return "right"
    if v in ("center", "centre", "c", "def", "default"):
        return "center"
    return "center"

def parse_alignment_word(section: dict) -> str:
    """Return 'left'|'center'|'right' from section fields."""
    raw = section.get("align", None)
    if raw is None:
        raw = section.get("alignment", None)
    return _normalise_to_word(raw)

def set_alignment_fields(section: dict, word: str) -> dict:
    """
    Return a COPY of section with BOTH fields set consistently:
      - align: L | R | def
      - alignment: left | center | right
    """
    compact = {"left": "L", "center": "def", "right": "R"}[word]
    sec = {**section}
    sec["align"] = compact
    sec["alignment"] = word
    return sec

def word_to_label(word: str) -> str:
    return {"left": "Left", "center": "Centre", "right": "Right"}[word]

def label_to_word(label: str) -> str:
    return {"Left": "left", "Centre": "center", "Right": "right"}[label]

# ===============================
# Core helper – insert rows
# ===============================

def insert_rows(
    seatmap: Dict,
    *,
    section_id: str,
    ref_row_index: str,
    new_rows: List[Dict[str, List[str]]],
    position: str = "above",
    default_price: str = "85"
) -> Dict:
    section = seatmap[section_id]
    rows_items = list(section["rows"].items())

    ordered_pairs = []
    source_iter = new_rows if position == "below" else reversed(new_rows)

    for spec in source_iter:
        row_letter = spec["index"].upper()
        seat_labels = spec["labels"]
        row_id = f"r{uuid.uuid4().hex[:6]}"

        seats = {}
        for label in seat_labels:
            seat_id = f"s{uuid.uuid4().hex[:6]}"
            seats[seat_id] = {
                "id": seat_id,
                "number": label,
                "price": default_price,
                "status": "av",
                "handicap": "no",
            }

        ordered_pairs.append(
            (row_id,
             {
                 "seats": seats,
                 "row_index": row_letter,
                 "row_price": default_price,
                 "row_id": row_id,
             })
        )

    updated_rows = {}
    inserted = False

    for rid, rdata in rows_items:
        if not inserted and (ref_row_index == "0" or rdata["row_index"].upper() == ref_row_index.upper()):
            if position == "above":
                for pid, pdata in ordered_pairs:
                    updated_rows[pid] = pdata
            if ref_row_index != "0":
                updated_rows[rid] = rdata
            if position == "below":
                for pid, pdata in ordered_pairs:
                    updated_rows[pid] = pdata
            inserted = True
        else:
            updated_rows[rid] = rdata

    if not inserted:
        if position == "above":
            for pid, pdata in ordered_pairs:
                updated_rows = {pid: pdata, **updated_rows}
        else:
            for pid, pdata in ordered_pairs:
                updated_rows[pid] = pdata

    new_seatmap = seatmap.copy()
    new_section = seatmap[section_id].copy()
    new_section["rows"] = updated_rows
    new_seatmap[section_id] = new_section
    return new_seatmap

# ===============================
# Relabel rows helper
# ===============================

def relabel_rows(
    seatmap: Dict,
    *,
    section_id: str,
    target_row_letters: List[str],
    new_prefix: str
) -> Dict:
    if not target_row_letters:
        return seatmap

    targets_upper = {t.upper() for t in target_row_letters}
    section = seatmap.get(section_id)
    if not section or "rows" not in section:
        return seatmap

    new_seatmap = seatmap.copy()
    new_section = section.copy()
    new_rows = {}

    for rid, rdata in section["rows"].items():
        original_row = str(rdata.get("row_index", ""))
        if original_row.upper() in targets_upper:
            new_row_label = f"{new_prefix}{original_row}"

            new_seats = {}
            for sid, sdata in rdata["seats"].items():
                old = str(sdata.get("number", ""))
                if old.upper().startswith(original_row.upper()):
                    rest = old[len(original_row):]
                    sdata = {**sdata, "number": f"{new_row_label}{rest}"}
                new_seats[sid] = sdata

            new_rows[rid] = {
                **rdata,
                "row_index": new_row_label,
                "seats": new_seats,
            }
        else:
            new_rows[rid] = rdata

    new_section["rows"] = new_rows
    new_seatmap[section_id] = new_section
    return new_seatmap

# ===============================
# Flip rows order helper
# ===============================

def flip_rows_order(
    seatmap: Dict,
    *,
    section_id: str,
    reverse: bool = False,
) -> Dict:
    """
    Reorders rows in a section. If reverse=True, reverse current order.
    If reverse=False, keep current order (no change).
    NOTE: Does NOT touch section name or alignment.
    """
    section = seatmap.get(section_id)
    if not section or "rows" not in section:
        return seatmap

    items = list(section["rows"].items())
    new_items = list(reversed(items)) if reverse else items

    new_rows = {}
    for rid, rdata in new_items:
        new_rows[rid] = rdata

    new_map = seatmap.copy()
    new_section = section.copy()
    new_section["rows"] = new_rows
    new_map[section_id] = new_section
    return new_map

# ===============================
# Section details updater
# ===============================

def update_section_details(
    seatmap: dict,
    *,
    section_id: str,
    new_name: str = None,
    alignment_label: str = None
) -> dict:
    """
    Update section_name and (optionally) alignment.
    - Name is updated if provided (non-empty).
    - Alignment is ONLY updated if alignment_label is provided AND differs from current.
      When we do update, we set BOTH fields align/alignment to keep them in sync.
    """
    if section_id is None:
        return seatmap

    new_map = seatmap.copy()
    current_section = new_map.get(section_id, {})
    sec = current_section.copy()

    # Section name
    if new_name is not None and new_name.strip():
        sec["section_name"] = new_name.strip()

    # Alignment (only if changed)
    if alignment_label:
        existing_word = parse_alignment_word(sec)
        chosen_word = label_to_word(alignment_label)
        if chosen_word != existing_word:
            sec = set_alignment_fields(sec, chosen_word)

    new_map[section_id] = sec
    return new_map

# ===============================
# Streamlit UI
# ===============================

st.title("🎭 Update Seat Plan")

# Prefer the latest updated map if we already saved in this session
base_map = st.session_state.get("updated_map")

uploaded_file = st.file_uploader("Upload your seatmap JSON", type="json")

ref_row_letter = st.text_input("Reference row letter (e.g. 'B' – or '0' for section start)", value="A")
ref_seat_number = st.text_input("Seat number in that row (e.g. '17')", value="1")

section_id = None
seatmap = None

if uploaded_file and base_map is None:
    seatmap = json.load(uploaded_file)
elif base_map is not None:
    seatmap = base_map

if seatmap:
    matched_rows = []
    for sid, sdata in seatmap.items():
        if "rows" not in sdata:
            continue
        for rdata in sdata["rows"].values():
            matches_letter = (ref_row_letter == "0") or (rdata["row_index"].upper() == ref_row_letter.upper())
            matches_seat = (
                ref_row_letter == "0"
                or any(s["number"] == f"{ref_row_letter.upper()}{ref_seat_number}" for s in rdata["seats"].values())
            )
            if matches_letter and matches_seat:
                sec_name = sdata.get("section_name", sid)
                matched_rows.append((f"{sec_name} (rows: {len(sdata['rows'])})", sid))
                break

    if not matched_rows:
        st.warning("No section matches that row/seat.")
    else:
        display_labels = [lbl for lbl, _ in matched_rows]
        label_choice = st.selectbox("Select section containing that seat:", display_labels)
        section_id = dict(matched_rows)[label_choice]

        # Editable section name + alignment (alignment only saved if changed)
        current_section = seatmap[section_id]
        current_name = current_section.get("section_name", "")
        current_align_label = word_to_label(parse_alignment_word(current_section))

        col_name, col_align = st.columns([3, 2])
        with col_name:
            new_section_name = st.text_input("Section name", value=current_name)
        with col_align:
            align_choice = st.radio(
                "Alignment",
                ["Left", "Centre", "Right"],
                horizontal=True,
                index=["Left", "Centre", "Right"].index(current_align_label),
            )

        # Preview rows
        rows_preview = []
        for r in seatmap[section_id]["rows"].values():
            letters = r["row_index"]
            nums = [
                int(s["number"][len(letters):])
                for s in r["seats"].values()
                if s["number"][len(letters):].isdigit()
            ]
            if nums:
                rows_preview.append(f"{letters}{min(nums)}–{max(nums)}")
        st.markdown("**Rows in this section:** " + ", ".join(rows_preview))

        # ----------------------------------------
        # Fix row order (No change / Reverse only)
        # ----------------------------------------
        with st.expander("Fix row order"):
            flip_mode = st.radio(
                "Row order",
                ["No change", "Reverse current order"],
                horizontal=True,
            )
            reverse_flag = (flip_mode == "Reverse current order")

            # Show a tiny preview (first ~15)
            current_order = [r["row_index"] for _, r in seatmap[section_id]["rows"].items()]
            st.caption("Current order: " + " → ".join(current_order[:15]) + (" …" if len(current_order) > 15 else ""))
            if reverse_flag:
                st.caption("New order:     " + " → ".join(list(reversed(current_order[:15]))) + (" …" if len(current_order) > 15 else ""))

            if st.button("↕️ Apply row order change"):
                try:
                    updated = flip_rows_order(
                        seatmap,
                        section_id=section_id,
                        reverse=reverse_flag
                    )
                    st.session_state["updated_map"] = updated
                    seatmap = updated  # keep UI in sync
                    st.success("Row order updated.")
                except Exception as e:
                    st.error(str(e))

        # Relabel existing rows
        with st.expander("Optional: Relabel existing rows (e.g. add '(RV) ' prefix)"):
            available_rows = sorted(
                {r["row_index"] for r in seatmap[section_id]["rows"].values()},
                key=lambda x: x.upper()
            )

            col_a, col_b = st.columns([2, 3])
            with col_a:
                selected_rows = st.multiselect("Rows to change", options=available_rows)
            with col_b:
                new_prefix = st.text_input("Prefix to add", value="(RV) ")

            if selected_rows:
                preview_samples = ", ".join([f"{new_prefix}{r}" for r in selected_rows[:3]])
                st.caption(f"Preview: {preview_samples}{'…' if len(selected_rows) > 3 else ''}")

            if st.button("Apply relabel to selected rows"):
                try:
                    seatmap_local = update_section_details(
                        seatmap,
                        section_id=section_id,
                        new_name=new_section_name,
                        alignment_label=align_choice  # will only update if changed
                    )
                    updated = relabel_rows(
                        seatmap_local,
                        section_id=section_id,
                        target_row_letters=selected_rows,
                        new_prefix=new_prefix
                    )
                    st.session_state["updated_map"] = updated
                    seatmap = updated  # keep in-memory state in sync
                    st.success(f"Relabelled {len(selected_rows)} row(s) and applied any changed section details.")
                except Exception as e:
                    st.error(str(e))

# -----------------------------
# Add new rows (optional)
# -----------------------------

position = st.radio("Insert rows", ["above", "below"], horizontal=True)
num_rows = st.number_input("How many new rows to add?", 0, 10, 0)  # allow 0 to only save details

new_rows = []
for i in range(int(num_rows)):
    st.markdown(f"### Row #{i+1}")
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        letter = st.text_input(f"Row letter #{i+1}", key=f"row_letter_{i}")
    with col2:
        first = st.number_input("First seat", 1, 999, 1, key=f"first_{i}")
    with col3:
        last = st.number_input("Last seat", 1, 999, 1, key=f"last_{i}")

    if letter:
        seat_numbers = list(range(first, last + 1)) if first <= last else list(range(first, last - 1, -1))
        base_labels = [f"{letter.upper()}{n}" for n in seat_numbers]

        num_anomalies = st.number_input(f"How many anomalies in Row #{i+1}?", 0, 5, 0, key=f"num_ano_{i}")
        anomalies = []
        for j in range(num_anomalies):
            col_a1, col_a2 = st.columns([2, 3])
            with col_a1:
                ano_between = st.number_input(
                    f"Insert anomaly between... (#{j+1})",
                    min_value=min(first, last),
                    max_value=max(first, last) - 1,
                    key=f"ano_pos_{i}_{j}"
                )
            with col_a2:
                ano_label = st.text_input(f"Anomaly label (#{j+1})", key=f"ano_label_{i}_{j}")
            if ano_label:
                anomalies.append((ano_between, ano_label))

        for ano_between, ano_label in sorted(anomalies, key=lambda x: x[0], reverse=True):
            if ano_between in seat_numbers:
                insertion_index = seat_numbers.index(ano_between) + 1
                base_labels.insert(insertion_index, ano_label)

        new_rows.append({"index": letter.upper(), "labels": base_labels})

# -----------------------------
# Single action button
# -----------------------------

if seatmap and section_id:
    if st.button("✅ Update seat plan"):
        try:
            # Apply section details (alignment only if changed)
            seatmap_local = update_section_details(
                seatmap,
                section_id=section_id,
                new_name=new_section_name,
                alignment_label=align_choice
            )

            # If rows were provided, also insert them
            if new_rows:
                default_price = seatmap_local[section_id].get("price", "85")
                updated = insert_rows(
                    seatmap_local,
                    section_id=section_id,
                    ref_row_index=ref_row_letter,
                    new_rows=new_rows,
                    position=position,
                    default_price=default_price
                )
                msg = "Rows inserted and changes saved"
            else:
                updated = seatmap_local
                msg = "Changes saved"

            st.session_state["updated_map"] = updated
            seatmap = updated  # keep UI in sync
            st.success(f"{msg} – download below 👇")
        except Exception as e:
            st.error(str(e))

# -----------------------------
# Download
# -----------------------------

if "updated_map" in st.session_state:
    js = json.dumps(st.session_state["updated_map"], indent=2)
    st.download_button("📥 Download updated JSON", js, "seatmap_updated.json")
