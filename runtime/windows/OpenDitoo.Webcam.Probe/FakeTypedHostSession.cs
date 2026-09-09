namespace OpenDitoo.Webcam.Probe;

/// <summary>
/// An in-memory stand-in for the typed Host's `/v1/session/*` family, for W5's dry run.
///
/// It is deliberately not a permissive mock. It re-encodes every frame independently and
/// refuses on hash mismatch exactly as the Host does, and it enforces the same lifetime, frame
/// and byte budgets and the same pacing floor. A dry run that passes against a lenient fake
/// would prove nothing about the real path, and the point of this milestone is to find the
/// refusals here rather than on the device.
///
/// It reaches no Bluetooth, no socket and no Ditoo. The ACK is a delay.
/// </summary>
internal sealed class FakeTypedHostSession
{
    internal const string ProfileStreamingAckClock = "streaming_ack_clock";
    internal const string ProfileActivity = "activity";

    private readonly int minFrameIntervalMs;
    private readonly int maxFrames;
    private readonly int maxTxBytes;
    private readonly int lifetimeMs;
    private readonly int fakeAckMs;
    private readonly System.Diagnostics.Stopwatch clock = System.Diagnostics.Stopwatch.StartNew();
    private double lastFrameStartedMs = double.NegativeInfinity;

    internal string SessionProfile { get; }
    internal int FramesSent { get; private set; }
    internal int PacketsSent { get; private set; }
    internal int TxBytesSent { get; private set; }
    internal string? TerminalReason { get; private set; }
    internal string? TerminalOutcome { get; private set; }

    internal FakeTypedHostSession(string profile, int lifetimeSeconds, int minFrameIntervalMs,
                                  int maxFrames, int maxTxBytes, int fakeAckMs)
    {
        SessionProfile = profile switch
        {
            ProfileStreamingAckClock or ProfileActivity => profile,
            _ => throw new ArgumentException("SESSION_PROFILE_UNKNOWN"),
        };
        var floor = profile == ProfileStreamingAckClock ? 40 : 150;
        if (minFrameIntervalMs < floor) throw new ArgumentException("SESSION_PACING_BELOW_ACCEPTED_CEILING");
        this.minFrameIntervalMs = minFrameIntervalMs;
        this.maxFrames = maxFrames;
        this.maxTxBytes = maxTxBytes;
        this.lifetimeMs = lifetimeSeconds * 1000;
        this.fakeAckMs = fakeAckMs;
    }

    internal sealed record FrameOutcome(bool Ok, string? ErrorCode, int Frame, int PaletteColors,
                                        int ApplicationBytes, double HostElapsedMs);

    /// <summary>The three stock packets of one frame: two preambles plus the image packet.</summary>
    private static readonly byte[] PreambleA = Convert.FromHexString("0103009fa20002");
    private static readonly byte[] PreambleB = Convert.FromHexString("010400bd31f20002");

    internal FrameOutcome SendFrame(byte[] rgb, string expectedPacketSha256, CancellationToken token)
    {
        if (TerminalReason is not null) return new(false, "SESSION_NOT_ACTIVE", FramesSent, 0, 0, 0);
        var now = clock.Elapsed.TotalMilliseconds;
        if (now >= lifetimeMs)
        {
            Terminate("lifetime_expired", "stopped_clean");
            return new(false, "SESSION_LIFETIME_EXPIRED", FramesSent, 0, 0, 0);
        }
        if (FramesSent + 1 > maxFrames)
        {
            Terminate("budget_exhausted", "stopped_clean");
            return new(false, "SESSION_FRAME_BUDGET_EXHAUSTED", FramesSent, 0, 0, 0);
        }
        if (now - lastFrameStartedMs < minFrameIntervalMs)
            return new(false, "SESSION_PACING_VIOLATION", FramesSent, 0, 0, 0);

        var (packet, palette) = DitooEncoder.EncodeRgb888(rgb);
        if (!DitooEncoder.Sha256Hex(packet).Equals(expectedPacketSha256, StringComparison.OrdinalIgnoreCase))
            return new(false, "IMAGE_ENCODER_HASH_MISMATCH", FramesSent, palette, 0, 0);

        var applicationBytes = packet.Length + PreambleA.Length + PreambleB.Length;
        if (TxBytesSent + applicationBytes > maxTxBytes)
        {
            Terminate("budget_exhausted", "stopped_clean");
            return new(false, "SESSION_TX_BUDGET_EXHAUSTED", FramesSent, palette, applicationBytes, 0);
        }

        lastFrameStartedMs = now;
        PreciseDelay.Wait(fakeAckMs, token);   // the "ACK": a delay, never a device
        var elapsed = clock.Elapsed.TotalMilliseconds - now;
        FramesSent++;
        PacketsSent += 3;
        TxBytesSent += applicationBytes;
        return new(true, null, FramesSent, palette, applicationBytes, elapsed);
    }

    internal void Close(string reason)
    {
        if (TerminalReason is null) Terminate(reason, "stopped_clean");
    }

    /// <summary>Ambiguity is terminal and unknown: no resend, no reconnect, no reclaim.</summary>
    internal void Fault(string detail) => Terminate($"transport_fault:{detail}", "unknown");

    private void Terminate(string reason, string outcome)
    {
        TerminalReason ??= reason;
        TerminalOutcome ??= outcome;
    }

    internal bool Expired => clock.Elapsed.TotalMilliseconds >= lifetimeMs;
}
