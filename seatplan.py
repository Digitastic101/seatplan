        # ---------------------------------------------
        # OPTIONAL: Relabel existing rows + seat tags
        # ---------------------------------------------
        with st.expander("Optional: Relabel existing rows (e.g. add '(RV) ' prefix)"):
            # Build a list of available row letters in this section
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
