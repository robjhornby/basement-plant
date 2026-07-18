"""Regenerate the committed Frutiger Aero site assets from their source art."""

from __future__ import annotations

import io
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRUTIGER_AERO_DIR = (
    PROJECT_ROOT / "src" / "basement_analysis" / "site_assets" / "frutiger_aero"
)
FRUTIGER_AERO_SOURCE_DIR = FRUTIGER_AERO_DIR / "source"
FRUTIGER_AERO_DERIVED_DIR = FRUTIGER_AERO_DIR / "derived"
FRUTIGER_AERO_ASSET_PREFIX = "assets/frutiger-aero"
FRUTIGER_AERO_CACHE_CONTROL = "public, max-age=600, no-transform"
FRUTIGER_AERO_SCENE_WIDTHS = (960, 1440, 2048)
FLOOR_CROP_TOP = 500
FLOOR_WRAP_OVERLAP = 128
DEHUMIDIFIER_MAX_WIDTH = 640
AERO_CUTOUT_MAX_WIDTHS = {"goldfish.png": 640, "dragonfly.png": 512}

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


@dataclass(frozen=True)
class RenderedSiteAsset:
    relative_path: str
    content: bytes
    content_type: str
    cache_control: str
    source_name: str
    width: int | None = None
    height: int | None = None


def resized_to_width(image: Image.Image, max_width: int) -> Image.Image:
    if image.width < max_width:
        raise ValueError(f"Cannot derive {max_width}px asset from {image.width}px source")
    if image.width == max_width:
        return image.copy()
    height = round(image.height * max_width / image.width)
    return image.resize((max_width, height), Image.Resampling.LANCZOS)


def rgb_pixel(image: Image.Image, x_position: int, y_position: int) -> tuple[int, int, int]:
    pixel_value = image.getpixel((x_position, y_position))
    if not isinstance(pixel_value, tuple) or len(pixel_value) < 3:
        raise ValueError("Expected RGB image pixel")
    return (int(pixel_value[0]), int(pixel_value[1]), int(pixel_value[2]))


def unblend_white(image: Image.Image) -> Image.Image:
    rgb_image = image.convert("RGB")
    output_image = Image.new("RGBA", rgb_image.size)
    for y_position in range(rgb_image.height):
        for x_position in range(rgb_image.width):
            red, green, blue = rgb_pixel(rgb_image, x_position, y_position)
            alpha = 255 - min(red, green, blue)
            if alpha < 6:
                output_image.putpixel((x_position, y_position), (0, 0, 0, 0))
                continue
            scale = 255 / alpha
            output_image.putpixel(
                (x_position, y_position),
                (
                    min(255, round((red - (255 - alpha)) * scale)),
                    min(255, round((green - (255 - alpha)) * scale)),
                    min(255, round((blue - (255 - alpha)) * scale)),
                    alpha,
                ),
            )
    return output_image


def horizontally_seamless(image: Image.Image, overlap: int) -> Image.Image:
    width = image.width - overlap
    base_image = image.crop((0, 0, width, image.height)).convert("RGB")
    tail_image = image.crop((width, 0, image.width, image.height)).convert("RGB")
    mask = Image.new("L", (overlap, image.height))
    for x_position in range(overlap):
        alpha = round(255 * (1 - x_position / overlap))
        for y_position in range(image.height):
            mask.putpixel((x_position, y_position), alpha)
    head_image = Image.composite(tail_image, base_image.crop((0, 0, overlap, image.height)), mask)
    base_image.paste(head_image, (0, 0))
    return base_image


def key_product_shot(image: Image.Image) -> Image.Image:
    rgb_image = image.convert("RGB")
    width, height = rgb_image.size
    background = [[False] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()

    def near_white(x_position: int, y_position: int) -> bool:
        red, green, blue = rgb_pixel(rgb_image, x_position, y_position)
        return min(red, green, blue) >= 246

    for x_position in range(width):
        for y_position in (0, height - 1):
            if near_white(x_position, y_position) and not background[y_position][x_position]:
                background[y_position][x_position] = True
                queue.append((x_position, y_position))
    for y_position in range(height):
        for x_position in (0, width - 1):
            if near_white(x_position, y_position) and not background[y_position][x_position]:
                background[y_position][x_position] = True
                queue.append((x_position, y_position))
    while queue:
        x_position, y_position = queue.popleft()
        for next_x, next_y in (
            (x_position - 1, y_position),
            (x_position + 1, y_position),
            (x_position, y_position - 1),
            (x_position, y_position + 1),
        ):
            if (
                0 <= next_x < width
                and 0 <= next_y < height
                and not background[next_y][next_x]
                and near_white(next_x, next_y)
            ):
                background[next_y][next_x] = True
                queue.append((next_x, next_y))

    rim = [[False] * width for _ in range(height)]
    for _ in range(2):
        additions: list[tuple[int, int]] = []
        for y_position in range(height):
            for x_position in range(width):
                if background[y_position][x_position] or rim[y_position][x_position]:
                    continue
                for next_x, next_y in (
                    (x_position - 1, y_position),
                    (x_position + 1, y_position),
                    (x_position, y_position - 1),
                    (x_position, y_position + 1),
                ):
                    if (
                        0 <= next_x < width
                        and 0 <= next_y < height
                        and (background[next_y][next_x] or rim[next_y][next_x])
                    ):
                        additions.append((x_position, y_position))
                        break
        for x_position, y_position in additions:
            rim[y_position][x_position] = True

    shadow_top = round(height * 0.78)
    output_image = Image.new("RGBA", rgb_image.size)
    for y_position in range(height):
        for x_position in range(width):
            red, green, blue = rgb_pixel(rgb_image, x_position, y_position)
            if background[y_position][x_position]:
                output_image.putpixel((x_position, y_position), (0, 0, 0, 0))
                continue
            minimum = min(red, green, blue)
            chroma = max(red, green, blue) - minimum
            soften = rim[y_position][x_position] or (
                y_position >= shadow_top and chroma <= 14 and minimum >= 190
            )
            if not soften:
                output_image.putpixel((x_position, y_position), (red, green, blue, 255))
                continue
            alpha = 255 - minimum
            if alpha < 6:
                output_image.putpixel((x_position, y_position), (0, 0, 0, 0))
                continue
            scale = 255 / alpha
            output_image.putpixel(
                (x_position, y_position),
                (
                    min(255, round((red - (255 - alpha)) * scale)),
                    min(255, round((green - (255 - alpha)) * scale)),
                    min(255, round((blue - (255 - alpha)) * scale)),
                    alpha,
                ),
            )
    return output_image


def webp_bytes(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=quality, method=6)
    return buffer.getvalue()


def render_frutiger_aero_assets(
    source_dir: Path = FRUTIGER_AERO_SOURCE_DIR,
) -> dict[str, RenderedSiteAsset]:
    assets: dict[str, RenderedSiteAsset] = {}

    def add_webp(filename: str, image: Image.Image, quality: int, source_name: str) -> None:
        relative_path = f"{FRUTIGER_AERO_ASSET_PREFIX}/{filename}"
        assets[relative_path] = RenderedSiteAsset(
            relative_path=relative_path,
            content=webp_bytes(image, quality=quality),
            content_type="image/webp",
            cache_control=FRUTIGER_AERO_CACHE_CONTROL,
            source_name=source_name,
            width=image.width,
            height=image.height,
        )

    scene_source_name = "tall-scene-source.webp"
    with Image.open(source_dir / scene_source_name) as raw_scene:
        scene = raw_scene.convert("RGB")
    for width in FRUTIGER_AERO_SCENE_WIDTHS:
        add_webp(
            filename=f"tall-scene-{width}.webp",
            image=resized_to_width(scene, width),
            quality=80,
            source_name=scene_source_name,
        )

    floor_source_name = "floor-strip.png"
    with Image.open(source_dir / floor_source_name) as raw_floor:
        floor = raw_floor.convert("RGB")
    floor = floor.crop((0, FLOOR_CROP_TOP, floor.width, floor.height))
    add_webp(
        filename="floor-strip.webp",
        image=horizontally_seamless(floor, FLOOR_WRAP_OVERLAP),
        quality=80,
        source_name=floor_source_name,
    )

    dehumidifier_source_name = "dehumidifier-no-shadow.png"
    with Image.open(source_dir / dehumidifier_source_name) as raw_dehumidifier:
        dehumidifier = key_product_shot(raw_dehumidifier)
    add_webp(
        filename="dehumidifier.webp",
        image=resized_to_width(dehumidifier, DEHUMIDIFIER_MAX_WIDTH),
        quality=82,
        source_name=dehumidifier_source_name,
    )

    for source_name, max_width in AERO_CUTOUT_MAX_WIDTHS.items():
        with Image.open(source_dir / source_name) as raw_cutout:
            cutout = unblend_white(resized_to_width(raw_cutout, max_width))
        add_webp(
            filename=f"{Path(source_name).stem}.webp",
            image=cutout,
            quality=78,
            source_name=source_name,
        )

    manifest_entries: list[dict[str, JsonValue]] = [
        {
            "path": asset.relative_path,
            "contentType": asset.content_type,
            "cacheControl": asset.cache_control,
            "source": asset.source_name,
            "width": asset.width,
            "height": asset.height,
            "bytes": len(asset.content),
        }
        for asset in sorted(assets.values(), key=lambda item: item.relative_path)
    ]
    manifest_path = f"{FRUTIGER_AERO_ASSET_PREFIX}/manifest.json"
    manifest_content = json.dumps(
        {
            "theme": "frutiger-aero",
            "cacheControl": FRUTIGER_AERO_CACHE_CONTROL,
            "assets": manifest_entries,
            "sceneSrcset": [
                f"{FRUTIGER_AERO_ASSET_PREFIX}/tall-scene-{width}.webp {width}w"
                for width in FRUTIGER_AERO_SCENE_WIDTHS
            ],
        },
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    assets[manifest_path] = RenderedSiteAsset(
        relative_path=manifest_path,
        content=manifest_content,
        content_type="application/json; charset=utf-8",
        cache_control=FRUTIGER_AERO_CACHE_CONTROL,
        source_name="generated",
    )
    return assets


def render_site_assets() -> dict[str, RenderedSiteAsset]:
    return render_frutiger_aero_assets()


def write_site_assets(
    assets: dict[str, RenderedSiteAsset],
    output_dir: Path = FRUTIGER_AERO_DERIVED_DIR,
) -> None:
    for relative_path, asset in assets.items():
        destination_path = output_dir / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(asset.content)


def main() -> None:
    assets = render_site_assets()
    write_site_assets(assets)
    print(f"Wrote {len(assets)} assets to {FRUTIGER_AERO_DERIVED_DIR}")


if __name__ == "__main__":
    main()
