# pyright: basic
"""PROTOTYPE — throwaway. Derive embeddable web assets from the final raster art.

Round 3 (ticket 16): the scene is ONE tall image (sky -> hills -> waterline ->
underwater); the underwater zone gains a concrete floor band and a dehumidifier.
Reads assets/ and writes assets/derived/:

- tall-scene.webp — opaque scene, recompressed at native size.
- floor-strip.webp — the concrete band cropped out of floor-strip.png and made
  horizontally seamless (wrap-crossfade) so it can repeat-x full-bleed.
- dehumidifier.webp — keyed via edge-connected flood fill (NOT the global white
  un-blend: the body itself is white), with a feathered rim and the soft baked
  shadow converted to translucent black in the bottom shadow zone.
- goldfish.webp, dragonfly.webp — white-background cutouts keyed to true alpha
  (un-blend white), unchanged from round 2.

Run from the repo root:

    uv run --with pillow python prototypes/site-redesign-mockups/process_assets.py
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
DERIVED = ASSETS / "derived"

CUTOUTS = {"goldfish.png": 640, "dragonfly.png": 512}
FLOOR_CROP_TOP = 500  # band starts at y=508; keep the bevel highlight
FLOOR_WRAP_OVERLAP = 128
DEHUMIDIFIER_MAX_WIDTH = 640
STALE = ["sky.webp", "waterline.webp", "grass.webp", "check-grass.png"]


def resized(image: Image.Image, max_width: int) -> Image.Image:
    if image.width <= max_width:
        return image
    height = round(image.height * max_width / image.width)
    return image.resize((max_width, height), Image.LANCZOS)


def unblend_white(image: Image.Image) -> Image.Image:
    """Invert 'composited over white': recover colour + alpha."""
    rgb = image.convert("RGB")
    pixels = rgb.load()
    out = Image.new("RGBA", rgb.size)
    out_pixels = out.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            r, g, b = pixels[x, y]
            alpha = 255 - min(r, g, b)
            if alpha < 6:  # kill compression-noise haze around the subject
                out_pixels[x, y] = (0, 0, 0, 0)
                continue
            scale = 255 / alpha
            out_pixels[x, y] = (
                min(255, round((r - (255 - alpha)) * scale)),
                min(255, round((g - (255 - alpha)) * scale)),
                min(255, round((b - (255 - alpha)) * scale)),
                alpha,
            )
    return out


def horizontally_seamless(image: Image.Image, overlap: int) -> Image.Image:
    """Wrap-crossfade: blend the right edge onto the left so repeat-x never seams."""
    width = image.width - overlap
    base = image.crop((0, 0, width, image.height)).convert("RGB")
    tail = image.crop((width, 0, image.width, image.height)).convert("RGB")
    mask = Image.new("L", (overlap, image.height))
    mask_pixels = mask.load()
    for x in range(overlap):
        alpha = round(255 * (1 - x / overlap))
        for y in range(image.height):
            mask_pixels[x, y] = alpha
    head = Image.composite(tail, base.crop((0, 0, overlap, image.height)), mask)
    base.paste(head, (0, 0))
    return base


def key_product_shot(image: Image.Image) -> Image.Image:
    """Key a product shot off its white background without touching interior whites.

    1. Flood-fill from the borders through near-white pixels -> transparent.
    2. Feather a 2px rim of the remaining foreground via un-blend (kills the
       white fringe, keeps antialiased edges soft).
    3. In the bottom shadow zone, convert bright neutral pixels (the soft baked
       contact shadow) to translucent black via the same un-blend.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()

    background = [[False] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()

    def near_white(x: int, y: int) -> bool:
        r, g, b = pixels[x, y]
        return min(r, g, b) >= 246

    for x in range(width):
        for y in (0, height - 1):
            if near_white(x, y) and not background[y][x]:
                background[y][x] = True
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if near_white(x, y) and not background[y][x]:
                background[y][x] = True
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and not background[ny][nx] and near_white(nx, ny):
                background[ny][nx] = True
                queue.append((nx, ny))

    rim = [[False] * width for _ in range(height)]
    for _ in range(2):
        additions = []
        for y in range(height):
            for x in range(width):
                if background[y][x] or rim[y][x]:
                    continue
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < width and 0 <= ny < height and (background[ny][nx] or rim[ny][nx]):
                        additions.append((x, y))
                        break
        for x, y in additions:
            rim[y][x] = True

    shadow_top = round(height * 0.78)
    out = Image.new("RGBA", rgb.size)
    out_pixels = out.load()
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if background[y][x]:
                out_pixels[x, y] = (0, 0, 0, 0)
                continue
            minimum = min(r, g, b)
            chroma = max(r, g, b) - minimum
            soften = rim[y][x] or (y >= shadow_top and chroma <= 14 and minimum >= 190)
            if not soften:
                out_pixels[x, y] = (r, g, b, 255)
                continue
            alpha = 255 - minimum
            if alpha < 6:
                out_pixels[x, y] = (0, 0, 0, 0)
                continue
            scale = 255 / alpha
            out_pixels[x, y] = (
                min(255, round((r - (255 - alpha)) * scale)),
                min(255, round((g - (255 - alpha)) * scale)),
                min(255, round((b - (255 - alpha)) * scale)),
                alpha,
            )
    return out


def save(image: Image.Image, stem: str, quality: int) -> None:
    target = DERIVED / f"{stem}.webp"
    image.save(target, "WEBP", quality=quality, method=6)
    print(f"{target.name}: {image.width}x{image.height}, {target.stat().st_size / 1024:.0f} KB")


def eyeball_check(stem: str, backdrop: tuple[int, int, int, int]) -> None:
    cutout = Image.open(DERIVED / f"{stem}.webp").convert("RGBA")
    board = Image.new("RGBA", cutout.size, backdrop)
    board.alpha_composite(cutout)
    board.convert("RGB").save(DERIVED / f"check-{stem}.png")


def main() -> None:
    DERIVED.mkdir(exist_ok=True)
    for name in STALE:
        (DERIVED / name).unlink(missing_ok=True)

    scene = Image.open(ASSETS / "tall-scene.png").convert("RGB")
    save(scene, "tall-scene", quality=80)

    floor = Image.open(ASSETS / "floor-strip.png").convert("RGB")
    floor = floor.crop((0, FLOOR_CROP_TOP, floor.width, floor.height))
    save(horizontally_seamless(floor, FLOOR_WRAP_OVERLAP), "floor-strip", quality=80)

    dehumidifier = key_product_shot(Image.open(ASSETS / "dehumidifier.png"))
    save(resized(dehumidifier, DEHUMIDIFIER_MAX_WIDTH), "dehumidifier", quality=82)
    eyeball_check("dehumidifier", (7, 58, 88, 255))  # over deep underwater blue

    for name, max_width in CUTOUTS.items():
        image = unblend_white(resized(Image.open(ASSETS / name), max_width))
        save(image, Path(name).stem, quality=78)
        eyeball_check(Path(name).stem, (86, 178, 229, 255))  # over mid-sky blue


if __name__ == "__main__":
    main()
