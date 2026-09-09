using System.Security.Cryptography;
using System.Text.Json;

namespace OpenDitoo.Webcam.Probe;

/// <summary>
/// The stock-derived Ditoo image encoder, ported so the sidecar can compute the packet hash
/// that `/v1/session/frame` verifies before it sends anything.
///
/// This is a HASH computation, not a transmit path: the Host encodes independently and refuses
/// the frame with IMAGE_ENCODER_HASH_MISMATCH if the two disagree. That refusal is the whole
/// point of the check, so a sidecar whose encoder drifts fails closed rather than displaying
/// something nobody reviewed. `tests/ditoo_encoder_cases.json` is the shared fixture.
///
/// Nothing here reaches Bluetooth, names the target, or opens a socket.
/// </summary>
internal static class DitooEncoder
{
    private const byte Start = 0x01;
    private const byte End = 0x02;
    private const byte CommandImage = 0x44;

    internal static byte[] BuildPacket(byte command, byte[] payload)
    {
        var innerLength = payload.Length + 3;
        var body = new byte[2 + 1 + payload.Length];
        body[0] = (byte)(innerLength & 0xFF);
        body[1] = (byte)((innerLength >> 8) & 0xFF);
        body[2] = command;
        Array.Copy(payload, 0, body, 3, payload.Length);
        var checksum = 0;
        foreach (var b in body) checksum += b;
        checksum &= 0xFFFF;
        var packet = new byte[1 + body.Length + 2 + 1];
        packet[0] = Start;
        Array.Copy(body, 0, packet, 1, body.Length);
        packet[^3] = (byte)(checksum & 0xFF);
        packet[^2] = (byte)((checksum >> 8) & 0xFF);
        packet[^1] = End;
        return packet;
    }

    /// <summary>Encode one 768-byte RGB888 frame. Returns the wire packet and palette size.</summary>
    internal static (byte[] Packet, int PaletteColors) EncodeRgb888(byte[] rgb)
    {
        if (rgb.Length != FrameTransform.FrameBytes)
            throw new ArgumentException($"expected {FrameTransform.FrameBytes} RGB888 bytes");

        // Palette order is FIRST-SEEN in row-major order, not sorted: the index stream depends
        // on it, so a different order is a different packet and a different hash.
        var lookup = new Dictionary<(byte, byte, byte), int>();
        var palette = new List<(byte R, byte G, byte B)>();
        var indices = new int[256];
        for (var i = 0; i < 256; i++)
        {
            var colour = (rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]);
            if (!lookup.TryGetValue(colour, out var index))
            {
                if (palette.Count >= 255)
                    throw new ArgumentException("at most 255 distinct RGB888 colours");
                index = palette.Count;
                lookup[colour] = index;
                palette.Add(colour);
            }
            indices[i] = index;
        }

        var bitsPerPixel = Math.Max(1, (int)Math.Ceiling(Math.Log2(palette.Count)));
        var pixelData = PackIndicesLsb(indices, bitsPerPixel);
        var paletteData = new byte[palette.Count * 3];
        for (var i = 0; i < palette.Count; i++)
        {
            paletteData[i * 3] = palette[i].R;
            paletteData[i * 3 + 1] = palette[i].G;
            paletteData[i * 3 + 2] = palette[i].B;
        }

        // Exact purchased-unit Pixel Coloring layout:
        // 00 0A 0A 04 | AA | frameSizeLE | F4 01 00 | colorCount | palette | packed indices
        var frameSize = 1 + 2 + 3 + 1 + paletteData.Length + pixelData.Length;
        using var payload = new MemoryStream();
        payload.Write(Convert.FromHexString("000a0a04"));
        payload.WriteByte(0xAA);
        payload.WriteByte((byte)(frameSize & 0xFF));
        payload.WriteByte((byte)((frameSize >> 8) & 0xFF));
        payload.Write(Convert.FromHexString("f40100"));
        payload.WriteByte((byte)palette.Count);
        payload.Write(paletteData);
        payload.Write(pixelData);
        return (BuildPacket(CommandImage, payload.ToArray()), palette.Count);
    }

    private static byte[] PackIndicesLsb(int[] indices, int bitsPerPixel)
    {
        if (indices.Length != 256) throw new ArgumentException("exactly 256 indices required");
        if (bitsPerPixel is <= 0 or > 8) throw new ArgumentException("invalid bitsPerPixel");
        var bits = new List<int>(indices.Length * bitsPerPixel);
        var limit = 1 << bitsPerPixel;
        foreach (var value in indices)
        {
            if (value < 0 || value >= limit)
                throw new ArgumentException($"palette index {value} does not fit {bitsPerPixel} bits");
            for (var bit = 0; bit < bitsPerPixel; bit++) bits.Add((value >> bit) & 1);
        }
        while (bits.Count % 8 != 0) bits.Add(0);
        var packed = new byte[bits.Count / 8];
        for (var offset = 0; offset < bits.Count; offset += 8)
        {
            var value = 0;
            for (var bit = 0; bit < 8; bit++) value |= bits[offset + bit] << bit;
            packed[offset / 8] = (byte)value;
        }
        return packed;
    }

    internal static string Sha256Hex(byte[] data) =>
        Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();

    // -- shared fixture ---------------------------------------------------

    private static byte[] FrameFromFormula(string kind, int n)
    {
        var frame = new byte[FrameTransform.FrameBytes];
        for (var i = 0; i < 256; i++)
        {
            int y = i / 16, x = i % 16;
            byte r, g, b;
            switch (kind)
            {
                case "solid": r = g = b = (byte)n; break;
                case "ramp":
                    r = (byte)(i * n % 256); g = (byte)((i * 3 + n) % 256); b = (byte)((i * 7 + n) % 256);
                    break;
                case "twotone":
                    if ((x + y) % 2 != 0) { r = (byte)n; g = 0; b = 0; }
                    else { r = 0; g = 0; b = (byte)n; }
                    break;
                default:  // "full": 256 distinct colours, exercises the palette guard
                    r = (byte)i; g = (byte)(255 - i); b = (byte)(i * 13 % 256); break;
            }
            frame[i * 3] = r; frame[i * 3 + 1] = g; frame[i * 3 + 2] = b;
        }
        return FrameTransform.QuantizeToPaletteLimit(frame);
    }

    internal static int SelfTest(string fixturePath)
    {
        using var document = JsonDocument.Parse(File.ReadAllText(fixturePath));
        int passed = 0, failed = 0;
        foreach (var item in document.RootElement.GetProperty("cases").EnumerateArray())
        {
            var kind = item.GetProperty("kind").GetString()!;
            var n = item.GetProperty("n").GetInt32();
            var frame = FrameFromFormula(kind, n);
            var frameSha = Sha256Hex(frame);
            var (packet, palette) = EncodeRgb888(frame);
            var packetSha = Sha256Hex(packet);

            var ok = frameSha == item.GetProperty("frame_sha256").GetString()
                     && packetSha == item.GetProperty("image_packet_sha256").GetString()
                     && palette == item.GetProperty("palette_colors").GetInt32()
                     && packet.Length == item.GetProperty("image_packet_bytes").GetInt32();
            if (ok) passed++;
            else
            {
                failed++;
                Console.Error.WriteLine(
                    $"ENCODER_MISMATCH kind={kind} n={n} palette={palette} bytes={packet.Length} " +
                    $"frameSha={frameSha} packetSha={packetSha}");
            }
        }
        Console.WriteLine($"ENCODER_SELFTEST_{(failed == 0 ? "PASS" : "FAIL")} " +
                          $"cases={passed + failed} failures={failed} deviceIo=false");
        return failed == 0 ? 0 : 2;
    }
}
