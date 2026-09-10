using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using OpenDitoo.Webcam.Probe;

namespace OpenDitoo.Webcam.Runner;

// Only the existing typed session family. The injected handler tests these exact requests.
internal sealed class TypedSession(HttpClient client) : IDisposable
{
    internal const string Origin = "http://127.0.0.1:8796";
    internal string? SessionId { get; private set; }
    internal bool OpenAttempted { get; private set; }
    internal int Frames { get; private set; }
    internal int Bytes { get; private set; }
    private bool closed;
    internal readonly Samples AckMs = new();
    internal readonly Samples HostFrameMs = new();
    internal readonly Samples HttpOverheadMs = new();

    internal static TypedSession Live(string token)
    {
        var client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false, UseProxy = false })
        { Timeout = TimeSpan.FromSeconds(7) };
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token.Trim());
        return new(client);
    }

    private async Task<JsonObject> Request(string path, object? body = null, bool requireOk = true)
    {
        using var response = body is null ? await client.GetAsync(Origin + path)
            : await client.PostAsJsonAsync(Origin + path, body);
        // Bound the body even if an unexpected service answers the fixed port.
        await response.Content.LoadIntoBufferAsync(1024 * 1024);
        var result = JsonNode.Parse(await response.Content.ReadAsStringAsync()) as JsonObject
            ?? throw new IOException("HOST_RESPONSE_INVALID");
        if (!response.IsSuccessStatusCode || (requireOk && result["ok"]?.GetValue<bool>() != true))
        {
            var code = result["errorCode"]?.GetValue<string>()
                ?? $"HOST_REQUEST_REFUSED_HTTP_{(int)response.StatusCode}";
            throw new IOException(code);
        }
        return result;
    }

    internal Task<JsonObject> GetStatus() => Request("/v1/status", requireOk: false);

    internal async Task Open(Trial trial)
    {
        // The established Day1 Host status contract is a successful identity document and
        // intentionally does not include the command-result `ok` field used by POST routes.
        // Success is the HTTP status plus the exact identity/controller checks below.
        var status = await GetStatus();
        if (status["target"]?.GetValue<string>() != Trial.Target ||
            status["bind"]?.GetValue<string>() != "127.0.0.1" ||
            status["port"]?.GetValue<int>() != 8796 ||
            status["activitySession"]?["active"]?.GetValue<bool>() == true ||
            status["diagnostics"]?["operationInProgress"]?.GetValue<bool>() == true)
            throw new IOException("HOST_IDENTITY_OR_CONTROLLER_PRECHECK_FAILED");
        OpenAttempted = true;
        var opened = await Request("/v1/session/open", new
        {
            experimentId = trial.Id, lifetimeSeconds = trial.Seconds, minFrameIntervalMs = Trial.HostFloor,
            maxFrames = trial.MaxFrames, maxTxBytes = trial.MaxBytes, sessionProfile = Trial.Profile,
        });
        // Retain identity before validating the profile, so mismatch still requests close once.
        SessionId = opened["sessionId"]?.GetValue<string>() ?? throw new IOException("SESSION_ID_MISSING");
        if (opened["sessionProfile"]?.GetValue<string>() != Trial.Profile ||
            opened["minFrameIntervalMs"]?.GetValue<int>() != Trial.HostFloor ||
            opened["sendSpacingMs"]?.GetValue<int>() != 0 ||
            opened["target"]?.GetValue<string>() != Trial.Target)
            throw new IOException("SESSION_PROFILE_NOT_CONFIRMED");
    }

    internal async Task Frame(TimedFrame frame)
    {
        var (packet, _) = DitooEncoder.EncodeRgb888(frame.Pixels);
        var sha = DitooEncoder.Sha256Hex(packet);
        var started = WebcamFrames.NowMs;
        var result = await Request("/v1/session/frame", new
        {
            sessionId = SessionId, pixelsRgb888Hex = Convert.ToHexString(frame.Pixels).ToLowerInvariant(),
            expectedImagePacketSha256 = sha,
        });
        if (result["imagePacketSha256"]?.GetValue<string>() != sha ||
            result["frame"]?.GetValue<int>() != Frames + 1 ||
            result["packetCount"]?.GetValue<int>() != 3 ||
            result["packetsSentTotal"]?.GetValue<int>() != (Frames + 1) * 3 ||
            result["txBytesSentTotal"]?.GetValue<int>() != Bytes + packet.Length + 15)
            throw new IOException("SESSION_FRAME_RESPONSE_MISMATCH");
        var totalMs = WebcamFrames.NowMs - started;
        var hostFrameMs = result["hostFrameElapsedMs"]?.GetValue<int>()
            ?? throw new IOException("HOST_FRAME_ELAPSED_MISSING");
        if (hostFrameMs < 0 || hostFrameMs > totalMs + 10)
            throw new IOException("HOST_FRAME_ELAPSED_INVALID");
        Frames++;
        Bytes += packet.Length + 15;
        AckMs.Add(totalMs);
        HostFrameMs.Add(hostFrameMs);
        HttpOverheadMs.Add(Math.Max(0, totalMs - hostFrameMs));
    }

    internal async Task Close(string reason)
    {
        if (closed || SessionId is null) return;
        closed = true;
        var result = await Request("/v1/session/close", new { sessionId = SessionId, reason });
        if (result["socketClosed"]?.GetValue<bool>() != true ||
            result["session"]?["terminalOutcome"]?.GetValue<string>() != "stopped_clean")
            throw new IOException("SESSION_CLOSE_NOT_CONFIRMED_CLEAN");
    }
    public void Dispose() => client.Dispose();
}

internal static class Sender
{
    internal static async Task<object> Run(Trial trial, IFrameSource source, TypedSession session,
                                           CancellationToken stop)
    {
        var reason = "lifetime_expired";
        var outcome = "stopped_clean";
        var sourceAges = new Samples();
        var ackAges = new Samples();
        var dispatchIntervals = new Samples();
        var quarterFrames = new int[4];
        var sourceAgesByQuarter = Enumerable.Range(0, 4).Select(_ => new Samples()).ToArray();
        var duplicateSourceFrames = 0;
        double? lastSourceTimestamp = null;
        double? previousDispatch = null;
        var started = WebcamFrames.NowMs;
        var lastDispatch = double.NegativeInfinity;
        try
        {
            if (source.Fault is not null) throw new IOException(source.Fault);
            await session.Open(trial);
            // Include open time in our deadline; the Host independently owns its watchdog.
            while (WebcamFrames.NowMs - started < trial.Seconds * 1000 && session.Frames < trial.MaxFrames)
            {
                if (stop.IsCancellationRequested) { reason = "operator_stop"; break; }
                if (source.Fault is { } fault) { reason = fault; break; }
                var wait = trial.ClientIntervalMs - (WebcamFrames.NowMs - lastDispatch);
                if (wait > 0) { await Task.Delay(TimeSpan.FromMilliseconds(wait), stop); continue; }
                if (!source.TryTake(out var frame)) { source.Wait(stop); continue; }
                var age = WebcamFrames.NowMs - frame.CapturedQpcMs;
                if (age is < 0 or > 500) { reason = "camera_stale"; break; }
                if (source.Fault is { } finalFault) { reason = finalFault; break; }
                if (WebcamFrames.NowMs - started >= trial.Seconds * 1000) break;
                var bytes = DitooEncoder.EncodeRgb888(frame.Pixels).Packet.Length + 15;
                if (session.Bytes + bytes > trial.MaxBytes) { reason = "budget_exhausted"; break; }
                var dispatch = WebcamFrames.NowMs;
                if (previousDispatch is { } prior) dispatchIntervals.Add(dispatch - prior);
                previousDispatch = dispatch;
                lastDispatch = dispatch;
                if (lastSourceTimestamp is { } priorSource && frame.CapturedQpcMs == priorSource)
                    duplicateSourceFrames++;
                lastSourceTimestamp = frame.CapturedQpcMs;
                var quarter = Math.Max(0, Math.Min(3,
                    (int)Math.Floor((dispatch - started) / (trial.Seconds * 1000.0 / 4.0))));
                sourceAges.Add(age);
                sourceAgesByQuarter[quarter].Add(age);
                await session.Frame(frame); // one request in flight, never resend
                ackAges.Add(WebcamFrames.NowMs - frame.CapturedQpcMs);
                quarterFrames[quarter]++;
            }
            if (session.Frames == trial.MaxFrames) reason = "budget_exhausted";
        }
        catch (OperationCanceledException) when (stop.IsCancellationRequested)
        { reason = "operator_stop"; }
        catch (Exception ex)
        { reason = ex.Message; outcome = session.OpenAttempted ? "unknown" : "not_opened"; }
        finally
        {
            try { await session.Close(reason); }
            catch (Exception) { outcome = "unknown"; reason += ";close_unconfirmed"; }
        }
        var elapsedMs = WebcamFrames.NowMs - started;
        var quarterSeconds = trial.Seconds / 4.0;
        var fpsByQuarter = quarterFrames.Select(count => count / quarterSeconds).ToArray();
        return new { outcome, terminalReason = reason, frames = session.Frames, packets = session.Frames * 3,
            bytes = session.Bytes, elapsedMs,
            effectiveFps = elapsedMs > 0 ? session.Frames / (elapsedMs / 1000.0) : 0,
            clientIntervalMs = trial.ClientIntervalMs,
            framesByQuarter = quarterFrames, fpsByQuarter,
            sourceAgeAtSendMs = sourceAges.Snapshot(),
            sourceAgeAtSendMsByQuarter = sourceAgesByQuarter.Select(samples => samples.Snapshot()).ToArray(),
            sourceAgeAtAckMs = ackAges.Snapshot(),
            dispatchIntervalMs = dispatchIntervals.Snapshot(), duplicateSourceFrames,
            ackMs = session.AckMs.Snapshot(), hostFrameMs = session.HostFrameMs.Snapshot(),
            httpOverheadMs = session.HttpOverheadMs.Snapshot(),
            retry = false, reconnect = false, reclaim = false };
    }
}
