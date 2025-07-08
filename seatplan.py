import json
import uuid
from typing import List, Dict

def insert_rows(
    seatmap: Dict,
    *,
    section_name: str,
    ref_row_index: str,
    new_rows: List[Dict[str, List[int]]],
    position: str = "above",
    default_price: str = "85"
) -> Dict:
    """
    Insert rows into a seatmap dictionary.

    Args:
        seatmap (dict): The seatmap JSON structure (already loaded).
        section_name (str): e.g. "Stalls" — name of section to modify.
        ref_row_index (str): Row index (e.g. 'L') where new rows will be inserted relative to.
        new_rows (list): List of row specs, e.g. [{"index": "M", "numbers": [16,17,18,19]}]
        position (str): "above" or "below" — position relative to ref_row_index.
        default_price (str): Price to assign to all new seats.

    Returns:
        dict: A new seatmap dict with added rows.
    """

    # Locate the correct section by name
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


# === Example usage ===
if __name__ == "__main__":
    with open("seatmap_data.json") as f:
        seatmap_data = json.load(f)

    updated_map = insert_rows(
        seatmap_data,
        section_name="Stalls",
        ref_row_index="L",
        position="above",
        new_rows=[
            {"index": "M", "numbers": [16, 17, 18, 19]},
            {"index": "N", "numbers": [20, 21]}
        ]
    )

    with open("seatmap_updated.json", "w") as f:
        json.dump(updated_map, f, indent=2)

    print("✅ Rows inserted successfully.")
