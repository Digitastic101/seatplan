import json
import uuid
from typing import List, Dict
import streamlit as st

# -------------------------------------------------
# Core helper – inserts rows keeping the user order
# If position == "above"  -> last item in new_rows ends up closest to ref_row
# If position == "below"  -> first item in new_rows ends up closest to ref_row
# -------------------------------------------------

def insert_rows(
    seatmap: Dict,
    *,
    section_id: str,
    ref_row_index: str,
    new_rows: List[Dict[str, List[int]]],
    position: str = "above",
    default_price: str = "85"
) -> Dict:
    """Return a copy of *seatmap* with *new_rows* inserted.

    new_rows MUST be ordered from nearest‑to‑reference → furthest‑away.
    """
    section = seatmap[section_id]
    rows_items = list(section["rows"].items())  # preserves original order

    # Build (row_id, row_dict) pairs in the order we want them injected
    ordered_pairs = []
    source_iter = new_rows if position == "below" else reversed(new_rows)

    for spec in source_iter:
        row_letter   = spec["index"].upper()
        seat_numbers = spec["numbers"]
        row_id       = f"r{uuid.uuid4().hex[:6]}"

        seats = {}
        for num in seat_numbers:
            seat_id = f"s{uuid.uuid4().hex[:6]}"
            seats[seat_id] = {
                "id": seat_id,
                "number": f"{row_letter}{num}",
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
            # Insert ABOVE the reference
            if position == "above":
                for pid, pdata in ordered_pairs:
                    updated_rows[pid] = pdata
            # Always keep the reference row itself (unless "0" used)
            if ref_row_index != "0":
                updated_rows[rid] = rdata
            # Insert BELOW the reference
            if position == "below":
                for pid, pdata in ordered_pairs:
                    updated_rows[pid] = pdata
            inserted = True
        else:
            updated_rows[rid] = rdata

    # If reference not located (or ref_row_index == "0"), insert at start/end
    if not inserted:
        if position == "above":
            for pid, pdata in ordered_pairs:
                updated_rows = {pid: pdata, **updated_rows}
        else:
            for pid, pdata in ordered_pairs:
                updated_rows[pid] = pdata

    # Re‑assemble seatmap copy
    new_seatmap = seatmap.copy()
    new_section        = section.copy()
    new_section["rows"] = updated_rows
    new_seatmap[section_id] = new_section
    return new_seatmap

# -------------------------------------------------
# Streamlit UI
# -------------------------------------------------

st.title("🎭 Add Rows to Seatmap")

uploaded_file = st.file_uploader("Upload your seatmap JSON", type="json")

# --- reference row / seat ---
ref_row_letter = st.text_input("Reference row letter (e.g. 'B' – or '0' for section start)", value="B")
ref_seat_number = st.text_input("Seat number in that row (e.g. '17')", value="17")

section_id = None
seatmap     = None
if uploaded_file:
    seatmap = json.load(uploaded_file)

    # find candidate sections
    matched_rows = []
    for sid, sdata in seatmap.items():
        if "rows" not in sdata:
            continue
        for rdata in sdata["rows"].values():
            if ref_row_letter == "0" or rdata["row_index"].upper() == ref_row_letter.upper():
                if ref_row_letter == "0" or any(s["number"] == f"{ref_row_letter.upper()}{ref_seat_number}" for s in rdata["seats"].values()):
                    matched_rows.append((f"{sdata['section_name']} (rows: {len(sdata['rows'])})", sid))
                    break

    if not matched_rows:
        st.warning("No section matches that row/seat.")
    else:
        display_labels = [lbl for lbl, _ in matched_rows]
        label_choice   = st.selectbox("Select section containing that seat:", display_labels)
        section_id     = dict(matched_rows)[label_choice]

        # show current rows
        rows_preview = []
        for r in seatmap[section_id]["rows"].values():
            letters = r["row_index"]
            nums    = [int(s["number"][len(letters):]) for s in r["seats"].values()]
            if nums:
                rows_preview.append(f"{letters}{min(nums)}–{max(nums)}")
        st.markdown("**Rows in this section:** " + ", ".join(rows_preview))

# --- insertion controls ---
position = st.radio("Insert rows", ["above", "below"], horizontal=True)
num_rows = st.number_input("How many new rows to add?", 1, 10, 1)

new_rows = []
for i in range(int(num_rows)):
    col1, col2, col3 = st.columns(3)
    with col1:
        letter = st.text_input(f"Row letter #{i+1}", key=f"row_letter_{i}")
    with col2:
        first = st.number_input("First seat", 1, 500, 1, key=f"first_{i}")
    with col3:
        last  = st.number_input("Last seat", 1, 500, 1, key=f"last_{i}")
    if letter and first <= last:
        new_rows.append({"index": letter.upper(), "numbers": list(range(first, last+1))})

# --- action & download ---
if uploaded_file and section_id and new_rows:
    if st.button("➕ Insert Rows"):
        try:
            update = insert_rows(
                seatmap,
                section_id=section_id,
                ref_row_index=ref_row_letter,
                new_rows=new_rows,
                position=position
            )
            st.session_state["updated_map"] = update
            st.success("Rows inserted – download below 👇")
        except Exception as e:
            st.error(str(e))

if "updated_map" in st.session_state:
    js = json.dumps(st.session_state["updated_map"], indent=2)
    st.download_button("📥 Download updated JSON", js, "seatmap_updated.json")
