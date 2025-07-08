import json
import uuid
from typing import List, Dict
import streamlit as st

def insert_rows(
    seatmap: Dict,
    *,
    section_name: str,
    ref_row_index: str,
    new_rows: List[Dict[str, List[int]]],
    position: str = "above",
    default_price: str = "85"
) -> Dict:
    section_id, section = next(
        (sid, sdata) for sid, sdata in seatmap.items()
        if sdata.get("section_name") == section_name and "rows" in sdata
    )

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

if uploaded_file:
    seatmap = json.load(uploaded_file)
    section_names = [s["section_name"] for s in seatmap.values() if "rows" in s]
    section = st.selectbox("Select section", options=section_names)

    ref_row = st.text_input("Reference row index (e.g. 'L')", value="L")
    position = st.radio("Insert rows", options=["above", "below"])
    num_rows = st.number_input("How many new rows to add?", min_value=1, max_value=10, value=1)

    new_rows = []
    for i in range(num_rows):
        col1, col2 = st.columns(2)
        with col1:
            letter = st.text_input(f"Row letter #{i+1}", key=f"letter_{i}")
        with col2:
            nums = st.text_input(f"Seat numbers (comma separated)", key=f"nums_{i}")
        if letter and nums:
            try:
                number_list = [int(n.strip()) for n in nums.split(",") if n.strip()]
                new_rows.append({"index": letter.upper(), "numbers": number_list})
            except ValueError:
                st.error(f"Invalid seat numbers for row {letter}.")

    if st.button("➕ Insert Rows") and new_rows:
        try:
            updated_map = insert_rows(
                seatmap,
                section_name=section,
                ref_row_index=ref_row.upper(),
                new_rows=new_rows,
                position=position
            )
            updated_json = json.dumps(updated_map, indent=2)
            st.success("✅ Rows added successfully!")
            st.download_button("Download updated JSON", updated_json, file_name="seatmap_updated.json")
        except Exception as e:
            st.error(f"❌ Error: {e}")
