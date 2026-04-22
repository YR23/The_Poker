from pathlib import Path

from reader_utils import (
	assign_table_positions,
	capture_screen,
	extract_player_sections,
	process_positions_parallel,
)


if __name__ == "__main__":
	dcim_dir = Path(__file__).resolve().parent / "DCIM"
	full_screenshot = dcim_dir / "screen.png"

	# Step 1: Capture fresh screenshot.
	capture_screen(full_screenshot, display_index=2)
	print(f"Step 1 complete: {full_screenshot}")

	extract_player_sections(dcim_dir)

	# Step 6: Process per-position pipeline in parallel (organize + OCR).
	players_dir = dcim_dir / "players"
	print("\nStep 6: Parallel per-position processing...")
	all_positions = [
		"top_left",
		"top_middle",
		"top_right",
		"bottom_left",
		"bottom_middle",
		"bottom_right",
	]
	results = process_positions_parallel(players_dir, all_positions, max_workers=6)

	warning = assign_table_positions(results)
	if warning:
		print(f"\nWarning: {warning}")

	print("\nStep 7: Assigned table positions...")
	for position in all_positions:
		role = str(results[position].get("table_position", "")) or "—"
		print(f"  {position}: {role}")