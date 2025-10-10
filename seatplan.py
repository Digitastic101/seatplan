import json
import uuid
import re
from collections import OrderedDict
from typing import List, Dict, Tuple
import streamlit as st

# =================================================
# 🎭 Seat Plan Adaptions
# =================================================

# -------------------------------------------------
# Core helper – inserts rows keeping the user order
# -------------------------------------------------
def insert_rows(
    seatmap: Dict,
    *,
    section_id: str,
    ref_row_index: str,
    new_rows: List[Dict[str, List[str]]],
    position: str = "above",
    default_price: str = "85",
) -> Dict:
    section = seatmap[section_id]
    rows_items = list(section["rows"].items())

    ordered_pairs = []
    # new_rows are assumed already in desired order (UI can reverse)
    for spec in new_rows:
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
            (
                row_id,
                {
                    "seats": seats,
                    "row_index": row_letter,
                    "row_price": default_price,
                    "row_id": row_id,
                },
            )
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
            elif position == "below":
                if ref_row_index != "0":
                    updated_rows[rid] = rdata
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
    new_section = section.copy()
    new_section["rows"] = updated_rows
    new_seatmap[section_id] = new_section
    return new_seatmap


# -------------------------------------------------
# Relabel multiple rows + their seats
# -------------------------------------------------
def relabel_rows(
    seatmap: Dict, *, section_id: str, target_row_letters: List[str], new_prefix: str
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


# -------------------------------------------------
# Update section meta (name + align)
# -------------------------------------------------
def update_section_meta(
    seatmap: Dict,
    *,
    section_id: str,
    new_name: str = None,
    new_align: str = None
) -> Dict:
    section = seatmap.get(section_id, {}).copy()
    if not section:
        return seatmap
    if new_name is not None:
        section["section_name"] = new_name
    if new_align is not None:
        section["align"] = new_align
    updated = seatmap.copy()
    updated[section_id] = section
    return updated


# -------------------------------------------------
# Direction helpers (operate on selected section)
# -------------------------------------------------
def _natural_seat_key(seat_label: str) -> tuple:
    """
    Sort like: 'A1', 'A2', 'A10' (not A1, A10, A2).
    Returns (row_letters, number_int|0, original_label).
    """
    m = re.match(r"^([A-Za-z]+)(\d+)$", str(seat_label))
    if not m:
        return (seat_label, 0, seat_label)
    row, num = m.group(1), int(m.group(2))
    return (row.upper(), num, seat_label)

def reverse_section_rows_order(seatmap: Dict, *, section_id: str) -> Dict:
    """
    Rebuilds the rows dict in reverse insertion order.
    """
    section = seatmap.get(section_id)
    if not section or "rows" not in section:
        return seatmap

    rows_items = list(section["rows"].items())  # preserves current order
    reversed_rows = OrderedDict()
    for rid, rdata in reversed(rows_items):
        reversed_rows[rid] = rdata

    updated = seatmap.copy()
    updated_section = section.copy()
    updated_section["rows"] = reversed_rows
    updated[section_id] = updated_section
    return updated

def reverse_section_seat_order(seatmap: Dict, *, section_id: str) -> Dict:
    """
    For each row in the section, rebuilds the seats dict in the opposite order.
    Labels are NOT changed—only the order in the dict.
    """
    section = seatmap.get(section_id)
    if not section or "rows" not in section:
        return seatmap

    updated = seatmap.copy()
    updated_section = section.copy()
    new_rows = OrderedDict()

    for rid, rdata in section["rows"].items():
        seats_items = list(rdata.get("seats", {}).items())
        seats_items_sorted = sorted(
            seats_items, key=lambda kv: _natural_seat_key(kv[1].get("number", ""))
        )
        seats_items_reversed = list(reversed(seats_items_sorted))
        new_seats = OrderedDict()
        for sid, sdata in seats_items_reversed:
            new_seats[sid] = sdata
        new_rows[rid] = {**rdata, "seats": new_seats}

    updated_section["rows"] = new_rows
    updated[section_id] = updated_section
    return updated


# =================================================
# Streamlit UI
# =================================================
st.title("🎭 Seat Plan Adaptions")

uploaded_file = st.file_uploader("Upload your seatmap JSON", type="json")

ref_row_letter = st.text_input(
    "Reference row letter (e.g. 'B' – or '0' for section start)",
    value="A"
)
ref_seat_number = st.text_input(
    "Seat number in that row (e.g. '17')",
    value="1"
)

section_id = None
seatmap = None

if uploaded_file:
    seatmap = json.load(uploaded_file)

    # Find candidate sections from the reference row/seat
    matched_rows: List[Tuple[str, str]] = []
    for sid, sdata in seatmap.items():
        if "rows" not in sdata:
            continue
        for rdata in sdata["rows"].values():
            if ref_row_letter == "0" or rdata["row_index"].upper() == ref_row_letter.upper():
                if ref_row_letter == "0" or any(
                    s["number"] == f"{ref_row_letter.upper()}{ref_seat_number}"
                    for s in rdata["seats"].values()
                ):
                    align_code = sdata.get("align", "def")
                    align_friendly = {"l":"Left", "r":"Right", "def":"Centre (default)"}.get(align_code, align_code)
                    label = f"{sdata.get('section_name','(unnamed)')} · rows: {len(sdata['rows'])} · align: {align_friendly}"
                    matched_rows.append((label, sid))
                    break

    if not matched_rows:
        st.warning("No section matches that row/seat.")
    else:
        display_labels = [lbl for lbl, _ in matched_rows]
        label_choice = st.selectbox("Select section containing that seat:", display_labels)
        section_id = dict(matched_rows)[label_choice]

        # --- Preview rows in this section ---
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
        st.markdown("**Rows in this section:** " + (", ".join(rows_preview) or "(none)"))

        # --- Editable section meta (NAME + ALIGN) ---
        st.subheader("Section settings")
        current_name = seatmap[section_id].get("section_name", "")
        current_align = seatmap[section_id].get("align", "def")

        align_labels = {
            "l": "Left",
            "r": "Right",
            "def": "Centre (default)",
        }
        align_options = list(align_labels.keys())
        align_display = [align_labels[a] for a in align_options]

        col_sn, col_al = st.columns([3, 1])
        with col_sn:
            edited_name = st.text_input("Section name", value=current_name)
        with col_al:
            selected_index = align_options.index(current_align) if current_align in align_options else 2
            display_choice = st.selectbox(
                "Align",
                align_display,
                index=selected_index,
                help="Where this section sits in the auditorium view."
            )
            edited_align = align_options[align_display.index(display_choice)]

        st.caption("Tip: Left / Right / Centre = seating alignment within the plan.")

        # ---------------------------------------------
        # OPTIONAL: Relabel existing rows + seat tags
        # ---------------------------------------------
        with st.expander("Optional: Relabel existing rows (e.g. add '(RV) ' prefix)"):
            # Available row letters in this section
            available_rows = []
            for r in seatmap[section_id]["rows"].values():
                if "row_index" in r:
                    available_rows.append(str(r["row_index"]))
            available_rows = sorted(dict.fromkeys(available_rows), key=lambda x: x.upper())

            col_a, col_b = st.columns([2, 3])
            with col_a:
                selected_rows = st.multiselect(
                    "Rows to change",
                    options=available_rows,
                    help="Pick one or more rows to relabel",
                )
            with col_b:
                new_prefix = st.text_input(
                    "Prefix to add",
                    value="(RV) ",
                    help="Applied to each selected row, e.g. '(RV) ' + T -> '(RV) T'",
                )

            if selected_rows:
                preview_samples = ", ".join([f"{new_prefix}{r}" for r in selected_rows[:3]])
                st.caption(f"Preview: {preview_samples}{'…' if len(selected_rows) > 3 else ''}")

            if st.button("Apply relabel to selected rows"):
                try:
                    seatmap = relabel_rows(
                        seatmap,
                        section_id=section_id,
                        target_row_letters=selected
