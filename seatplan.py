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
            else:  # below
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
    """Sort naturally: A1 < A2 < A10 (not A1, A10, A2)."""
    m = re.match(r"^([A-Za-z]+)(\d+)$", str(seat_label))
    if not m:
        return (seat_label, 0, seat_label)
    row, num = m.group(1), int(m.group(2))
    return (row.upper(), num, seat_label)

def reverse_section_rows_order(seatmap: Dict, *, section_id: str) -> Dict:
    """Reverse row order for the whole section."""
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

def reverse_section_seat_order_selective(
    seatmap: Dict, *, section_id: str, rows_to_reverse: List[str]
) -> Dict:
    """Reverse seat order only for specified row labels (labels themselves unchanged)."""
    if not rows_to_reverse:
        return seatmap

    targets = {r.upper() for r in rows_to_reverse}
    section = seatmap.get(section_id)
    if not section or "rows" not in section:
        return seatmap

    updated = seatmap.copy()
    updated_section = section.copy()
    new_rows = OrderedDict()

    for rid, rdata in section["rows"].items():
        row_label = str(rdata.get("row_index", "")).upper()
        if row_label in targets:
            seats_items = list(rdata.get("seats", {}).items())
            seats_items_sorted = sorted(
                seats_items, key=lambda kv: _natural_seat_key(kv[1].get("number", ""))
            )
            seats_items_reversed = list(reversed(seats_items_sorted))
            new_seats = OrderedDict((sid, sdata) for sid, sdata in seats_items_reversed)
            new_rows[rid] = {**rdata, "seats": new_seats}
        else:
            new_rows[rid] = rdata

    updated_section["rows"] = new_rows
    updated[section_id] = updated_section
    return updated


# -------------------------------------------------
# NEW: robust delete of rows that only contain the "first" seat (A1/B1/etc.)
# -------------------------------------------------
def _extract_base_row_letters(row_index: str) -> str:
    """
    From a row_index like 'A', '(RV) A', 'VIP A', return the trailing letters token, e.g. 'A'.
    """
    m = re.search(r"([A-Za-z]+)$", str(row_index))
    return m.group(1).upper() if m else str(row_index).strip().upper()

def _parse_seat_label(label: str) -> Tuple[str, int]:
    """
    Parse 'A1', 'A01' -> ('A', 1). Returns (letters.upper(), number) or (label, -1) if not parseable.
    """
    m = re.match(r"^\s*([A-Za-z]+)\s*0*(\d+)\s*$", str(label))
    if not m:
        return (str(label).strip().upper(), -1)
    return (m.group(1).upper(), int(m.group(2)))

def delete_rows_where_only_first_seat(
    seatmap: Dict, *, section_id: str, rows_filter: List[str] = None
) -> Tuple[Dict, int]:
    """
    Remove any row that has exactly one seat and that seat corresponds to '<base_row_letters>1'.
    Returns (updated_seatmap, deleted_count).
    """
    section = seatmap.get(section_id)
    if not section or "rows" not in section:
        return seatmap, 0

    rows_filter_upper = {r.upper() for r in rows_filter} if rows_filter else None

    updated = seatmap.copy()
    updated_section = section.copy()
    new_rows = OrderedDict()
    deleted = 0

    for rid, rdata in section["rows"].items():
        row_label_raw = str(rdata.get("row_index", ""))
        base_letters = _extract_base_row_letters(row_label_raw)

        if rows_filter_upper is not None and base_letters not in rows_filter_upper and row_label_raw.upper() not in rows_filter_upper:
            new_rows[rid] = rdata
            continue

        seats_dict = rdata.get("seats", {})
        if len(seats_dict) == 1:
            _, only_sdata = next(iter(seats_dict.items()))
            seat_letters, seat_num = _parse_seat_label(only_sdata.get("number", ""))
            if seat_letters == base_letters and seat_num == 1:
                deleted += 1
                continue  # skip -> delete this row

        new_rows[rid] = rdata

    updated_section["rows"] = new_rows
    updated[section_id] = updated_section
    return updated, deleted


# =================================================
# Streamlit UI
# =================================================
st.title("🎭 Seat Plan Adaptions")

uploaded_file = st.file_uploader("Upload your seatmap JSON", type="json")

ref_row_letter = st.text_input(
    "Reference row letter (e.g. 'B' – or '0' for section start)", value="A"
)
ref_seat_number = st.text_input("Seat number in that row (e.g. '17')", value="1")

section_id = None
seatmap = None

# Defaults to avoid UnboundLocal errors
do_reverse_rows = False
do_reverse_seats_master = False
rows_selected: List[str] = []
do_delete_lonely_first = False  # NEW default

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
                    str(s.get("number", "")).upper() == f"{ref_row_letter.upper()}{ref_seat_number}".upper()
                    for s in rdata["seats"].values()
                ):
                    # Friendly align label for the chooser
                    align_code = sdata.get("align", "def")
                    align_friendly = {"l": "Left", "r": "Right", "def": "Centre (default)"}\
                        .get(align_code, align_code)
                    label = f"{sdata.get('section_name','(unnamed)')} · rows: {len(sdata['rows'])} · align: {align_friendly}"
                    matched_rows.append((label, sid))
                    break

    if not matched_rows:
        st.warning("No section matches that row/seat.")
    else:
        display_labels = [lbl for lbl, _ in matched_rows]
        label_choice = st.selectbox("Select section containing that seat:", display_labels)
        section_id = dict(matched_rows)[label_choice]

        # Preview rows in this section
        rows_preview = []
        for r in seatmap[section_id]["rows"].values():
            letters = str(r.get("row_index", ""))
            base_letters = _extract_base_row_letters(letters)
            nums = [
                # show numeric range only for parseable labels matching this row's base letters
                int(re.match(r"^\s*[A-Za-z]+\s*0*(\d+)\s*$", s.get("number","")).group(1))
                for s in r["seats"].values()
                if re.match(r"^\s*([A-Za-z]+)\s*0*(\d+)\s*$", s.get("number","")) and
                   _parse_seat_label(s.get("number",""))[0] == base_letters
            ]
            if nums:
                rows_preview.append(f"{letters}{min(nums)}–{max(nums)}")
        st.markdown("**Rows in this section:** " + (", ".join(rows_preview) or "(none)"))

        # Section settings (name + align)
        st.subheader("Section settings")
        current_name = seatmap[section_id].get("section_name", "")
        current_align = seatmap[section_id].get("align", "def")

        align_labels = {"l": "Left", "r": "Right", "def": "Centre (default)"}
        align_options = list(align_labels.keys())
        align_display = [align_labels[a] for a in align_options]

        col_sn, col_al = st.columns([3, 1])
        with col_sn:
            edited_name = st.text_input("Section name", value=current_name)
        with col_al:
            selected_index = align_options.index(current_align) if current_align in align_options else 2
            display_choice = st.selectbox(
                "Align", align_display, index=selected_index,
                help="Where this section sits in the auditorium view."
            )
            edited_align = align_options[align_display.index(display_choice)]

        st.caption("Tip: Left / Right / Centre = seating alignment within the plan.")

        # Optional relabel
        with st.expander("Optional: Relabel existing rows (e.g. add '(RV) ' prefix)"):
            available_rows = []
            for r in seatmap[section_id]["rows"].values():
                if "row_index" in r:
                    available_rows.append(str(r["row_index"]))
            available_rows = sorted(dict.fromkeys(available_rows), key=lambda x: x.upper())

            col_a, col_b = st.columns([2, 3])
            with col_a:
                selected_rows = st.multiselect(
                    "Rows to change", options=available_rows,
                    help="Pick one or more rows to relabel",
                )
            with col_b:
                new_prefix = st.text_input(
                    "Prefix to add", value="(RV) ",
                    help="Applied to each selected row, e.g. '(RV) ' + T -> '(RV) T'",
                )

            if selected_rows:
                preview_samples = ", ".join([f"{new_prefix}{r}" for r in selected_rows[:3]])
                st.caption(f"Preview: {preview_samples}{'…' if len(selected_rows) > 3 else ''}")

            if st.button("Apply relabel to selected rows"):
                try:
                    seatmap = relabel_rows(
                        seatmap, section_id=section_id,
                        target_row_letters=selected_rows, new_prefix=new_prefix,
                    )
                    st.session_state["updated_map"] = seatmap
                    st.success(f"Relabelled {len(selected_rows)} row(s).")
                except Exception as e:
                    st.error(str(e))

        # Direction options (apply on save)
        with st.expander("Fix direction for this section"):
            row_ids = list(seatmap[section_id]["rows"].keys())
            row_labels = [seatmap[section_id]["rows"][rid].get("row_index", "") for rid in row_ids]
            if row_labels:
                st.caption(f"Current row order: {row_labels[0]} … {row_labels[-1]}")

            sample_row_id = row_ids[0] if row_ids else None
            if sample_row_id:
                r = seatmap[section_id]["rows"][sample_row_id]
                seat_labels = [s["number"] for s in r.get("seats", {}).values()]
                seat_labels_sorted = sorted(seat_labels, key=_natural_seat_key)
                if seat_labels_sorted:
                    st.caption(f"Sample seat direction (row {r.get('row_index','')}): {seat_labels_sorted[0]} … {seat_labels_sorted[-1]}")

            col_dir1, col_dir2 = st.columns(2)
            with col_dir1:
                do_reverse_rows = st.checkbox(
                    "Reverse **row order** in this section", value=False,
                    help="Flips top↔bottom (or near↔far) order of rows. Applied on save."
                )
            with col_dir2:
                do_reverse_seats_master = st.checkbox(
                    "Reverse seat order **per row**", value=False,
                    help="Flips left↔right order; choose rows below. Applied on save."
                )

            rows_in_section = [seatmap[section_id]["rows"][rid].get("row_index", "") for rid in row_ids]
            rows_in_section = [str(x) for x in rows_in_section]

            rows_selected = []
            if do_reverse_seats_master and rows_in_section:
                st.markdown("**Rows to reverse (untick any you *don’t* want changed):**")
                cols = st.columns(4)
                for i, row_label in enumerate(rows_in_section):
                    with cols[i % 4]:
                        chk = st.checkbox(row_label, value=True, key=f"rev_row_{row_label}")
                        if chk:
                            rows_selected.append(row_label)

            st.caption("Labels (e.g., A1, A2) are left unchanged; this fixes visual direction without renumbering.")

        # NEW: Cleanup options (independent)
        with st.expander("Cleanup options"):
            do_delete_lonely_first = st.checkbox(
                "Delete rows that only contain the first seat (e.g., row A with just A1)",
                value=False,
                help="If a row has exactly one seat and its label corresponds to RowLetters + 1, delete that entire row."
            )

            # Independent one-click action
            if st.button("🧹 Apply cleanup now"):
                try:
                    updated_map, deleted = delete_rows_where_only_first_seat(
                        seatmap, section_id=section_id
                    )
                    st.session_state["updated_map"] = updated_map
                    st.success(f"Deleted {deleted} row(s) that only contained the first seat.")
                except Exception as e:
                    st.error(str(e))

        # -----------------------------
        # Add rows  (NO reverse toggles here)
        # -----------------------------
        st.subheader("Add rows")
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
                # Build seat sequence as typed (no "reverse new rows" UI anymore)
                if first <= last:
                    seat_numbers = list(range(first, last + 1))
                else:
                    seat_numbers = list(range(first, last - 1, -1))

                base_labels = [f"{letter.upper()}{n}" for n in seat_numbers]

                num_anomalies = st.number_input(
                    f"How many anomalies in Row #{i+1}?",
                    0, 5, 0, key=f"num_ano_{i}"
                )
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

        # -----------------------------
        # APPLY: update plan (rows + meta + direction + cleanup)
        # -----------------------------
        if uploaded_file and section_id:
            if st.button("💾 Update Plan"):
                try:
                    current = seatmap

                    # 1) If adding rows, insert them first
                    if new_rows:
                        default_price = seatmap[section_id].get("price", seatmap[section_id].get("def_price", "85"))
                        current = insert_rows(
                            current,
                            section_id=section_id,
                            ref_row_index=ref_row_letter,
                            new_rows=new_rows,
                            position=position,
                            default_price=default_price,
                        )

                    # 2) Apply meta changes (name + align)
                    current = update_section_meta(
                        current,
                        section_id=section_id,
                        new_name=edited_name,
                        new_align=edited_align,
                    )

                    # 3) Apply direction fixes (affects newly added rows too)
                    if do_reverse_rows:
                        current = reverse_section_rows_order(current, section_id=section_id)
                    if do_reverse_seats_master:
                        current = reverse_section_seat_order_selective(
                            current, section_id=section_id,
                            rows_to_reverse=rows_selected or []
                        )

                    # 4) Cleanup: delete rows that only have '<row>1'
                    if do_delete_lonely_first:
                        current, deleted = delete_rows_where_only_first_seat(
                            current, section_id=section_id
                        )
                        st.info(f"Cleanup removed {deleted} row(s).")

                    st.session_state["updated_map"] = current
                    st.success("Plan updated – download below 👇")
                except Exception as e:
                    st.error(str(e))

# -----------------------------
# Download the updated JSON
# -----------------------------
if "updated_map" in st.session_state:
    js = json.dumps(st.session_state["updated_map"], indent=2)
    st.download_button("📥 Download updated JSON", js, "seatmap_updated.json")
