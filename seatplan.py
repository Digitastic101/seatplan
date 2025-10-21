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
# Natural sort helper for seat labels
# -------------------------------------------------
def _natural_seat_key(seat_label: str) -> tuple:
    """Sort naturally: handles 'A1', 'A10', '1', '10', etc."""
    s = str(seat_label)
    # Letter(s) + digits, e.g. A12 / AA7
    m = re.match(r"^([A-Za-z]+)(\d+)$", s)
    if m:
        row, num = m.group(1), int(m.group(2))
        return (row.upper(), num, s)
    # Digits only, e.g. '12'
    m2 = re.match(r"^(\d+)$", s)
    if m2:
        return ("", int(m2.group(1)), s)
    # Fallback: keep original string as last key
    return (s.upper(), float("inf"), s)


# -------------------------------------------------
# Core helper – inserts rows keeping the user order
# and applying A⇄Z rule when there's no anchor
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
    rows_items = list(section.get("rows", {}).items())

    # Decide order of the *added* rows.
    # If there is no anchor (ref == "0") OR the anchor doesn't exist in the section,
    # we sort by row index and:
    #   - above  => Z→A
    #   - below  => A→Z
    ref_upper = str(ref_row_index).upper()
    anchor_exists = any(
        str(rdata.get("row_index", "")).upper() == ref_upper
        for _, rdata in rows_items
    )
    empty_or_anchorless = (not rows_items) or (ref_upper == "0") or (not anchor_exists)

    if empty_or_anchorless:
        new_rows_sorted = sorted(
            new_rows,
            key=lambda x: str(x.get("index", "")).upper(),
            reverse=(position == "above"),  # above => Z→A ; below => A→Z
        )
    else:
        # When anchoring to an existing row, respect the user's input order
        new_rows_sorted = new_rows

    # Build rows to insert (in the decided order)
    ordered_pairs = []
    for spec in new_rows_sorted:
        row_label = str(spec["index"]).upper()
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
                    "row_index": row_label,
                    "row_price": default_price,
                    "row_id": row_id,
                },
            )
        )

    updated_rows = OrderedDict()
    inserted = False

    # Insert relative to the anchor if it exists
    for rid, rdata in rows_items:
        if not inserted and (ref_upper == "0" or str(rdata.get("row_index", "")).upper() == ref_upper):
            if position == "above":
                for pid, pdata in ordered_pairs:
                    updated_rows[pid] = pdata
                if ref_upper != "0":
                    updated_rows[rid] = rdata
            else:  # below
                if ref_upper != "0":
                    updated_rows[rid] = rdata
                for pid, pdata in ordered_pairs:
                    updated_rows[pid] = pdata
            inserted = True
        else:
            updated_rows[rid] = rdata

    # If no anchor was matched at all, prepend/append in the already-decided order
    if not inserted:
        if position == "above":
            # Prepend
            prepend = OrderedDict((pid, pdata) for pid, pdata in ordered_pairs)
            updated_rows = OrderedDict(list(prepend.items()) + list(updated_rows.items()))
        else:
            # Append
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
    new_rows = OrderedDict()
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
# Delete any row that has exactly one seat (label-agnostic)
# -------------------------------------------------
def delete_rows_with_exactly_one_seat(
    seatmap: Dict, *, section_id: str
) -> Tuple[Dict, int]:
    """
    Delete any row that has exactly one seat, regardless of row_index or seat label.
    Returns (updated_map, deleted_count).
    """
    section = seatmap.get(section_id)
    if not section or "rows" not in section:
        return seatmap, 0

    updated = seatmap.copy()
    updated_section = section.copy()
    new_rows = OrderedDict()
    deleted = 0

    for rid, rdata in section["rows"].items():
        seats = rdata.get("seats", {})
        if isinstance(seats, dict) and len(seats) == 1:
            deleted += 1
            continue  # drop this row entirely
        new_rows[rid] = rdata

    updated_section["rows"] = new_rows
    updated[section_id] = updated_section
    return updated, deleted


# =================================================
# Streamlit UI
# =================================================
st.title("🎭 Seat Plan Adaptions")

uploaded_file = st.file_uploader("Upload your seatmap JSON", type="json")

# NOTE: numbers are fine; '0' means "section start / no anchor"
ref_row_letter = st.text_input(
    "Reference row label (e.g. 'B' or '10' — or '0' for section start)",
    value="A"
)
ref_seat_number = st.text_input("Seat number in that row (e.g. '17')", value="1")

section_id = None
seatmap = None

# Defaults to avoid UnboundLocal errors
do_reverse_rows = False
do_reverse_seats_master = False
rows_selected: List[str] = []
do_delete_lonely_first = False  # single-seat row deletion

if uploaded_file:
    seatmap = json.load(uploaded_file)

    # --------------------------------------------
    # Find candidate sections (forgiving + fallback)
    # --------------------------------------------
    matched_rows: List[Tuple[str, str]] = []
    ref_raw = (ref_row_letter or "").strip()
    ref_full = ref_raw.upper()
    base_letters_match = re.search(r"([A-Za-z]+)", ref_raw or "")
    base_letters = base_letters_match.group(1).upper() if base_letters_match else ""

    for sid, sdata in seatmap.items():
        rows = sdata.get("rows", {})
        if not rows:
            continue
        for rdata in rows.values():
            row_idx_raw = str(rdata.get("row_index", ""))
            row_idx_full = row_idx_raw.upper()
            row_idx_letters_match = re.search(r"([A-Za-z]+)$", row_idx_raw)
            row_idx_letters = row_idx_letters_match.group(1).upper() if row_idx_letters_match else ""

            # Match rules:
            # - '0' => always match section
            # - letters present in ref => match by letters
            # - otherwise (digits-only ref) => exact full match
            if (
                ref_full == "0"
                or (base_letters and row_idx_letters == base_letters)
                or (ref_full and not base_letters and row_idx_full == ref_full)
            ):
                align_code = sdata.get("align", "def")
                align_friendly = {"l": "Left", "r": "Right", "def": "Centre (default)"}.get(align_code, align_code)
                label = f"{sdata.get('section_name','(unnamed)')} · rows: {len(rows)} · align: {align_friendly} · ID: {sid}"
                matched_rows.append((label, sid))
                break

    # Fallback: list all sections if nothing matched
    if not matched_rows:
        for sid, sdata in seatmap.items():
            rows = sdata.get("rows", {})
            if not rows:
                continue
            align_code = sdata.get("align", "def")
            align_friendly = {"l": "Left", "r": "Right", "def": "Centre (default)"}.get(align_code, align_code)
            label = f"{sdata.get('section_name','(unnamed)')} · rows: {len(rows)} · align: {align_friendly} · ID: {sid}"
            matched_rows.append((label, sid))

    if not matched_rows:
        st.warning("No section matches that row/seat.")
    else:
        display_labels = [lbl for lbl, _ in matched_rows]
        label_choice = st.selectbox("Select section:", display_labels)
        section_id = dict(matched_rows)[label_choice]

        # Preview rows in this section
        rows_preview = []
        for r in seatmap[section_id]["rows"].values():
            letters = r.get("row_index", "")
            nums = [
                int(s["number"][len(str(letters)):])
                for s in r.get("seats", {}).values()
                if isinstance(s.get("number", ""), str)
                and s["number"][len(str(letters)) :].isdigit()
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

        # Optional: Relabel
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

        # Cleanup options
        with st.expander("Cleanup options"):
            do_delete_lonely_first = st.checkbox(
                "Delete any row that has exactly one seat",
                value=False,
                help="Ignores row letters and seat numbers; removes rows that contain only one seat."
            )

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
                letter = st.text_input(f"Row label #{i+1}", key=f"row_letter_{i}")
            with col2:
                first = st.number_input("First seat", 1, 999, 1, key=f"first_{i}")
            with col3:
                last = st.number_input("Last seat", 1, 999, 1, key=f"last_{i}")

            if letter:
                # Build seat sequence as typed
                if first <= last:
                    seat_numbers = list(range(first, last + 1))
                else:
                    seat_numbers = list(range(first, last - 1, -1))

                base_labels = [f"{str(letter).upper()}{n}" for n in seat_numbers]

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

                new_rows.append({"index": str(letter).upper(), "labels": base_labels})

        # -----------------------------
        # APPLY: update plan (rows + meta + direction + cleanup)
        # -----------------------------
        if uploaded_file and section_id:
            if st.button("💾 Update Plan"):
                try:
                    current = seatmap

                    # 1) If adding rows, insert them first (with A/Z rule when no anchor)
                    default_price = seatmap[section_id].get("price", seatmap[section_id].get("def_price", "85"))
                    if new_rows:
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

                    # 4) Cleanup: delete any single-seat rows (label-agnostic)
                    if do_delete_lonely_first:
                        current, deleted = delete_rows_with_exactly_one_seat(
                            current, section_id=section_id
                        )
                        st.info(f"Cleanup removed {deleted} single-seat row(s).")

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
