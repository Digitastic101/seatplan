import json
import uuid
from typing import List, Dict
import streamlit as st

def insert_rows(
    seatmap: Dict,
    *,
    section_id: str,
    ref_row_index: str,
    new_rows: List[Dict[str, List[int]]],
    position: str = "above",
    default_price: str = "85"
) -> Dict:
    section = seatmap[section_id]
    rows_items = list(section["rows"].items())
    new_rows_dict = {}

    for spec in new_rows:
        row_letter = spec["index"]
        seat_numbers = spec["numbers"]
        row_id = f"r{uuid.uuid4().hex[:6]}"

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

        new_rows_dict[row_id] = {
            "seats": seats,
            "row_index": row_letter,
            "row_price": default_price,
            "row_id": row_id,
        }

    updated_rows = {}
    inserted = False

    for rid, rdata in rows_items:
        if not inserted and rdata["row_index"] == ref_row_index:
            if position == "above":
                updated_rows.update(new_rows_dict)
            updated_rows[rid] = rdata
            if position == "below":
                updated_rows.update(new_rows_dict)
            inserted = True
        else:
            updated_rows[rid] = rdata

    if not inserted:
        updated_rows.update(new_rows_dict)

    new_seatmap = seatmap.copy()
    new_section = section.copy()
    new_section["rows"] = updated_rows
    new_seatmap[section_id] = new_section
    return new_seatmap


# === Streamlit App ===
st.title("🎭 Add Rows to Seatmap")

uploaded_file = st.file_uploader("Upload your seatmap JSON", type="json")

# Always show inputs
ref_row_letter = st.text_input("Reference row letter (e.g. 'B')", value="B")
ref_seat_number = st.text_input("Seat number in that row (e.g. '17')", value="17")

section_id = None
seatmap = None
if uploaded_file:
    seatmap = json.load(uploaded_file)

    # Find all rows matching that combination
    matched_rows = []
    for sid, sdata in seatmap.items():
        if "rows" not in sdata:
            continue
        for rid, rdata in sdata["rows"].items():
            if rdata["row_index"].upper() != ref_row_letter.upper():
                continue
            if any(s["number"] == f"{ref_row_letter.upper()}{ref_seat_number}" for s in rdata["seats"].values()):
                label = f"{sdata['section_name']} (Row {ref_row_letter.upper()} includes {ref_row_letter.upper()}{ref_seat_number})"
                matched_rows.append((label, sid))

    if not matched_rows:
        st.warning("No matching row found for that letter and seat number.")
    else:
        display_labels = [opt[0] for opt in matched_rows]
        section_label = st.selectbox("Select section containing that seat:", options=display_labels)
        section_id = dict(matched_rows)[section_label]

        # Show existing rows in that section
        selected_section = seatmap[section_id]
        existing_rows = selected_section.get("rows", {})
        row_summaries = []
        for r in existing_rows.values():
            row_index = r.get("row_index")
            seat_numbers = [int(seat["number"][len(row_index):]) for seat in r.get("seats", {}).values() if seat["number"].startswith(row_index)]
            if seat_numbers:
                row_summaries.append(f"{row_index}{min(seat_numbers)}–{max(seat_numbers)}")
        if row_summaries:
            st.markdown("**Rows in this section:** " + ", ".join(sorted(row_summaries)))

position = st.radio("Insert rows", options=["above", "below"])
num_rows = st.number_input("How many new rows to add?", min_value=1, max_value=10, value=1)

new_rows = []
for i in range(num_rows):
    col1, col2, col3 = st.columns(3)
    with col1:
        letter = st.text_input(f"Row letter #{i+1}", key=f"letter_{i}")
    with col2:
        start_num = st.number_input(f"First seat number", min_value=1, max_value=500, value=1, key=f"start_{i}", placeholder="1")
    with col3:
        end_num = st.number_input(f"Last seat number", min_value=1, max_value=500, value=1, key=f"end_{i}", placeholder="1")

    if letter and start_num <= end_num:
        seat_range = list(range(start_num, end_num + 1))
        new_rows.append({"index": letter.upper(), "numbers": seat_range})

if uploaded_file and section_id and new_rows:
    if st.button("➕ Insert Rows"):
        try:
            updated_map = insert_rows(
                seatmap,
                section_id=section_id,
                ref_row_index=ref_row_letter.upper(),
                new_rows=new_rows,
                position=position
            )
            updated_json = json.dumps(updated_map, indent=2)
            st.success("✅ Rows added successfully!")
            st.download_button("Download updated JSON", updated_json, file_name="seatmap_updated.json")
        except Exception as e:
            st.error(f"❌ Error: {e}")
