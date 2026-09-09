"""Reference 16x16 transform: source frame -> square ROI -> 768 bytes of RGB888.

This is the REFERENCE implementation, and the Windows sidecar's C# transform must match it
bit for bit. That is not tidiness: offline previews are how a stream is reviewed before it is
sent, so a preview that does not equal what the device receives makes every visual acceptance
unverifiable. `tests/frame_transform_cases.json` is the shared fixture both sides replay.

Deliberately deterministic: integer output, no dithering, no random seed, no wall-clock or
frame-history dependence. The same source pixels and the same preset always give the same 768
bytes.

Order of operations, and why:

1. **Square ROI, then zoom.** A 16x16 panel is square; cropping before scaling means no
   anisotropic squash, and cropping the largest centred square keeps the most detail.
2. **Downscale by area average, in linear light.** This is where 16x16 fidelity is won or
   lost. Averaging gamma-encoded sRGB values is the single largest avoidable quality loss
   available -- it biases every average dark, because sRGB is not proportional to light. The
   `linear` preset undoes the transfer function, averages, then re-applies it.
3. **Optional exposure/contrast normalisation.** A 16x16 crop of a webcam frame is dominated
   by dynamic range, not detail, so this matters more than resampler choice.
4. **Palette guard last.** It must be the final step: any adjustment after it could
   reintroduce a 256th colour and make the frame unencodable.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import numpy as np

SIZE = 16
FRAME_BYTES = SIZE * SIZE * 3


@dataclass(frozen=True)
class Preset:
    """A frozen, reviewable transform configuration. Hash this, not the pixels."""

    name: str
    linear_light: bool = True
    # Fraction of the largest centred square to keep. 1.0 is the whole square; smaller zooms in.
    zoom: float = 1.0
    # Centre offset as a fraction of the croppable margin, -1..1. 0 is centred.
    offset_x: float = 0.0
    offset_y: float = 0.0
    mirror: bool = True          # a webcam facing the user reads correctly mirrored
    # The owner's camera is physically mounted on its side, so the scene arrives rotated.
    # Correcting it here keeps the ROI square and the subject upright; doing it downstream
    # would mean cropping a rotated rectangle.
    quarter_turns: int = 0
    # Benchmark-only resamplers from plan section 7.2. "area" is the only one the sidecar has
    # to implement unless a challenger actually wins the ranking.
    resampler: str = "area"      # area | bicubic | lanczos | area32_bicubic
    normalize: bool = False      # stretch luma to full range
    # Percentiles used by normalisation, so one blown highlight cannot define the range.
    low_percentile: float = 2.0
    high_percentile: float = 98.0
    saturation: float = 1.0
    gamma: float = 1.0

    @property
    def violates_v1_preprocessing_policy(self) -> bool:
        """Plan section 7.3 bars per-frame auto-levels in v1: it pumps brightness temporally.

        A still image cannot show that, which is exactly why this is a flag and not a
        judgement made from a contact sheet.
        """
        return self.normalize

    def describe(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


# sRGB area average is the plan's default and the baseline every candidate is judged against.
BASELINE = Preset(name="srgb_area", linear_light=False)
# Plan section 7.2's candidate set. A and B are production-shaped; C, D and E are
# benchmark-only, and would each cost the sidecar a real resampler implementation if promoted.
# The normalize/saturation variants are kept to MEASURE what section 7.3 warns about, not as
# proposals -- they are flagged and cannot be defaults.
CANDIDATES = (
    BASELINE,                                                    # A
    Preset(name="linear_area"),                                  # B
    Preset(name="linear_bicubic", resampler="bicubic"),          # C
    Preset(name="linear_lanczos", resampler="lanczos"),          # D
    Preset(name="linear_area32_bicubic", resampler="area32_bicubic"),  # E
    Preset(name="linear_area_contrast108", saturation=1.0, gamma=0.95),
    Preset(name="BENCHMARK_ONLY_linear_area_normalized", normalize=True),
    Preset(name="BENCHMARK_ONLY_linear_area_normalized_sat", normalize=True, saturation=1.10),
)
# Until a challenger wins a majority of scene classes without losing the motion class, the
# frozen default is the plan's provisional one.
DEFAULT = BASELINE


def _srgb_to_linear_scalar(values: np.ndarray) -> np.ndarray:
    values = values / 255.0
    return np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)


# The source is uint8, so the transfer function has exactly 256 possible inputs. A lookup turns
# the decode from a pow() over ~700k floats into a gather, which is what took the linear-light
# presets from 15 ms to well inside the 5 ms budget. The sidecar should build the same table.
_SRGB_TO_LINEAR = _srgb_to_linear_scalar(np.arange(256, dtype=np.float64))


def _srgb_to_linear(values: np.ndarray) -> np.ndarray:
    if values.dtype == np.uint8:
        return _SRGB_TO_LINEAR[values]
    return _srgb_to_linear_scalar(values)


def _linear_to_srgb(values: np.ndarray) -> np.ndarray:
    encoded = np.where(values <= 0.0031308, values * 12.92,
                       1.055 * np.maximum(values, 0.0) ** (1 / 2.4) - 0.055)
    return np.clip(encoded * 255.0, 0.0, 255.0)


def square_roi(height: int, width: int, preset: Preset) -> tuple[int, int, int]:
    """Return (top, left, side) of the crop, clamped to stay inside the frame."""
    side = int(round(min(height, width) * max(0.05, min(1.0, preset.zoom))))
    side = max(SIZE, min(side, min(height, width)))
    max_top, max_left = height - side, width - side
    top = int(round(max_top / 2 * (1.0 + max(-1.0, min(1.0, preset.offset_y)))))
    left = int(round(max_left / 2 * (1.0 + max(-1.0, min(1.0, preset.offset_x)))))
    return max(0, min(top, max_top)), max(0, min(left, max_left)), side


def _area_downsample(block: np.ndarray) -> np.ndarray:
    """Average each of the 16x16 destination cells over its exact source region.

    Source sides are not generally divisible by 16, so cell edges are computed per row and
    column rather than assuming a uniform block size -- otherwise the right and bottom edges
    silently lose or double-count pixels.
    """
    height, width = block.shape[:2]
    rows = np.linspace(0, height, SIZE + 1).round().astype(int)
    cols = np.linspace(0, width, SIZE + 1).round().astype(int)
    row_counts = np.diff(rows)
    col_counts = np.diff(cols)
    if row_counts.min() < 1 or col_counts.min() < 1:
        raise ValueError(f"degenerate cell in {width}x{height} crop")
    # Two reduceat passes sum each cell exactly, with no assumption that the side divides by
    # 16 -- the edge cells are simply wider or narrower, and the divisor matches.
    summed = np.add.reduceat(np.add.reduceat(block, rows[:-1], axis=0), cols[:-1], axis=1)
    return summed / (row_counts[:, None] * col_counts[None, :])[:, :, None]


def _resample_via_pil(block: np.ndarray, preset: Preset) -> np.ndarray:
    """Benchmark-only resamplers (plan 7.2 C/D/E). PIL is imported lazily so the production
    area path never needs it.

    Resizing happens in linear light for the same reason area averaging does: a sinc kernel
    over gamma-encoded values weights dark samples wrongly, and at 256 pixels that shows.
    """
    from PIL import Image

    linear = _srgb_to_linear(block) if preset.linear_light else block.astype(np.float64) / 255.0

    def resize(planes: np.ndarray, size: int, filt) -> np.ndarray:
        # One float plane per channel: PIL's "F" mode resamples without any 8-bit round trip,
        # so no precision is lost between the two stages of the E candidate.
        return np.stack([
            np.asarray(Image.fromarray(planes[:, :, channel].astype(np.float32), mode="F")
                       .resize((size, size), filt), dtype=np.float64)
            for channel in range(3)], axis=2)

    if preset.resampler == "bicubic":
        out = resize(linear, SIZE, Image.Resampling.BICUBIC)
    elif preset.resampler == "lanczos":
        out = resize(linear, SIZE, Image.Resampling.LANCZOS)
    elif preset.resampler == "area32_bicubic":
        out = resize(resize(linear, 32, Image.Resampling.BOX), SIZE, Image.Resampling.BICUBIC)
    else:
        raise ValueError(f"unknown resampler {preset.resampler!r}")
    # Sinc-family kernels overshoot. Clipping is what keeps ringing from becoming out-of-range
    # values the encoder would wrap into nonsense colours.
    return np.clip(out, 0.0, 1.0)


def _normalize_luma(rgb: np.ndarray, preset: Preset) -> np.ndarray:
    """Stretch to the full range using luma only, so hue is not dragged around.

    Percentile-based: one specular highlight or one black shadow must not define the range.
    """
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722])
    low = float(np.percentile(luma, preset.low_percentile))
    high = float(np.percentile(luma, preset.high_percentile))
    if high - low < 1e-6:
        return rgb
    gain = 1.0 / (high - low)
    scaled = (rgb - low) * gain
    return np.clip(scaled, 0.0, 1.0)


def transform(source_rgb: np.ndarray, preset: Preset) -> bytes:
    """One source frame (H, W, 3) uint8 RGB -> exactly 768 bytes of RGB888."""
    from host.frame_stream import quantize_to_palette_limit

    if source_rgb.ndim != 3 or source_rgb.shape[2] != 3:
        raise ValueError(f"expected (H, W, 3) RGB, got {source_rgb.shape}")
    height, width = source_rgb.shape[:2]
    if height < SIZE or width < SIZE:
        raise ValueError(f"source smaller than {SIZE}x{SIZE}: {width}x{height}")

    top, left, side = square_roi(height, width, preset)
    # Kept as uint8 through crop and mirror so the linear decode can use its lookup table.
    block = source_rgb[top:top + side, left:left + side]
    if preset.mirror:
        block = block[:, ::-1]

    if preset.quarter_turns:
        block = np.rot90(block, k=preset.quarter_turns % 4)

    if preset.resampler == "area":
        small = (_area_downsample(_srgb_to_linear(block)) if preset.linear_light
                 else _area_downsample(block.astype(np.float64)) / 255.0)
    else:
        small = _resample_via_pil(block, preset)

    if preset.normalize:
        small = _normalize_luma(small, preset)
    if preset.saturation != 1.0:
        luma = (small @ np.array([0.2126, 0.7152, 0.0722]))[:, :, None]
        small = np.clip(luma + (small - luma) * preset.saturation, 0.0, 1.0)
    if preset.gamma != 1.0:
        small = np.clip(small, 0.0, 1.0) ** preset.gamma

    encoded = (_linear_to_srgb(small) if preset.linear_light
               else np.clip(small * 255.0, 0.0, 255.0))
    frame = np.rint(encoded).astype(np.uint8).tobytes()
    assert len(frame) == FRAME_BYTES, len(frame)
    # Last, always: any adjustment after this could reintroduce a 256th colour.
    guarded, _ = quantize_to_palette_limit(frame)
    return guarded


def enlarge(frame: bytes, scale: int = 24) -> np.ndarray:
    """Nearest-neighbour enlargement for human inspection. Never used for device output."""
    pixels = np.frombuffer(frame, dtype=np.uint8).reshape(SIZE, SIZE, 3)
    return pixels.repeat(scale, axis=0).repeat(scale, axis=1)


def preset_by_name(name: str) -> Preset:
    for candidate in CANDIDATES:
        if candidate.name == name:
            return candidate
    raise KeyError(name)
