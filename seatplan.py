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
    new_section = section.copy()
    new_section["rows"] = updated_rows
    new_seatmap[section_id] = new_section
    return new_seatmap

# -------------------------------------------------
# NEW helper – relabel multiple rows and their seats
# -------------------------------------------------

def relabel_rows(
    seatmap: Dict,
    *,
    section_id: str,
    target_row_letters: List[str],
    new_prefix: str
) -> Dict:
    """
    For each selected row, updates:
      - row_index: 'T' -> '(RV) T'  (prefix + original)
      - seats: 'T12' -> '(RV) T12'
    Only seats that start with the original row letters are changed.
    """
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
                if ref_row_letter == "0" or any(s["number"] == f"{ref_row_letter.upper()}{ref_seat_number}" for s in rdata["seats"].values()):
                    matched_rows.append((f"{sdata['section_name']} (rows: {len(sdata['rows'])})", sid))
                    break

    if not matched_rows:
        st.warning("No section matches that row/seat.")
    else:
        display_labels = [lbl for lbl, _ in matched_rows]
        label_choice = st.selectbox("Select section containing that seat:", display_labels)
        section_id = dict(matched_rows)[label_choice]

        rows_preview = []
        for r in seatmap[section_id]["rows"].values():
            letters = r["row_index"]
            nums = [int(s["number"][len(letters):]) for s in r["seats"].values()
                    if s["number"][len(letters):].isdigit()]
            if nums:
                rows_preview.append(f"{letters}{min(nums)}–{max(nums)}")
        st.markdown("**Rows in this section:** " + ", ".join(rows_preview))

        # ---------------------------------------------
        # OPTIONAL: Relabel existing rows + seat tags
        # ---------------------------------------------
        with st.expander("Optional: Relabel existing rows (e.g. add '(RV) ' prefix)"):
            # Build a list of available row letters in this section
            available_rows = []
            for r in seatmap[section_id]["rows"].values():
                if "row_index" in r:
                    available_rows.append(str(r["row_index"]))
            # Remove dups, keep stable alpha sort
            available_rows = sorted(dict.fromkeys(available_rows), key=lambda x: x.upper())

            col_a, col_b = st.columns([2, 3])
            with col_a:
                selected_rows = st.multiselect(
                    "Rows to change",
                    options=available_rows,
                    help="Pick one or more rows to relabel"
                )
            with col_b:
                new_prefix = st.text_input(
                    "Prefix to add",
                    value="(RV) ",
                    help="Applied to each selected row, e.g. '(RV) ' + T -> '(RV) T'"
                )

            if selected_rows:
                preview_samples = ", ".join([f"{new_prefix}{r}" for r in selected_rows[:3]])
                st.caption(f"Preview: {preview_samples}{'…' if len(selected_rows) > 3 else ''}")

            if st.button("Apply relabel to selected rows"):
                try:
                    updated = relabel_rows(
                        seatmap,
                        section_id=section_id,
                        target_row_letters=selected_rows,
                        new_prefix=new_prefix
                    )
                    st.session_state["updated_map"] = updated
                    st.success(f"Relabelled {len(selected_rows)} row(s).")
                except Exception as e:
                    st.error(str(e))

# Controls for inserting rows (stay outside the section block)
position = st.radio("Insert rows", ["above", "below"], horizontal=True)
num_rows = st.number_input("How many new rows to add?", 1, 10, 1)

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
        # Automatically determine order
        if first <= last:
            seat_numbers = list(range(first, last + 1))  # Ascending
        else:
            seat_numbers = list(range(first, last - 1, -1))  # Descending

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
                ano_label = st.text_input(
                    f"Anomaly label (#{j+1})",
                    key=f"ano_label_{i}_{j}"
                )
            if ano_label:
                anomalies.append((ano_between, ano_label))

        for ano_between, ano_label in sorted(anomalies, key=lambda x: x[0], reverse=True):
            if ano_between in seat_numbers:
                insertion_index = seat_numbers.index(ano_between) + 1
                base_labels.insert(insertion_index, ano_label)

        new_rows.append({"index": letter.upper(), "labels": base_labels})

if uploaded_file and section_id and new_rows:
    if st.button("➕ Insert Rows"):
        try:
            default_price = seatmap[section_id].get("price", "85")

            update = insert_rows(
                seatmap,
                section_id=section_id,
                ref_row_index=ref_row_letter,
                new_rows=new_rows,
                position=position,
                default_price=default_price
            )
            st.session_state["updated_map"] = update
            st.success("Rows inserted – download below 👇")
        except Exception as e:
            st.error(str(e))

if "updated_map" in st.session_state:
    js = json.dumps(st.session_state["updated_map"], indent=2)
    st.download_button("📥 Download updated JSON", js, "seatmap_updated.json")
