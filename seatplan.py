... (truncated previous content for brevity) ...

    anomaly_labels = []
    if letter and first <= last:
        seat_numbers = list(range(first, last + 1))
        base_labels = [f"{letter.upper()}{n}" for n in seat_numbers]

        # Allow multiple anomaly insertions
        num_anomalies = st.number_input(f"How many anomalies in Row #{i+1}?", 0, 5, 0, key=f"num_ano_{i}")
        anomalies = []
        for j in range(num_anomalies):
            col_a1, col_a2 = st.columns([2, 3])
            with col_a1:
                ano_between = st.number_input(
                    f"Insert anomaly between... (#{j+1})",
                    min_value=first,
                    max_value=last - 1,
                    key=f"ano_pos_{i}_{j}"
                )
            with col_a2:
                ano_label = st.text_input(
                    f"Anomaly label (#{j+1})",
                    key=f"ano_label_{i}_{j}"
                )
            if ano_label:
                anomalies.append((ano_between, ano_label))

        # Insert anomalies sorted by index
        for ano_between, ano_label in sorted(anomalies, key=lambda x: x[0], reverse=True):
            if ano_between in seat_numbers:
                insertion_index = seat_numbers.index(ano_between) + 1
                base_labels.insert(insertion_index, ano_label)

        new_rows.append({"index": letter.upper(), "labels": base_labels})

... (remainder unchanged) ...
