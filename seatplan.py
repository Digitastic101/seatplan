import streamlit as st
import json

st.title("🎭 Seat Cleaner")

uploaded_file = st.file_uploader("Upload your seatmap JSON file", type="json")

st.markdown("### 🎯 Seat Removal Rules")

num_rules = st.number_input("How many rules do you want to define?", min_value=1, max_value=10, value=1)

rules = []
for i in range(num_rules):
    with st.expander(f"Rule {i+1}"):
        section_name = st.text_input(f"Section name for Rule {i+1}", value="Stalls", key=f"section_{i}")
        row_letters = st.multiselect(f"Rows for Rule {i+1}", options=list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), default=["F", "G", "H"], key=f"rows_{i}")
        seat_limit = st.number_input(f"Remove seats up to number for Rule {i+1}", min_value=1, max_value=250, value=77, key=f"limit_{i}")
        rules.append({"section": section_name, "rows": row_letters, "limit": seat_limit})

if uploaded_file:
    seatmap = json.load(uploaded_file)
    removed_seats = []

    for rule in rules:
        section_name = rule["section"]
        row_letters = rule["rows"]
        seat_limit = rule["limit"]

        for section_id, section_data in seatmap.items():
            if section_data.get("section_name") == section_name and "rows" in section_data:
                for row_id, row_data in section_data["rows"].items():
                    if row_data.get("row_index") in row_letters:
                        seats = row_data.get("seats", {})
                        new_seats = {}
                        for sid, seat in seats.items():
                            try:
                                number = int(''.join(filter(str.isdigit, seat["number"])))
                                if number <= seat_limit:
                                    removed_seats.append({
                                        "section": section_name,
                                        "row": row_data.get("row_index"),
                                        "seat_number": seat["number"],
                                        "seat_id": sid
                                    })
                                    continue
                            except ValueError:
                                pass
                            new_seats[sid] = seat

                        row_data["seats"] = new_seats

    if removed_seats:
        st.success(f"Removed {len(removed_seats)} seats.")
        st.dataframe(removed_seats)
        cleaned_json = json.dumps(seatmap, indent=2)
        st.download_button("Download cleaned JSON", cleaned_json, file_name="cleaned_seatmap.json")
    else:
        st.info("No seats matched the removal rules.")
