using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using OpenDitoo.Webcam.Probe;
using OpenDitoo.Webcam.Runner;

namespace OpenDitoo.Webcam.Studio;

/// <summary>Scheduler and sender checks against the frozen in-memory Host. No camera, no device.</summary>
internal static class StudioTests
{
    /// <summary>Adds the heartbeat route in front of the frozen fake, which refuses unknown routes.</summary>
    internal sealed class HeartbeatHandler(OfflineTests.FakeHandler inner, bool endSession = false) : DelegatingHandler(inner)
    {
        internal int Heartbeats;
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token)
        {
            if (request.RequestUri!.AbsolutePath != "/v1/session/heartbeat") return base.SendAsync(request, token);
            Heartbeats++;
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = JsonContent.Create(new
            {
                ok = true, session = new { active = !endSession, sessionId = endSession ? null : "offline" },
            }) });
        }
    }

    /// <summary>A camera whose behaviour each case scripts. Ids always come from acquisition.</summary>
    private sealed class ScriptedSource(string mode) : IFrameSource
    {
        private long acquired;
        private double lastIssue = double.NegativeInfinity;
        internal volatile string? FaultValue;
        public string? Fault => FaultValue;
        public long LastAcquiredSourceId => Interlocked.Read(ref acquired);
        public bool TryTake(out TimedFrame frame)
        {
            frame = default;
            // A ~60 fps camera: at most one new frame per 16 ms, like the real ready slot.
            if (WebcamFrames.NowMs - lastIssue < 16 || (mode == "stall" && acquired > 0)) return false;
            lastIssue = WebcamFrames.NowMs;
            var id = mode == "same_id" && acquired > 0 ? acquired : Interlocked.Increment(ref acquired);
            var value = mode == "static" ? (byte)7 : (byte)(id % 251);
            frame = new(Enumerable.Repeat(value, 768).ToArray(), 16, 16, WebcamFrames.NowMs, id);
            return true;
        }
        public void Wait(CancellationToken token) => token.WaitHandle.WaitOne(5);
    }

    private static int failures;
    private static void Check(string name, bool passed, string detail = "")
    {
        if (!passed) failures++;
        Console.WriteLine($"STUDIO_{name}_{(passed ? "PASS" : "FAIL")} {detail}".TrimEnd());
    }

    private static void ClockCases()
    {
        var onTime = new DeadlineClock(0, 100);
        foreach (var t in new[] { 0.0, 100, 200 }) onTime.MarkSent(t);
        Check("CLOCK_ON_TIME", onTime.SkippedSlots == 0 && onTime.EarliestSend == 300);

        // Late frame for slot 1 arrives at 250: slot 1 is skipped, slot 2 served, next due 300.
        var late = new DeadlineClock(0, 100);
        late.MarkSent(0);
        late.MarkSent(250);
        Check("CLOCK_SKIPS_MISSED_SLOTS", late.SkippedSlots == 1 && late.EarliestSend == 300,
            $"skipped={late.SkippedSlots} next={late.EarliestSend}");

        // Sent at 290 for slot 2: slot 3 is due at 300 but the Host-floor clock says 340.
        var floor = new DeadlineClock(0, 100);
        floor.MarkSent(0);
        floor.MarkSent(290);
        Check("CLOCK_HOST_FLOOR_WINS", floor.EarliestSend == 340, $"next={floor.EarliestSend}");

        // A long stall never turns into a burst: after it, exactly one send is permitted per slot.
        var stall = new DeadlineClock(0, 50);
        stall.MarkSent(0);
        stall.MarkSent(1000);
        var burstRefused = false;
        try { stall.MarkSent(1001); } catch (InvalidOperationException) { burstRefused = true; }
        Check("CLOCK_NO_CATCHUP_BURST", burstRefused && stall.SkippedSlots == 19 && stall.EarliestSend == 1050,
            $"skipped={stall.SkippedSlots} next={stall.EarliestSend}");

        // Time passing without a send moves nothing.
        var idle = new DeadlineClock(0, 100);
        idle.MarkSent(0);
        Check("CLOCK_IDLE_DOES_NOT_ADVANCE", idle.EarliestSend == 100 && idle.Sent == 1 && idle.SkippedSlots == 0);
    }

    private static async Task<(JsonObject Result, OfflineTests.FakeHandler Host, HeartbeatHandler Beat)> Session(
        string fault, ScriptedSource source, int intervalMs, int seconds, int maxFrames = 60,
        int heartbeatMs = 10_000, CancellationToken stop = default, bool endSession = false)
    {
        var host = new OfflineTests.FakeHandler(fault);
        var beat = new HeartbeatHandler(host, endSession);
        var trial = new Trial("OFFLINE-W10", seconds, maxFrames, maxFrames * Trial.WorstCaseFrameTxBytes, intervalMs);
        var result = await StudioSender.Run(trial, source, new HttpClient(beat), stop, heartbeatMs: heartbeatMs);
        return (result, host, beat);
    }

    private static long Long(JsonObject result, string key) => result[key]!.GetValue<long>();
    private static string Str(JsonObject result, string key) => result[key]!.GetValue<string>();

    private static void ColourCases()
    {
        var gradient = new byte[FrameTransform.FrameBytes];
        for (var i = 0; i < 256; i++) { gradient[i * 3] = (byte)i; gradient[i * 3 + 1] = (byte)(255 - i); gradient[i * 3 + 2] = (byte)(i * 7); }
        var full = DitooEncoder.EncodeRgb888(FrameTransform.QuantizeToPaletteLimit(gradient));
        foreach (var n in new[] { 64, 16, 8 })
        {
            var reduced = ColourReduce.MedianCut(gradient, n);
            var (packet, palette) = DitooEncoder.EncodeRgb888(reduced);
            Check($"COLOURS_{n}", palette <= n && packet.Length < full.Packet.Length &&
                reduced.SequenceEqual(ColourReduce.MedianCut(gradient, n)),
                $"palette={palette} bytes={packet.Length} full_bytes={full.Packet.Length}");
        }
        Check("COLOURS_255_IS_IDENTITY", ReferenceEquals(ColourReduce.MedianCut(gradient, 255), gradient));
        Check("PRESETS_MATCH_W2_NAMES", ColourReduce.Presets.All(p => p.Key == p.Value.Name) &&
            ColourReduce.Presets["srgb_area"] == FrameTransform.Default);
    }

    internal static async Task<int> Run()
    {
        ClockCases();
        ColourCases();

        // 10 fps against a 65 ms fake ACK: every slot is served on the absolute grid. A late send is
        // followed by a shorter gap back onto the grid (not a burst), so the mean, not p50, is ~100.
        var (steady, steadyHost, _) = await Session("none", new ScriptedSource("moving"), 100, 2);
        var steadyMean = steady["dispatchIntervalMs"]!["mean"]!.GetValue<double>();
        Check("SENDER_10FPS_DEADLINES", Str(steady, "outcome") == "stopped_clean" &&
            steadyHost.Frames is >= 19 and <= 21 && Long(steady, "skippedSlots") == 0 &&
            steadyMean is >= 95 and <= 105 && steadyHost.Closes == 1,
            $"frames={steadyHost.Frames} mean_dispatch_ms={steadyMean:F1} skipped={Long(steady, "skippedSlots")}");

        // max mode: the 65 ms fake ACK is slower than the 50 ms grid, so slots are skipped rather
        // than made up, and the Host floor is never violated.
        var (max, maxHost, _) = await Session("none", new ScriptedSource("moving"), 50, 2);
        Check("SENDER_MAX_SKIPS_NOT_BURSTS", Str(max, "outcome") == "stopped_clean" &&
            Long(max, "skippedSlots") > 0 && maxHost.Frames <= 2000 / 65 + 1,
            $"frames={maxHost.Frames} skipped={Long(max, "skippedSlots")}");

        // A static scene transmits once, then holds with heartbeats instead of resending.
        var (still, stillHost, stillBeat) = await Session("none", new ScriptedSource("static"), 50, 2, heartbeatMs: 400);
        Check("SENDER_UNCHANGED_NOT_SENT", Str(still, "outcome") == "stopped_clean" && stillHost.Frames == 1 &&
            Long(still, "unchangedFrames") > 10 && stillBeat.Heartbeats >= 3,
            $"frames={stillHost.Frames} unchanged={Long(still, "unchangedFrames")} heartbeats={stillBeat.Heartbeats}");

        // The same acquisition offered repeatedly is a duplicate and is never transmitted twice.
        var (dup, dupHost, _) = await Session("none", new ScriptedSource("same_id"), 50, 1);
        Check("SENDER_DUPLICATE_NOT_SENT", dupHost.Frames == 1 && Long(dup, "duplicateSelections") > 5,
            $"frames={dupHost.Frames} duplicates={Long(dup, "duplicateSelections")}");

        // Camera frames stop arriving without a Failed event: stop cleanly, do not wait forever.
        var (stall, stallHost, _) = await Session("none", new ScriptedSource("stall"), 50, 5);
        Check("SENDER_CAMERA_STALL", Str(stall, "terminalReason") == "camera_stalled" &&
            Str(stall, "outcome") == "stopped_clean" && stallHost.Closes == 1);

        // Camera unplugged mid-session: clean close, reason recorded.
        var unplug = new ScriptedSource("moving");
        var unplugTask = Session("none", unplug, 100, 5);
        await Task.Delay(500);
        unplug.FaultValue = "camera_disconnected";
        var (unplugged, unplugHost, _) = await unplugTask;
        Check("SENDER_CAMERA_DISCONNECT", Str(unplugged, "terminalReason") == "camera_disconnected" &&
            Str(unplugged, "outcome") == "stopped_clean" && unplugHost.Closes == 1 && unplugHost.Frames >= 2);

        // Operator stop (button, window close, Ctrl+C all cancel this token).
        using (var stop = new CancellationTokenSource(600))
        {
            var (stopped, stopHost, _) = await Session("none", new ScriptedSource("moving"), 100, 5, stop: stop.Token);
            Check("SENDER_OPERATOR_STOP", Str(stopped, "terminalReason") == "operator_stop" &&
                Str(stopped, "outcome") == "stopped_clean" && stopHost.Closes == 1);
        }

        // Stopped before the session opened (window closed during the handshake): never opened.
        using (var early = new CancellationTokenSource())
        {
            early.Cancel();
            var (pre, preHost, _) = await Session("none", new ScriptedSource("moving"), 100, 5, stop: early.Token);
            Check("SENDER_STOP_BEFORE_OPEN", Str(pre, "outcome") == "not_opened" && preHost.Opens == 0 && preHost.Closes == 0);
        }

        // Host loses a frame response: outcome unknown, close attempted once, no retry.
        var (lost, lostHost, _) = await Session("frame", new ScriptedSource("moving"), 100, 5);
        Check("SENDER_HOST_FAULT_NO_RETRY", Str(lost, "outcome") == "unknown" && lostHost.Attempts == 2 &&
            lostHost.Opens == 1 && lostHost.Closes == 1, $"attempts={lostHost.Attempts}");

        // Host controller busy: never opened, never closed.
        var (busy, busyHost, _) = await Session("busy", new ScriptedSource("moving"), 100, 5);
        Check("SENDER_BUSY_HOST_NOT_OPENED", Str(busy, "outcome") == "not_opened" && busyHost.Opens == 0);

        // Host ended the session under us (lifetime/watchdog): the heartbeat notices and we stop.
        var (ended, _, _) = await Session("none", new ScriptedSource("static"), 50, 5, heartbeatMs: 300, endSession: true);
        Check("SENDER_HOST_SESSION_ENDED", Str(ended, "terminalReason").StartsWith("host_session_ended"));

        // Frame budget ends the session cleanly.
        var (budget, budgetHost, _) = await Session("none", new ScriptedSource("moving"), 100, 5, maxFrames: 4);
        Check("SENDER_BUDGET", Str(budget, "terminalReason") == "budget_exhausted" && budgetHost.Frames == 4);

        Console.WriteLine($"STUDIO_SELFTEST_{(failures == 0 ? "PASS" : "FAIL")} failures={failures} device_io=false camera_io=false");
        return failures == 0 ? 0 : 2;
    }
}
