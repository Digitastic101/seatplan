import json
import uuid
from typing import List, Dict
import streamlit as st

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

# -------------------------------------------------
# Relabel rows helper
# -------------------------------------------------

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

# -------------------------------------------------
# Helper – update section name and alignment
# -------------------------------------------------

def update_section_details(
    seatmap: Dict,
    *,
    section_id: str,
    new_name: str = None,
    alignment_choice: str = None
) -> Dict:
    if section_id is None:
        return seatmap

    mapping = {"Left": "left", "Centre": "center", "Right": "right"}
    normalised_alignment = mapping.get(alignment_choice, None)

    new_map = seatmap.copy()
    sec = new_map.get(section_id, {}).copy()

    if new_name:
        sec["section_name"] = new_name.strip()
    if normalised_alignment:
        sec["alignment"] = normalised_alignment

    new_map[section_id] = sec
    return new_map

# -------------------------------------------------
# Streamlit UI
# -------------------------------------------------

st.title("🎭 Add Rows to Seatmap")

uploaded_file = st.file_uploader("Upload your seatmap JSON", type="json")

ref_row_letter = st.text_input("Reference row letter (e.g. 'B' – or '0' for section start)", value="A")
ref_seat_number = st.text_input("Seat number in that row (e.g. '17')", value="1")

section_id = None
seatmap = None

if uploaded_file:
    seatmap = json.load(uploaded_file)

    matched_rows = []
    for sid, sdata in seatmap.items():
        if "rows" not in sdata:
            continue
        for rdata in sdata["rows"].values():
            if ref_row_letter == "0" or rdata["row_index"].upper() == ref_row_letter.upper():
                if ref_row_letter == "0" or any(
                    s["number"] == f"{ref_row_letter.upper()}{ref_seat_number}"
                    for s in rdata["seats"].values()
                ):
                    sec_name = sdata.get("section_name", sid)
                    matched_rows.append((f"{sec_name} (rows: {len(sdata['rows'])})", sid))
                    break

    if not matched_rows:
        st.warning("No section matches that row/seat.")
    else:
        display_labels = [lbl for lbl, _ in matched_rows]
        label_choice = st.selectbox("Select section containing that seat:", display_labels)
        section_id = dict(matched_rows)[label_choice]

        # Editable section name + alignment (no separate button)
        current_name = seatmap[section_id].get("section_name", "")
        current_alignment = seatmap[section_id].get("alignment", "left")
        align_label_map = {"left": "Left", "center": "Centre", "right": "Right"}
        current_align_label = align_label_map.get(str(current_alignment).lower(), "Left")

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
        f
