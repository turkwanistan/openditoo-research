# Implementation Spec

## Canvas

- Resolution: **16×16**
- Color model: **RGB222** (per-channel values limited to 0, 85, 170, 255)
- Background: black

## Column mapping

Each MCP occupies a 5-pixel-wide slot.

- **x = 0..4**: Lab → `L` + mushroom
- **x = 5..9**: OptiPlex MCP → `O` + bunny
- **x = 10..14**: WSL MCP → `W` + skull
- **x = 15**: spare / empty

## Vertical layout (approved baseline)

- **rows 0..2**: activity animation zone
- **rows 3..4**: spacer
- **rows 5..9**: identity letters
- **row 10**: blank divider
- **rows 11..15**: 5×5 icons

## Identity glyphs

Use the exact extracted logical glyphs:

### L
.#...
.#...
.#...
.#...
.###.

### O
.##..
#..#.
#..#.
#..#.
.##..

### W
#...#
#...#
#.#.#
##.##
#...#

## Status meanings

Normal status colors:

- **green** = last traffic < 5 min
- **yellow** = last traffic 5–20 min
- **red** = last traffic > 20 min
- **grey** = idle / disconnected / no recent data

## Icon color behavior

- **Mushroom**: recolor cap family to status color
- **Bunny**: recolor eye pixels only
- **Skull**: recolor the 2 eye pixels only, preserve the nose and all other pixels

## Activity behavior (preferred)

When a packet event occurs for one MCP column:

1. animate the **top crown** in that column;
2. simultaneously recolor the active column's:
   - identity letter
   - icon status accent
3. use the same blue pulse family as the crown;
4. revert to the normal status color when the animation ends.

## Blue pulse family used in the mockup

- stage 0 → cyan `(0,255,255)`
- stage 1 → blue `(0,170,255)`
- stage 2 → light blue `(85,170,255)`
- stage 3 → cyan `(0,255,255)`

This does not need to be mathematically identical as long as the visible behavior matches the mockups.

## Deliverables for the implementor

The final implementation should support:

- static state rendering;
- activity animation per MCP column;
- automatic return to state color after animation;
- hookable external updates from MCP activity events.

