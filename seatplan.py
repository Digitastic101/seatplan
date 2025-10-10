import json
import uuid
from typing import List, Dict
import streamlit as st

# ===============================
# Helpers (no alignment touched)
# ===============================

def reverse_rows_in_section(seatmap: Dict, section_id: str) -> Dict:
    """Reverse current row order in a section. Leaves all fields as-is."""
    section = seatmap.get(section_id)
    if not section or "rows" not in section:
        return seatmap
    items = list(section["rows"].items())
    items.reverse()
    new_rows = {rid: rdata for rid, rdata in items}
    new_map = seatmap.copy()
    new_sec = section.copy()
    new_sec["rows"] = new_rows
    new_map[section_id] = new_sec
    return new_map


def insert_rows(
    seatmap: Dict,
    *,
    section_id: str,
    ref_row_index: str,                   # e.g. 'A' or '0' for section start
    new_rows: List[Dict[str, List[str]]], # [{"index":"T","labels":["T1","T2",...]}]
    position: str = "above",
    default_price: str = "85",
) -> Dict:
    """Insert new rows above/below a reference row (or at start if ref_row_index=='0')."""
    section = seatmap[section_id]
    rows_items = list(section["rows"].items())

    ordered_pairs = []
    source_iter = new_rows if position == "below" else reversed(new_rows)

    for spec in source_iter:
        row_letter = spec["index"].upper()
        labels = spec["labels"]
        row_id = f"r{uuid.uuid4().hex[:6]}"

        seats = {}
        for label in labels:
            sid = f"s{uuid.uuid4().hex[:6]}"
            seats[sid] = {
                "id": sid,
                "number": label,
                "price": default_price,
                "status": "av",
                "handicap": "no",
            }

        ordered_pairs.append((row_id, {
            "seats": seats,
            "row_index": row_letter,
            "row_price": default_price,
            "row_id": row_id,
        }))

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

    new_map = seatmap.copy()
    new_sec = section.copy()
    new_sec["rows"] = updated_rows
    new_map[section_id] = new_sec
    return new_map


def relabel_rows(
    seatmap: Dict,
    *,
    section_id: str,
    target_row_letters: List[str],
    new_prefix: str
) -> Dict:
    """
    Add a prefix to selected rows' labels:
      - row_index: 'T' -> '(RV) T'
      - seats: 'T12' -> '(RV) T12'
    """
    if not target_row_letters:
        return seatmap

    targets_upper = {t.upper() for t in target_row_letters}
    section = seatmap.get(section_id)
    if not section or "rows" not in section:
        return seatmap

    new_map = seatmap.copy()
    new_sec = section.copy()
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

            new_rows[rid] = {**rdata, "row_index": new_row_label, "seats": new_seats}
        else:
            new_rows[rid] = rdata

    new_sec["rows"] = new_rows
    new_map[section_id] = new_sec
    return new_map


# ===============================
# Streamlit UI (no alignment UI)
# ===============================

st.title("🎭 Update Seat Plan (alignment untouched)")

uploaded_file = st.file_uploader("Upload seatmap JSON", type="json")
seatmap = None

if uploaded_file:
    seatmap = json.load(uploaded_file)

if seatmap:
    # Pick a section
    st.subheader("Select section")
    options = []
    for sid, sdata in seatmap.items():
        name = sdata.get("section_name", sid)
        nrows = len(sdata.get("rows", {}))
        options.append(f"{name}  •  {sid}  •  {nrows} rows")
    choice = st.selectbox("Section", options=options)
    section_id = choice.split("•")[-2].strip()

    sec = seatmap[section_id]

    st.write("---")
    # Section name
    new_name = st.text_input("Section name", value=sec.get("section_name", ""))

    # Tiny read-only peek so you can see what's currently stored (we don't touch it)
    st.caption(f"(Info) Current align field in file: {sec.get('align', '(none)')}")

    st.write("---")
    # Reverse rows
    reverse_flag = st.checkbox("Reverse current row order (optional)", value=False)

    st.write("---")
    # Relabel rows (optional)
    with st.expander("Optional: Relabel existing rows (add a prefix)"):
        available_rows = sorted(
            {r["row_index"] for r in sec.get("rows", {}).values()},
            key=lambda x: str(x).upper()
        )
        col_a, col_b = st.columns([2, 3])
        with col_a:
            selected_rows = st.multiselect("Rows to change", options=available_rows)
        with col_b:
            new_prefix = st.text_input("Prefix to add", value="(RV) ")
        relabel_requested = st.checkbox("Apply relabel on save", value=False)

    st.write("---")
    # Insert rows (optional)
    st.subheader("Add rows (optional)")
    ref_row_letter = st.text_input("Reference row letter (or '0' for section start)", value="0")
    position = st.radio("Insert position", ["above", "below"], horizontal=True)
    num_rows = st.number_input("How many new rows?", 0, 10, 0)

    new_rows_specs = []
    for i in range(int(num_rows)):
        st.markdown(f"**Row #{i+1}**")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            letter = st.text_input(f"Row letter #{i+1}", key=f"row_letter_{i}")
        with c2:
            first = st.number_input("First seat", 1, 999, 1, key=f"first_{i}")
        with c3:
            last = st.number_input("Last seat", 1, 999, 1, key=f"last_{i}")

        labels = []
        if letter:
            rng = range(first, last + 1) if first <= last else range(first, last - 1, -1)
            labels = [f"{letter.upper()}{n}" for n in rng]

        nano = st.number_input(f"Anomalies in Row #{i+1}", 0, 5, 0, key=f"ano_n_{i}")
        anomalies = []
        for j in range(nano):
            a1, a2 = st.columns([2, 3])
            with a1:
                between = st.number_input(f"Insert after seat number (#{j+1})", 1, 999, key=f"ano_pos_{i}_{j}")
            with a2:
                label = st.text_input(f"Anomaly label (#{j+1})", key=f"ano_lab_{i}_{j}")
            if label:
                anomalies.append((between, label))
        # apply anomalies
        for between, lab in sorted(anomalies, key=lambda x: x[0], reverse=True):
            try:
                idx = [int(s[len(letter):]) for s in labels if s[len(letter):].isdigit()].index(between)
                labels.insert(idx + 1, lab)
            except Exception:
                pass

        if letter:
            new_rows_specs.append({"index": letter.upper(), "labels": labels})

    st.write("---")
    if st.button("💾 Save changes"):
        updated = seatmap.copy()
        cur = updated[section_id].copy()

        # Update name only (alignment is intentionally untouched)
        if new_name.strip():
            cur["section_name"] = new_name.strip()
        updated[section_id] = cur

        # Reverse rows if requested
        if reverse_flag:
            updated = reverse_rows_in_section(updated, section_id)

        # Relabel selected rows if requested
        if relabel_requested and selected_rows:
            updated = relabel_rows(
                updated,
                section_id=section_id,
                target_row_letters=selected_rows,
                new_prefix=new_prefix
            )

        # Insert rows if provided
        if new_rows_specs:
            default_price = cur.get("price", "85")
            updated = insert_rows(
                updated,
                section_id=section_id,
                ref_row_index=ref_row_letter,
                new_rows=new_rows_specs,
                position=position,
                default_price=default_price
            )

        st.session_state["updated_map"] = updated
        seatmap = updated
        st.success("Saved. Download below.")

    # Download
    if "updated_map" in st.session_state:
        js = json.dumps(st.session_state["updated_map"], indent=2)
        st.download_button("📥 Download updated JSON", js, "seatmap_updated.json")
