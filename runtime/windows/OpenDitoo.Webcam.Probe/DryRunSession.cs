namespace OpenDitoo.Webcam.Probe;

// Shared by the real-camera dry run and camera-free fault tests. Construction of the
// stand-in is the simulated open/claim boundary; only a validated first frame crosses it.
internal sealed class DryRunSession(Func<FakeTypedHostSession> open)
{
    private readonly object gate = new();
    private string? stopRequested;
    internal FakeTypedHostSession? Host { get; private set; }
    internal int OpenAttempts { get; private set; }
    internal string? TerminalReason { get; private set; }
    internal string? TerminalOutcome { get; private set; }
    internal bool Stopped => Volatile.Read(ref stopRequested) is not null;

    internal FakeTypedHostSession.FrameOutcome SendFrame(byte[] pixels, string sha, CancellationToken token)
    {
        lock (gate)
        {
            if (Stopped) return new(false, "SESSION_NOT_ACTIVE", Host?.FramesSent ?? 0, 0, 0, 0);
            if (token.IsCancellationRequested)
            {
                Stop("operator_stop");
                return new(false, "SESSION_NOT_ACTIVE", Host?.FramesSent ?? 0, 0, 0, 0);
            }
            try
            {
                // Validate before simulated authority consumption, including the encoder hash.
                var (packet, _) = DitooEncoder.EncodeRgb888(pixels);
                if (!DitooEncoder.Sha256Hex(packet).Equals(sha, StringComparison.OrdinalIgnoreCase))
                    throw new ArgumentException("IMAGE_ENCODER_HASH_MISMATCH");
                if (Host is null) { OpenAttempts++; Host = open(); }
                var outcome = Host.SendFrame(pixels, sha, token);
                if (!outcome.Ok) Stop(Host.TerminalReason ?? outcome.ErrorCode!);
                return outcome;
            }
            catch (Exception ex)
            {
                // A submission/close may have reached its destination even without a result.
                Stop(Host is null ? "camera_frame_invalid" : "transport_fault", unknown: Host is not null);
                return new(false, ex.Message, Host?.FramesSent ?? 0, 0, 0, 0);
            }
        }
    }

    internal static int SelfTest()
    {
        var failures = 0;
        var cases = new[] { "healthy_control", "camera_before_open", "camera_mid_session",
            "host_frame_fault", "ambiguous_close", "invalid_first_frame", "frame_budget",
            "byte_budget", "pacing_refusal", "lifetime", "cancelled_ack" };
        foreach (var name in cases)
        {
            // Generated pixels cross the real transform, latest slot and encoder/hash boundary.
            var raw = Enumerable.Range(0, 32 * 32 * 3).Select(i => (byte)(i * 7)).ToArray();
            var pixels = FrameTransform.Transform(raw, 32, 32, FrameTransform.Default);
            var slot = new LatestFrameSlot<byte[]>();
            slot.Put(new byte[768]);
            slot.Put(pixels);
            slot.TryTake(out var newest);
            var sha = DitooEncoder.Sha256Hex(DitooEncoder.EncodeRgb888(newest).Packet);
            var run = new DryRunSession(() => new FakeTypedHostSession(
                FakeTypedHostSession.ProfileStreamingAckClock, name == "lifetime" ? 0 : 10,
                40, name == "frame_budget" ? 1 : 10, name == "byte_budget" ? 1 : 10540,
                name == "pacing_refusal" ? 0 : 45)
            {
                FaultOnFrame = name == "host_frame_fault" ? 2 : 0,
                FaultOnClose = name == "ambiguous_close",
            });
            try
            {
                if (name == "camera_before_open") run.Stop("camera_disconnected");
                if (name == "invalid_first_frame") sha = new string('0', 64);
                using var cancel = new CancellationTokenSource();
                if (name == "cancelled_ack") cancel.CancelAfter(10);
                run.SendFrame(newest, sha, cancel.Token);
                if (name is "camera_mid_session" or "ambiguous_close") run.Stop("camera_disconnected");
                if (name is "healthy_control" or "host_frame_fault" or "frame_budget" or "pacing_refusal")
                    run.SendFrame(newest, sha, CancellationToken.None);
                run.Stop("operator_stop");
                var opens = run.OpenAttempts;
                var sends = run.Host?.SendAttempts ?? 0;
                var closes = run.Host?.CloseAttempts ?? 0;
                // Negative control: stale/new input and cleanup after a terminal do nothing.
                run.SendFrame(newest, sha, CancellationToken.None);
                run.Stop("operator_stop");
                var expectedOpens = name is "camera_before_open" or "invalid_first_frame" ? 0 : 1;
                var expectedSends = name switch
                {
                    "camera_before_open" or "invalid_first_frame" or "byte_budget" or "lifetime" => 0,
                    "healthy_control" or "host_frame_fault" => 2,
                    _ => 1,
                };
                var expectedOutcome = name switch
                {
                    "camera_before_open" or "invalid_first_frame" => "not_opened",
                    "host_frame_fault" or "ambiguous_close" or "cancelled_ack" => "unknown",
                    _ => "stopped_clean",
                };
                if (opens != expectedOpens || sends != expectedSends || closes != expectedOpens ||
                    run.OpenAttempts != opens || (run.Host?.SendAttempts ?? 0) != sends ||
                    (run.Host?.CloseAttempts ?? 0) != closes || run.TerminalOutcome != expectedOutcome ||
                    slot.Replaced != 1 || slot.Depth != 0 ||
                    (name == "cancelled_ack" && run.Host!.FramesSent != 0) ||
                    (name == "camera_mid_session" && run.TerminalReason != "camera_disconnected"))
                    throw new Exception($"opens={opens} sends={sends} closes={closes} outcome={run.TerminalOutcome}");
                Console.WriteLine($"FAULT_CASE_PASS name={name} opens={opens} sends={sends} closes={closes} outcome={run.TerminalOutcome}");
            }
            catch (Exception ex) { failures++; Console.WriteLine($"FAULT_CASE_FAIL name={name} detail={ex.Message}"); }
        }
        Console.WriteLine($"FAULT_SELFTEST_{(failures == 0 ? "PASS" : "FAIL")} cases={cases.Length} failures={failures} device_io=false camera_io=false");
        return failures == 0 ? 0 : 2;
    }

    internal void Stop(string reason, bool unknown = false)
    {
        // Publish before waiting for a possible in-flight ACK: no sibling send can overtake stop.
        Interlocked.CompareExchange(ref stopRequested, reason, null);
        lock (gate)
        {
            if (TerminalOutcome is not null) return;
            TerminalReason = unknown ? reason : stopRequested;
            TerminalOutcome = unknown ? "unknown" : Host is null ? "not_opened" : "stopped_clean";
            if (Host is null) return;
            if (unknown) Host.Fault(reason);
            try { Host.Close(TerminalReason!); }
            catch (Exception)
            {
                TerminalReason = "close_fault";
                TerminalOutcome = "unknown";
                Host.Fault("close_fault");
            }
        }
    }
}
