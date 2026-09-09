using System.Text.Json;

namespace OpenDitoo.Webcam.Probe;

/// <summary>
/// C# port of host/frame_transform.py. It MUST agree with the Python reference bit for bit:
/// offline previews are how a stream is reviewed before it is sent, so a preview that does not
/// equal what the device receives makes every visual acceptance unverifiable.
///
/// `--transform-selftest tests/frame_transform_cases.json` replays the shared fixture and is
/// the thing that proves the two implementations still agree.
///
/// Rounding is the subtle part: numpy's round and rint are half-to-even, so every rounding here
/// is MidpointRounding.ToEven. Getting that wrong produces frames that differ from the preview
/// in a handful of pixels -- which is exactly the class of drift a fixture exists to catch.
/// </summary>
internal static class FrameTransform
{
    internal const int Size = 16;
    internal const int FrameBytes = Size * Size * 3;
    internal const int MaxPaletteColors = 255;

    private static readonly double[] SrgbToLinear = BuildSrgbToLinear();

    private static double[] BuildSrgbToLinear()
    {
        var table = new double[256];
        for (var i = 0; i < 256; i++)
        {
            var v = i / 255.0;
            table[i] = v <= 0.04045 ? v / 12.92 : Math.Pow((v + 0.055) / 1.055, 2.4);
        }
        return table;
    }

    private static double LinearToSrgb(double value)
    {
        var encoded = value <= 0.0031308 ? value * 12.92
                                         : 1.055 * Math.Pow(Math.Max(value, 0.0), 1 / 2.4) - 0.055;
        return Math.Clamp(encoded * 255.0, 0.0, 255.0);
    }

    internal sealed record Preset(
        string Name, bool LinearLight = true, double Zoom = 1.0,
        double OffsetX = 0.0, double OffsetY = 0.0, bool Mirror = true,
        int QuarterTurns = 0, string Resampler = "area", bool Normalize = false,
        double LowPercentile = 2.0, double HighPercentile = 98.0,
        double Saturation = 1.0, double Gamma = 1.0);

    /// <summary>The frozen default: plan 7.2 candidate A, kept because no challenger won.</summary>
    internal static readonly Preset Default = new("srgb_area", LinearLight: false);

    internal static (int Top, int Left, int Side) SquareRoi(int height, int width, Preset preset)
    {
        var zoom = Math.Max(0.05, Math.Min(1.0, preset.Zoom));
        var side = (int)Math.Round(Math.Min(height, width) * zoom, MidpointRounding.ToEven);
        side = Math.Max(Size, Math.Min(side, Math.Min(height, width)));
        int maxTop = height - side, maxLeft = width - side;
        var top = (int)Math.Round(maxTop / 2.0 * (1.0 + Math.Clamp(preset.OffsetY, -1.0, 1.0)),
                                  MidpointRounding.ToEven);
        var left = (int)Math.Round(maxLeft / 2.0 * (1.0 + Math.Clamp(preset.OffsetX, -1.0, 1.0)),
                                   MidpointRounding.ToEven);
        return (Math.Max(0, Math.Min(top, maxTop)), Math.Max(0, Math.Min(left, maxLeft)), side);
    }

    private static int[] CellEdges(int extent)
    {
        var edges = new int[Size + 1];
        for (var i = 0; i <= Size; i++)
            edges[i] = (int)Math.Round((double)i * extent / Size, MidpointRounding.ToEven);
        return edges;
    }

    /// <summary>
    /// Transform one source frame. `source` is row-major RGB888, `width` x `height`.
    /// Returns exactly 768 bytes.
    /// </summary>
    /// <summary>Source pixel layouts we can read without an intermediate copy.</summary>
    internal enum SourceFormat { Rgb24, Bgra32 }

    internal static byte[] Transform(byte[] source, int width, int height, Preset preset) =>
        Transform(source, width, height, preset, SourceFormat.Rgb24);

    internal static byte[] Transform(byte[] source, int width, int height, Preset preset,
                                     SourceFormat format)
    {
        // Reading the camera's native BGRA in place avoids a 1.2 MB read plus a 900 KB write
        // per frame. Measured effect: transform p95 fell from 2.84 ms to 1.22 ms. It does NOT
        // change the camera's frame rate -- a control run established that rate tracks exposure.
        var pixelStride = format == SourceFormat.Bgra32 ? 4 : 3;
        var channelOffsets = format == SourceFormat.Bgra32
            ? new[] { 2, 1, 0 }   // BGRA -> R, G, B
            : new[] { 0, 1, 2 };
        if (source.Length != width * height * pixelStride)
            throw new ArgumentException(
                $"expected {width * height * pixelStride} bytes, got {source.Length}");
        if (height < Size || width < Size)
            throw new ArgumentException($"source smaller than {Size}x{Size}");
        if (preset.Resampler != "area")
            throw new ArgumentException($"only the area resampler is in the sidecar contract; got {preset.Resampler}");

        var (top, left, side) = SquareRoi(height, width, preset);

        // Crop, mirror and rotate by index mapping rather than by copying intermediate buffers.
        var turns = ((preset.QuarterTurns % 4) + 4) % 4;
        double Sample(int y, int x, int channel)
        {
            // Undo rotation: (y, x) in rotated space -> (sy, sx) in cropped space.
            int sy, sx;
            switch (turns)
            {
                case 1: sy = x; sx = side - 1 - y; break;              // np.rot90 k=1
                case 2: sy = side - 1 - y; sx = side - 1 - x; break;
                case 3: sy = side - 1 - x; sx = y; break;
                default: sy = y; sx = x; break;
            }
            if (preset.Mirror) sx = side - 1 - sx;
            var offset = ((top + sy) * width + (left + sx)) * pixelStride + channelOffsets[channel];
            return preset.LinearLight ? SrgbToLinear[source[offset]] : source[offset];
        }

        var rows = CellEdges(side);
        var cols = CellEdges(side);
        var small = new double[Size, Size, 3];
        for (var cy = 0; cy < Size; cy++)
        {
            for (var cx = 0; cx < Size; cx++)
            {
                int y0 = rows[cy], y1 = rows[cy + 1], x0 = cols[cx], x1 = cols[cx + 1];
                var count = (y1 - y0) * (x1 - x0);
                if (count <= 0) throw new InvalidOperationException("degenerate cell");
                double r = 0, g = 0, b = 0;
                for (var y = y0; y < y1; y++)
                {
                    for (var x = x0; x < x1; x++)
                    {
                        r += Sample(y, x, 0);
                        g += Sample(y, x, 1);
                        b += Sample(y, x, 2);
                    }
                }
                small[cy, cx, 0] = r / count;
                small[cy, cx, 1] = g / count;
                small[cy, cx, 2] = b / count;
                if (!preset.LinearLight)
                {
                    for (var c = 0; c < 3; c++) small[cy, cx, c] /= 255.0;
                }
            }
        }

        if (preset.Normalize) NormalizeLuma(small, preset);
        if (Math.Abs(preset.Saturation - 1.0) > 1e-12)
        {
            for (var y = 0; y < Size; y++)
                for (var x = 0; x < Size; x++)
                {
                    var luma = 0.2126 * small[y, x, 0] + 0.7152 * small[y, x, 1] + 0.0722 * small[y, x, 2];
                    for (var c = 0; c < 3; c++)
                        small[y, x, c] = Math.Clamp(luma + (small[y, x, c] - luma) * preset.Saturation, 0.0, 1.0);
                }
        }
        if (Math.Abs(preset.Gamma - 1.0) > 1e-12)
        {
            for (var y = 0; y < Size; y++)
                for (var x = 0; x < Size; x++)
                    for (var c = 0; c < 3; c++)
                        small[y, x, c] = Math.Pow(Math.Clamp(small[y, x, c], 0.0, 1.0), preset.Gamma);
        }

        var frame = new byte[FrameBytes];
        var index = 0;
        for (var y = 0; y < Size; y++)
            for (var x = 0; x < Size; x++)
                for (var c = 0; c < 3; c++)
                {
                    var encoded = preset.LinearLight
                        ? LinearToSrgb(small[y, x, c])
                        : Math.Clamp(small[y, x, c] * 255.0, 0.0, 255.0);
                    frame[index++] = (byte)Math.Round(encoded, MidpointRounding.ToEven);
                }

        // Last, always: any adjustment after this could reintroduce a 256th colour.
        return QuantizeToPaletteLimit(frame);
    }

    private static void NormalizeLuma(double[,,] small, Preset preset)
    {
        var luma = new double[Size * Size];
        for (var y = 0; y < Size; y++)
            for (var x = 0; x < Size; x++)
                luma[y * Size + x] = 0.2126 * small[y, x, 0] + 0.7152 * small[y, x, 1] + 0.0722 * small[y, x, 2];
        var low = Percentile(luma, preset.LowPercentile);
        var high = Percentile(luma, preset.HighPercentile);
        if (high - low < 1e-6) return;
        var gain = 1.0 / (high - low);
        for (var y = 0; y < Size; y++)
            for (var x = 0; x < Size; x++)
                for (var c = 0; c < 3; c++)
                    small[y, x, c] = Math.Clamp((small[y, x, c] - low) * gain, 0.0, 1.0);
    }

    /// <summary>numpy's linear-interpolation percentile, so the two agree exactly.</summary>
    private static double Percentile(double[] values, double percent)
    {
        var sorted = (double[])values.Clone();
        Array.Sort(sorted);
        var position = percent / 100.0 * (sorted.Length - 1);
        var lower = (int)Math.Floor(position);
        var upper = (int)Math.Ceiling(position);
        if (lower == upper) return sorted[lower];
        return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
    }

    /// <summary>
    /// A 16x16 frame is 256 pixels against a 255-colour encoder cap, so at exactly 256 colours
    /// every colour occurs once and ONE merge always suffices: repaint the single pixel of the
    /// closer pair's second colour. Ties break on scan order, matching the Python reference.
    /// </summary>
    internal static byte[] QuantizeToPaletteLimit(byte[] frame)
    {
        if (frame.Length != FrameBytes) throw new ArgumentException("frame must be 768 bytes");
        var palette = new List<(byte R, byte G, byte B)>();
        var seen = new HashSet<(byte, byte, byte)>();
        for (var i = 0; i < FrameBytes; i += 3)
            if (seen.Add((frame[i], frame[i + 1], frame[i + 2])))
                palette.Add((frame[i], frame[i + 1], frame[i + 2]));
        if (palette.Count <= MaxPaletteColors) return frame;

        // Python sorts the palette before pairing, so the tie-break order must match.
        palette.Sort((a, b) => a.R != b.R ? a.R.CompareTo(b.R)
                             : a.G != b.G ? a.G.CompareTo(b.G) : a.B.CompareTo(b.B));
        long best = long.MaxValue;
        (byte R, byte G, byte B) keep = default, drop = default;
        for (var i = 0; i < palette.Count; i++)
        {
            for (var j = i + 1; j < palette.Count; j++)
            {
                long dr = palette[i].R - palette[j].R, dg = palette[i].G - palette[j].G,
                     db = palette[i].B - palette[j].B;
                var distance = 3 * dr * dr + 4 * dg * dg + 2 * db * db;
                if (distance < best) { best = distance; keep = palette[i]; drop = palette[j]; }
            }
        }
        var merged = (byte[])frame.Clone();
        for (var i = 0; i < FrameBytes; i += 3)
            if (merged[i] == drop.R && merged[i + 1] == drop.G && merged[i + 2] == drop.B)
            {
                merged[i] = keep.R; merged[i + 1] = keep.G; merged[i + 2] = keep.B;
            }
        return merged;
    }

    // -- shared fixture ---------------------------------------------------

    private static byte[] GenerateSource(string kind, int width, int height)
    {
        var data = new byte[width * height * 3];
        var index = 0;
        for (var y = 0; y < height; y++)
            for (var x = 0; x < width; x++)
            {
                if (kind == "gradient")
                {
                    data[index++] = (byte)(x * 255 / Math.Max(1, width - 1));
                    data[index++] = (byte)(y * 255 / Math.Max(1, height - 1));
                    data[index++] = (byte)((x + y) * 255 / Math.Max(1, width + height - 2));
                }
                else
                {
                    var on = (byte)(((x / 7 + y / 7) % 2) * 255);
                    data[index++] = on;
                    data[index++] = (byte)(255 - on);
                    data[index++] = (byte)(x * 3 % 256);
                }
            }
        return data;
    }

    internal static int SelfTest(string fixturePath)
    {
        using var document = JsonDocument.Parse(File.ReadAllText(fixturePath));
        var cases = document.RootElement.GetProperty("cases");
        int passed = 0, failed = 0;
        foreach (var item in cases.EnumerateArray())
        {
            var sourceName = item.GetProperty("source").GetString()!;
            var parts = sourceName.Split('_');
            var dims = parts[^1].Split('x');
            int width = int.Parse(dims[0]), height = int.Parse(dims[1]);
            var source = GenerateSource(parts[0], width, height);

            var p = item.GetProperty("preset");
            var preset = new Preset(
                p.GetProperty("name").GetString()!,
                p.GetProperty("linear_light").GetBoolean(),
                p.GetProperty("zoom").GetDouble(),
                p.GetProperty("offset_x").GetDouble(),
                p.GetProperty("offset_y").GetDouble(),
                p.GetProperty("mirror").GetBoolean(),
                p.GetProperty("quarter_turns").GetInt32(),
                p.GetProperty("resampler").GetString()!,
                p.GetProperty("normalize").GetBoolean(),
                p.GetProperty("low_percentile").GetDouble(),
                p.GetProperty("high_percentile").GetDouble(),
                p.GetProperty("saturation").GetDouble(),
                p.GetProperty("gamma").GetDouble());

            var frame = Transform(source, width, height, preset);
            var actual = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(frame))
                                .ToLowerInvariant();
            var expected = item.GetProperty("output_sha256").GetString();
            if (actual == expected) passed++;
            else
            {
                failed++;
                Console.Error.WriteLine(
                    $"TRANSFORM_MISMATCH source={sourceName} preset={preset.Name} " +
                    $"expected={expected} actual={actual}");
            }
        }
        Console.WriteLine($"TRANSFORM_SELFTEST_{(failed == 0 ? "PASS" : "FAIL")} " +
                          $"cases={passed + failed} failures={failed} deviceIo=false");
        return failed == 0 ? 0 : 2;
    }
}
