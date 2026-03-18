# Puzzle packet versions in `ramses.msgs`

Parsed `puzzle_packet` (7FFF) lines include `engine` and `parser` strings from ramses_rf.

**Finding (sample capture):** All **177** puzzle lines in `ramses.msgs` report the same pair:

- **engine:** `v0.51.4`
- **parser:** `v0.51.4`

So this capture shows **no version drift** over the logged session (multiple hours on 2025-11-15).

The live exporter records a row in `puzzle_version_events` only when that pair **first appears** or **changes** per gateway `src_id`.
