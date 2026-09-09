/// <summary>
/// Bounded reassembly and classification of inbound application frames.
///
/// The device does not only answer: physical controls produce UNSOLICITED wrapped
/// reports on the same link, with no request from us (M7). While a display session is
/// open we therefore have to read a stream, not a reply, and a read may deliver a
/// fragment, an exact frame, or an ACK and a state report coalesced together.
///
/// This assigns no new command semantics. It answers exactly one question: is this our
/// ACK, or is it something else that means we should stop?
/// </summary>
readonly record struct DitooReport(byte OuterCommand, byte InnerCommand, byte Tag, byte[] Payload, byte[] Wire)
{
    // The one shape we have exact-unit evidence for: a wrapped 0x44 answer carrying a
    // single payload byte. That byte is NOT a success constant (20 distinct values
    // observed across two loop runs), so it is reported and never validated.
    internal bool IsAck => OuterCommand == 0x04 && InnerCommand == 0x44 && Tag == 0x55 && Payload.Length == 1;

    internal string Kind => IsAck ? "ack" : "state_report";

    internal string Describe() =>
        $"outer=0x{OuterCommand:X2} inner=0x{InnerCommand:X2} tag=0x{Tag:X2} payloadBytes={Payload.Length}";
}

sealed class DitooTakeoverException(DitooReport report, bool ackAlreadyReceived)
    : Exception($"IMAGE_SESSION_UNEXPECTED_REPORT {report.Describe()}; NO_RETRY; NO_RECLAIM")
{
    internal DitooReport Report { get; } = report;

    // Whether the frame in flight had already been acknowledged when the canvas was
    // taken. Either way the session ends: a late ACK cannot restore ownership.
    internal bool AckAlreadyReceived { get; } = ackAlreadyReceived;
}

/// <summary>Byte-stream assembler. Fail-closed: anything it cannot parse ends the session.</summary>
sealed class DitooReportAssembler
{
    // Largest inbound frame we will hold. The largest exact-unit report observed is a
    // 0x46 state report at 22 data bytes; this is a defensive cap, not a device limit.
    internal const int MaxFrameBytes = 256;
    private const byte Start = 0x01, End = 0x02;

    private readonly List<byte> buffer = new(MaxFrameBytes);

    internal int BufferedBytes => buffer.Count;

    internal void Feed(byte[] chunk, int count)
    {
        for (var i = 0; i < count; i++) buffer.Add(chunk[i]);
        if (buffer.Count > MaxFrameBytes)
            throw new InvalidOperationException($"IMAGE_RX_OVERSIZE BYTES={buffer.Count}; NO_RETRY");
    }

    /// <summary>Pull every complete frame currently buffered. A trailing fragment stays.</summary>
    internal List<DitooReport> Drain()
    {
        var reports = new List<DitooReport>();
        while (true)
        {
            if (buffer.Count < 3) return reports;
            if (buffer[0] != Start)
                throw new InvalidOperationException($"IMAGE_RX_BAD_START BYTE=0x{buffer[0]:X2}; NO_RETRY");
            var inner = buffer[1] | (buffer[2] << 8);
            var total = inner + 4;
            // Wrapped shape: outer, inner command, tag, then payload.
            if (inner < 5 || total > MaxFrameBytes)
                throw new InvalidOperationException($"IMAGE_RX_LENGTH_REJECTED INNER={inner}; NO_RETRY");
            if (buffer.Count < total) return reports;
            var wire = buffer.GetRange(0, total).ToArray();
            buffer.RemoveRange(0, total);
            reports.Add(Parse(wire));
        }
    }

    internal static DitooReport Parse(byte[] wire)
    {
        if (wire.Length < 9 || wire[0] != Start || wire[^1] != End)
            throw new InvalidOperationException("IMAGE_RX_BOUNDARY_REJECTED; NO_RETRY");
        var inner = wire[1] | (wire[2] << 8);
        if (wire.Length != inner + 4)
            throw new InvalidOperationException($"IMAGE_RX_LENGTH_MISMATCH DECLARED={inner + 4} ACTUAL={wire.Length}; NO_RETRY");
        ushort sum = 0;
        for (var i = 1; i < wire.Length - 3; i++) sum = unchecked((ushort)(sum + wire[i]));
        var observed = (ushort)(wire[^3] | (wire[^2] << 8));
        if (sum != observed)
            throw new InvalidOperationException($"IMAGE_RX_CHECKSUM_REJECTED OBSERVED=0x{observed:X4} EXPECTED=0x{sum:X4}; NO_RETRY");
        var payload = wire[6..^3];
        return new DitooReport(wire[3], wire[4], wire[5], payload, wire);
    }

    /// <summary>
    /// Offline self-check over a shared fixture, so the C# assembler can be exercised
    /// from the repository without a test framework or any device. See
    /// `--selftest` in Program.cs and the mirrored Python cases in the offline suite.
    /// </summary>
    internal static int SelfTest(string fixturePath)
    {
        var text = File.ReadAllText(fixturePath);
        var cases = System.Text.Json.JsonDocument.Parse(text).RootElement.GetProperty("cases");
        var failures = 0;
        foreach (var item in cases.EnumerateArray())
        {
            var name = item.GetProperty("name").GetString()!;
            var assembler = new DitooReportAssembler();
            var kinds = new List<string>();
            string? error = null;
            try
            {
                foreach (var chunk in item.GetProperty("chunks").EnumerateArray())
                {
                    var bytes = Convert.FromHexString(chunk.GetString()!);
                    assembler.Feed(bytes, bytes.Length);
                    foreach (var report in assembler.Drain()) kinds.Add(report.Kind);
                }
            }
            catch (Exception ex)
            {
                error = ex.Message.Split(' ')[0];
            }
            var expectedKinds = item.GetProperty("expect_kinds").EnumerateArray()
                .Select(value => value.GetString()!).ToList();
            var expectedError = item.TryGetProperty("expect_error", out var e) ? e.GetString() : null;
            var ok = error == expectedError && kinds.SequenceEqual(expectedKinds);
            if (!ok)
            {
                failures++;
                Console.Error.WriteLine(
                    $"SELFTEST_FAIL {name}: kinds=[{string.Join(",", kinds)}] expected=[{string.Join(",", expectedKinds)}] " +
                    $"error={error ?? "-"} expectedError={expectedError ?? "-"}");
            }
        }
        var count = cases.GetArrayLength();
        Console.WriteLine($"HOST_SELFTEST_{(failures == 0 ? "PASS" : "FAIL")} cases={count} failures={failures} device_io=false");
        return failures == 0 ? 0 : 1;
    }
}
