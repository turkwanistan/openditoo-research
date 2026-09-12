using System.Security.Cryptography;

internal static class FrozenVram67Protocol
{
    internal const string ExperimentId = "OPENDITOO-VRAM67-BXLR-001";
    internal const string RequiredGrantText = "Grant OPENDITOO-VRAM67-BXLR-001 -- stock btplayer selected";
    internal const string TargetMac = "11:75:58:CE:DE:C7";
    internal const ulong TargetBluetoothAddress = 0x117558CEDEC7;
    internal const uint TargetRfcommChannel = 1;
    internal const int ExpectedInstalledVersion = 42012;

    internal const int SourceLength = 1088;
    internal const int Runtime50SourceOffset = 1032;
    internal const int Runtime50ModelOffset = 8;
    internal const int CallbackSourceOffset = 1084;
    internal const uint Stage0ThumbEntry = 0x00804779;
    internal const int InterPacketDelayMs = 40;
    internal const int ConnectBudgetMs = 15_000;
    internal const int ObservationHoldMs = 75_000;
    internal const int TotalBudgetMs = 92_000;

    internal const string SourceSha256 = "7ec43cab8cd04da6b2d90983dcec868baee3a1615448d05f446aa5a1c2e3ce48";
    internal const string PrimeSha256 = "9f643ace4ce755ddcd04446c0cb21bbaa23b53f123788a225d1c9eda81e213ec";
    internal const string VoiceTipSha256 = "4cf9f3d0458664a2c99681e6a672b8eaefea3a043d83a2f15a751aabcd9d0316";
    internal const string OverwriteSha256 = "c3fbc813e2646b44ace4a2105163fe7bc2622d5e6cc61477ac6098d0b23b12cd";

    internal static byte[] BuildSource()
    {
        var source = Enumerable.Repeat((byte)0xFF, SourceLength).ToArray();
        source[0] = 0x70;
        source[1] = 0x47; // Thumb BX LR
        source[Runtime50SourceOffset] = 0xFF;
        source[Runtime50SourceOffset + Runtime50ModelOffset] = 0x22;
        BitConverter.GetBytes(Stage0ThumbEntry).CopyTo(source, CallbackSourceOffset);
        return source;
    }

    internal static byte[] BuildPrime() => BuildFrame(0x6E, [0x01]);

    internal static byte[] BuildVoiceTip() => BuildFrame(0xA5, [0x01, 0x02, 0x01]);

    internal static byte[] BuildOverwrite()
    {
        var source = BuildSource();
        var payload = new byte[4 + source.Length];
        // stock frame counter 0, little-endian
        payload[0] = 0x00;
        payload[1] = 0x00;
        payload[2] = checked((byte)(source.Length & 0xFF));
        payload[3] = checked((byte)(source.Length >> 8));
        source.CopyTo(payload, 4);
        return BuildFrame(0x6C, payload);
    }

    internal static void VerifyFrozenConstants()
    {
        if (!BitConverter.IsLittleEndian)
            throw new InvalidOperationException("VRAM67_LITTLE_ENDIAN_REQUIRED");
        var source = BuildSource();
        var prime = BuildPrime();
        var voiceTip = BuildVoiceTip();
        var overwrite = BuildOverwrite();
        RequireHash(source, SourceSha256, "SOURCE");
        RequireHash(prime, PrimeSha256, "PRIME");
        RequireHash(voiceTip, VoiceTipSha256, "VOICETIP");
        RequireHash(overwrite, OverwriteSha256, "OVERWRITE");
        if (prime.Length != 8 || Convert.ToHexString(prime) != "0104006E01730002")
            throw new InvalidOperationException("VRAM67_PRIME_BYTES_DRIFT");
        if (voiceTip.Length != 10 || Convert.ToHexString(voiceTip) != "010600A5010201AF0002")
            throw new InvalidOperationException("VRAM67_VOICETIP_BYTES_DRIFT");
        if (overwrite.Length != 1099 || Convert.ToHexString(overwrite.AsSpan(0, 8)) != "0147046C00004004")
            throw new InvalidOperationException("VRAM67_OVERWRITE_PREFIX_DRIFT");
        if (overwrite[^3] != 0xDB || overwrite[^2] != 0x37 || overwrite[^1] != 0x02)
            throw new InvalidOperationException("VRAM67_OVERWRITE_CHECKSUM_DRIFT");
    }

    private static byte[] BuildFrame(byte command, byte[] payload)
    {
        var innerLength = checked(payload.Length + 3);
        var body = new byte[3 + payload.Length];
        body[0] = checked((byte)(innerLength & 0xFF));
        body[1] = checked((byte)(innerLength >> 8));
        body[2] = command;
        payload.CopyTo(body, 3);
        ushort checksum = 0;
        foreach (var value in body)
            checksum = unchecked((ushort)(checksum + value));
        var wire = new byte[body.Length + 4];
        wire[0] = 0x01;
        body.CopyTo(wire, 1);
        wire[^3] = checked((byte)(checksum & 0xFF));
        wire[^2] = checked((byte)(checksum >> 8));
        wire[^1] = 0x02;
        return wire;
    }

    private static void RequireHash(byte[] data, string expected, string label)
    {
        var actual = Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
        if (!StringComparer.Ordinal.Equals(actual, expected))
            throw new InvalidOperationException($"VRAM67_{label}_HASH_DRIFT ACTUAL={actual}");
    }
}
