using OpenDitoo.Webcam.Probe;

namespace OpenDitoo.Webcam.Studio;

/// <summary>
/// Optional palette reduction after the transform, for comparing looks: fewer colours means fewer
/// bits per pixel and a smaller palette, so a smaller packet (about 190 bytes at 16 colours versus
/// about 1000 at a full 255). Deterministic median cut over the frame's 256 pixels: repeatedly split
/// the box with the widest single-channel range at its median, then paint each box its mean colour.
/// </summary>
internal static class ColourReduce
{
    internal static readonly int[] Choices = [255, 64, 32, 16, 8];

    internal static byte[] MedianCut(byte[] rgb, int colours)
    {
        if (rgb.Length != FrameTransform.FrameBytes) throw new ArgumentException("frame must be 768 bytes");
        if (colours >= FrameTransform.MaxPaletteColors) return rgb;
        var boxes = new List<int[]> { Enumerable.Range(0, 256).ToArray() };
        while (boxes.Count < colours)
        {
            int best = -1, bestChannel = 0, bestRange = 0;
            for (var b = 0; b < boxes.Count; b++)
                for (var c = 0; c < 3; c++)
                {
                    int min = 255, max = 0;
                    foreach (var p in boxes[b]) { min = Math.Min(min, rgb[p * 3 + c]); max = Math.Max(max, rgb[p * 3 + c]); }
                    if (max - min > bestRange) { bestRange = max - min; best = b; bestChannel = c; }
                }
            if (best < 0) break; // every box is a single colour already
            var sorted = boxes[best].OrderBy(p => rgb[p * 3 + bestChannel]).ThenBy(p => p).ToArray();
            boxes[best] = sorted[..(sorted.Length / 2)];
            boxes.Add(sorted[(sorted.Length / 2)..]);
        }
        var output = new byte[FrameTransform.FrameBytes];
        foreach (var box in boxes)
            for (var c = 0; c < 3; c++)
            {
                var mean = (byte)Math.Round(box.Average(p => rgb[p * 3 + c]), MidpointRounding.ToEven);
                foreach (var p in box) output[p * 3 + c] = mean;
            }
        return output;
    }

    /// <summary>The C# transform's parity-tested presets (area resampler only), by their W2 names.</summary>
    internal static readonly IReadOnlyDictionary<string, FrameTransform.Preset> Presets = new Dictionary<string, FrameTransform.Preset>
    {
        ["srgb_area"] = FrameTransform.Default,
        ["linear_area"] = new("linear_area"),
        ["linear_area_contrast108"] = new("linear_area_contrast108", Saturation: 1.0, Gamma: 0.95),
        ["BENCHMARK_ONLY_linear_area_normalized"] = new("BENCHMARK_ONLY_linear_area_normalized", Normalize: true),
        ["BENCHMARK_ONLY_linear_area_normalized_sat"] = new("BENCHMARK_ONLY_linear_area_normalized_sat", Normalize: true, Saturation: 1.10),
    };
}
