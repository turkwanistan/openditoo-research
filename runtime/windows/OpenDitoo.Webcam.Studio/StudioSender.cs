using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using OpenDitoo.Webcam.Probe;
using OpenDitoo.Webcam.Runner;

namespace OpenDitoo.Webcam.Studio;

/// <summary>
/// Absolute-deadline pacing. Logical slots are start + k * interval; the earliest permitted send
/// is max(next due slot, last real send + MinGap). A send at t serves the newest slot at or before
/// t and every slot passed over is counted, never made up: there is no catch-up burst. Nothing but
/// a real transmission moves either clock, so a duplicate or unchanged frame can never be counted
/// as a sent interval.
/// </summary>
internal sealed class DeadlineClock(double start, double interval)
{
    /// <summary>The proven W8-005 client floor: 40 ms Host backstop plus 10 ms arrival margin.</summary>
    internal const double MinGapMs = Trial.W8SafeClientInterval;
    private long nextSlot;
    private double lastSent = double.NegativeInfinity;
    internal long SkippedSlots { get; private set; }
    internal long Sent { get; private set; }
    internal double EarliestSend => Math.Max(start + nextSlot * interval, lastSent + MinGapMs);

    internal void MarkSent(double at)
    {
        if (at < EarliestSend) throw new InvalidOperationException("SEND_BEFORE_DEADLINE");
        // Max() guards the floating-point edge where at == start + nextSlot * interval exactly.
        var served = Math.Max(nextSlot, (long)Math.Floor((at - start) / interval));
        SkippedSlots += served - nextSlot;
        nextSlot = served + 1;
        lastSent = at;
        Sent++;
    }
}

internal static class StudioModes
{
    /// <summary>Name -> logical slot interval. `max` is the accepted W8-005 ACK-clocked shape.</summary>
    internal static readonly IReadOnlyDictionary<string, int> IntervalMs =
        new Dictionary<string, int> { ["max"] = 50, ["10fps"] = 100, ["5fps"] = 200 };
}

internal static class StudioSender
{
    internal const int StallMs = 2000;
    internal const int StaleMs = 500;

    /// <summary>
    /// One bounded typed session: open once, one frame in flight, close once, never retry or
    /// reconnect. `client` must already carry the Host bearer token; the heartbeat shares it.
    /// </summary>
    internal static async Task<JsonObject> Run(Trial trial, IFrameSource source, HttpClient client,
        CancellationToken stop, Action<string>? progress = null, int heartbeatMs = 10_000)
    {
        using var session = new TypedSession(client);
        var reason = "lifetime_expired";
        var outcome = "stopped_clean";
        var sourceAges = new Samples();
        var dispatchIntervals = new Samples();
        var identity = new SourceIdentityLedger();
        long unchangedFrames = 0, duplicateSelections = 0, heartbeats = 0;
        byte[]? lastPixels = null;
        long lastSourceId = 0;
        double? previousDispatch = null;
        var started = WebcamFrames.NowMs;
        var clock = new DeadlineClock(started, trial.ClientIntervalMs);
        try
        {
            if (source.Fault is not null) throw new IOException(source.Fault);
            stop.ThrowIfCancellationRequested(); // stopped before open: never open just to close
            await session.Open(trial);
            var lastContact = WebcamFrames.NowMs;
            var lastFresh = lastContact;
            while (true)
            {
                var now = WebcamFrames.NowMs;
                if (now - started >= trial.Seconds * 1000) break;
                if (session.Frames >= trial.MaxFrames) { reason = "budget_exhausted"; break; }
                if (stop.IsCancellationRequested) { reason = "operator_stop"; break; }
                if (source.Fault is { } fault) { reason = fault; break; }
                if (now - lastContact >= heartbeatMs)
                {
                    // A quiet scene is legitimate silence. Prove liveness without transmitting.
                    if (!await Heartbeat(client, session.SessionId!)) { reason = "host_session_ended"; break; }
                    heartbeats++;
                    lastContact = WebcamFrames.NowMs;
                }
                var wait = clock.EarliestSend - now;
                if (wait > 0)
                {
                    await Task.Delay(TimeSpan.FromMilliseconds(Math.Min(wait, heartbeatMs)), stop);
                    continue;
                }
                if (!source.TryTake(out var frame))
                {
                    if (now - lastFresh > StallMs) { reason = "camera_stalled"; break; }
                    source.Wait(stop);
                    continue;
                }
                lastFresh = now;
                // Re-sampled after the take: a frame that landed after `now` would read as negative age.
                var age = WebcamFrames.NowMs - frame.CapturedQpcMs;
                if (age is < 0 or > StaleMs) { reason = "camera_stale"; break; }
                if (frame.SourceId <= lastSourceId) { duplicateSelections++; continue; }
                lastSourceId = frame.SourceId;
                if (lastPixels is not null && frame.Pixels.AsSpan().SequenceEqual(lastPixels))
                { unchangedFrames++; continue; }
                var bytes = DitooEncoder.EncodeRgb888(frame.Pixels).Packet.Length + 15;
                if (session.Bytes + bytes > trial.MaxBytes) { reason = "budget_exhausted"; break; }
                var dispatch = WebcamFrames.NowMs;
                clock.MarkSent(dispatch);
                if (previousDispatch is { } prior) dispatchIntervals.Add(dispatch - prior);
                previousDispatch = dispatch;
                identity.Select(frame.SourceId);
                sourceAges.Add(dispatch - frame.CapturedQpcMs);
                await session.Frame(frame); // one request in flight, never resend
                lastPixels = frame.Pixels;
                lastContact = WebcamFrames.NowMs;
                // Display only: a closing window must never turn a clean session into `unknown`.
                try
                {
                    progress?.Invoke($"sent {session.Frames}/{trial.MaxFrames}  skipped slots {clock.SkippedSlots}  " +
                        $"unchanged {unchangedFrames}  ACKed transport {session.Frames / ((lastContact - started) / 1000):F1} fps");
                }
                catch { /* telemetry never decides an outcome */ }
            }
        }
        catch (OperationCanceledException) when (stop.IsCancellationRequested)
        { reason = "operator_stop"; if (!session.OpenAttempted) outcome = "not_opened"; }
        catch (Exception ex)
        { reason = ex.Message; outcome = session.OpenAttempted ? "unknown" : "not_opened"; }
        finally
        {
            try { await session.Close(reason); }
            catch (Exception) { outcome = "unknown"; reason += ";close_unconfirmed"; }
        }
        var elapsedMs = WebcamFrames.NowMs - started;
        var result = new
        {
            outcome, terminalReason = reason, frames = session.Frames, packets = session.Frames * 3,
            bytes = session.Bytes, elapsedMs,
            // ACKed transport rate only. Panel refresh and visible cadence are unmeasured (W9B deferred).
            ackedTransportFps = elapsedMs > 0 ? session.Frames / (elapsedMs / 1000.0) : 0,
            slotIntervalMs = trial.ClientIntervalMs, minGapMs = DeadlineClock.MinGapMs,
            skippedSlots = clock.SkippedSlots, unchangedFrames, duplicateSelections, heartbeats,
            dispatchIntervalMs = dispatchIntervals.Snapshot(), sourceAgeAtSendMs = sourceAges.Snapshot(),
            ackMs = session.AckMs.Snapshot(), hostFrameMs = session.HostFrameMs.Snapshot(),
            sourceIdentity = identity.Snapshot(source.LastAcquiredSourceId),
            retry = false, reconnect = false, reclaim = false,
        };
        return JsonSerializer.SerializeToNode(result)!.AsObject();
    }

    private static async Task<bool> Heartbeat(HttpClient client, string sessionId)
    {
        using var response = await client.PostAsJsonAsync(TypedSession.Origin + "/v1/session/heartbeat", new { sessionId });
        await response.Content.LoadIntoBufferAsync(1024 * 1024);
        var body = JsonNode.Parse(await response.Content.ReadAsStringAsync());
        if (!response.IsSuccessStatusCode || body?["ok"]?.GetValue<bool>() != true)
            throw new IOException("HOST_HEARTBEAT_REFUSED");
        return body["session"]?["active"]?.GetValue<bool>() == true &&
               body["session"]?["sessionId"]?.GetValue<string>() == sessionId;
    }
}
