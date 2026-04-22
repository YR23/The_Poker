from pathlib import Path

from reader_utils import (
	assign_table_positions,
	capture_screen,
	extract_player_sections,
	extract_player_text,
	organize_player_sections,
)


if __name__ == "__main__":
	dcim_dir = Path(__file__).resolve().parent / "DCIM"
	full_screenshot = dcim_dir / "screen.png"

	# Step 1: Capture fresh screenshot.
	# capture_screen(full_screenshot, display_index=2)
	print(f"Step 1 complete: {full_screenshot}")

	extract_player_sections(dcim_dir)

	# Step 6: Organize player sections for all bottom positions.
	players_dir = dcim_dir / "players"
	print("\nStep 6: Organizing player sections...")
	all_positions = [
		"top_left",
		"top_middle",
		"top_right",
		"bottom_left",
		"bottom_middle",
		"bottom_right",
	]
	organize_player_sections(players_dir, positions=all_positions)

	# Step 7: Extract text from name and pot_size images for all positions.
	print("\nStep 7: Extracting text from split images...")
	results = {}
	for position in all_positions:
		results[position] = extract_player_text(players_dir, position)

	warning = assign_table_positions(results)
	if warning:
		print(f"\nWarning: {warning}")

	print("\nStep 8: Assigned table positions...")
	for position in all_positions:
		role = str(results[position].get("table_position", "")) or "—"
		print(f"  {position}: {role}")