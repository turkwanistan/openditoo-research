using System.Security.Cryptography;

static class DitooStaticImageProtocol
{
    internal const string TargetMac = "11:75:58:CE:DE:C7";
    internal const ulong TargetBluetoothAddress = 0x117558CEDEC7;
    internal const uint TargetRfcommChannel = 1;
    internal const int ConnectBudgetMs = 15_000;
    internal const int AckBudgetMs = 5_000;
    internal const int TotalBudgetMs = 20_000;
    internal const int SendSpacingMs = 40;
    internal const int RgbBytes = 16 * 16 * 3;
    internal static readonly byte[] ImagePreambleA = Convert.FromHexString("0103009FA20002");
    internal static readonly byte[] ImagePreambleB = Convert.FromHexString("010400BD31F20002");

    internal sealed record EncodedImage(byte[] Packet, int PaletteColors, string PacketSha256);

    internal static EncodedImage EncodeRgb888(byte[] rgb)
    {
        if (rgb.Length != RgbBytes)
            throw new ArgumentException($"IMAGE_RGB_LENGTH_REJECTED EXPECTED={RgbBytes} ACTUAL={rgb.Length}");

        var palette = new List<(byte R, byte G, byte B)>();
        var lookup = new Dictionary<int, byte>();
        var indices = new byte[256];
        for (var pixel = 0; pixel < 256; pixel++)
        {
            var offset = pixel * 3;
            var r = rgb[offset];
            var g = rgb[offset + 1];
            var b = rgb[offset + 2];
            var key = (r << 16) | (g << 8) | b;
            if (!lookup.TryGetValue(key, out var index))
            {
                if (palette.Count >= 255)
                    throw new ArgumentException("IMAGE_PALETTE_REJECTED: at most 255 distinct RGB888 colors are supported");
                index = checked((byte)palette.Count);
                lookup.Add(key, index);
                palette.Add((r, g, b));
            }
            indices[pixel] = index;
        }

        var bitsPerPixel = 1;
        while ((1 << bitsPerPixel) < palette.Count)
            bitsPerPixel++;
        var packed = new byte[(256 * bitsPerPixel + 7) / 8];
        var bitOffset = 0;
        foreach (var index in indices)
        {
            for (var bit = 0; bit < bitsPerPixel; bit++)
            {
                if (((index >> bit) & 1) != 0)
                    packed[bitOffset / 8] |= checked((byte)(1 << (bitOffset % 8)));
                bitOffset++;
            }
        }

        var paletteBytes = new byte[palette.Count * 3];
        for (var i = 0; i < palette.Count; i++)
        {
            paletteBytes[i * 3] = palette[i].R;
            paletteBytes[i * 3 + 1] = palette[i].G;
            paletteBytes[i * 3 + 2] = palette[i].B;
        }

        var frameSize = 1 + 2 + 3 + 1 + paletteBytes.Length + packed.Length;
        if (frameSize > ushort.MaxValue)
            throw new ArgumentException("IMAGE_FRAME_SIZE_REJECTED");
        var payload = new List<byte>(11 + paletteBytes.Length + packed.Length)
        {
            0x00, 0x0A, 0x0A, 0x04, 0xAA,
            checked((byte)(frameSize & 0xFF)), checked((byte)((frameSize >> 8) & 0xFF)),
            0xF4, 0x01, 0x00,
            checked((byte)palette.Count)
        };
        payload.AddRange(paletteBytes);
        payload.AddRange(packed);
        var packet = BuildPacket(0x44, payload.ToArray());
        return new EncodedImage(packet, palette.Count, Sha256Hex(packet));
    }

    internal static byte[][] BuildTransaction(byte[] imagePacket) =>
    [
        ImagePreambleA.ToArray(),
        ImagePreambleB.ToArray(),
        imagePacket.ToArray(),
    ];

    private static byte[] BuildPacket(byte command, byte[] payload)
    {
        var innerLength = payload.Length + 3;
        if (innerLength > ushort.MaxValue)
            throw new ArgumentException("APPLICATION_FRAME_TOO_LARGE");
        var body = new byte[3 + payload.Length];
        body[0] = checked((byte)(innerLength & 0xFF));
        body[1] = checked((byte)((innerLength >> 8) & 0xFF));
        body[2] = command;
        payload.CopyTo(body, 3);
        ushort checksum = 0;
        foreach (var value in body)
            checksum = unchecked((ushort)(checksum + value));
        var wire = new byte[1 + body.Length + 2 + 1];
        wire[0] = 0x01;
        body.CopyTo(wire, 1);
        wire[^3] = checked((byte)(checksum & 0xFF));
        wire[^2] = checked((byte)(checksum >> 8));
        wire[^1] = 0x02;
        return wire;
    }

    internal static string Sha256Hex(byte[] data) => Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
}
