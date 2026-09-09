using System.Security.Cryptography;
using System.Text.Json;

/// <summary>
/// A bounded activity-display session, owned and bounded by the HOST.
///
/// The worker decides what to draw; it does not decide how long, how fast, or how much.
/// Lifetime, pacing floor and byte/frame budgets are enforced here by a watchdog that
/// keeps running when the worker disappears, so a dropped HTTP client or a hung caller
/// cannot silently leave a live link sending or leave authority re-usable.
///
/// One use per experiment id, recorded on disk before the socket is opened. A crash
/// therefore leaves a claim with no terminal record, which reads as an unknown outcome
/// and refuses re-entry. There is no reset path, by construction.
/// </summary>
static class ActivitySessionHost
{
    // The rate measured and accepted twice at M8. The Host will not accept a manifest
    // that paces faster, whatever the caller asks for.
    internal const int AcceptedMinFrameIntervalMs = 1118;
    internal const int MaxLifetimeSeconds = 900;
    internal const int MaxFrames = 500;
    internal const int WatchdogIntervalMs = 250;
    // If the worker stops asking for frames entirely we still end the session rather
    // than hold the device's link open indefinitely.
    internal const int WorkerSilenceGraceMs = 30_000;

    private static readonly object Gate = new();
    /// <summary>Set by the Host so a live session holds the same single-operation gate
    /// that image-show and image-sequence use. Released exactly once, on terminal.</summary>
    internal static Action? OnRelease;
    private static bool releaseIssued;
    private static WindowsRfcommStaticImageTransport.DitooLink? link;
    private static Timer? watchdog;
    private static string ledgerPath = "";

    internal static string? SessionId { get; private set; }
    internal static string? ExperimentId { get; private set; }
    internal static bool IsActive => SessionId is not null;

    private static DateTimeOffset startedAt, deadline, lastWorkerContact;
    private static int minFrameIntervalMs, maxFrames, maxTxBytes;
    private static int framesSent, packetsSent, txBytesSent;
    private static long lastFrameStartedTicks;
    private static string terminalReason = "", terminalOutcome = "";
    private static string displayState = "unknown_nothing_sent";
    private static readonly List<string> acks = [];

    internal static void ConfigureLedger(string path) => ledgerPath = path;

    // -- durable one-use authority ----------------------------------------

    private static bool LedgerContains(string experimentId)
    {
        if (!File.Exists(ledgerPath)) return false;
        foreach (var line in File.ReadLines(ledgerPath))
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            try
            {
                using var doc = JsonDocument.Parse(line);
                if (doc.RootElement.TryGetProperty("experimentId", out var value) &&
                    string.Equals(value.GetString(), experimentId, StringComparison.Ordinal))
                    return true;
            }
            catch (JsonException)
            {
                // A corrupt ledger line must never be read as "this id is free".
                return true;
            }
        }
        return false;
    }

    private static void Append(string kind, object record)
    {
        var line = JsonSerializer.Serialize(new
        {
            kind,
            atUtc = DateTimeOffset.UtcNow.ToString("O"),
            experimentId = ExperimentId,
            sessionId = SessionId,
            detail = record,
        });
        var directory = Path.GetDirectoryName(ledgerPath);
        if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);
        File.AppendAllText(ledgerPath, line + Environment.NewLine);
    }

    // -- lifecycle ---------------------------------------------------------

    internal sealed record OpenResult(string SessionId, string DeadlineUtc, int MinFrameIntervalMs);

    internal static OpenResult Open(string experimentId, int lifetimeSeconds, int minIntervalMs,
                                    int frameBudget, int txByteBudget)
    {
        lock (Gate)
        {
            if (IsActive) throw new SessionRejectedException("SESSION_ALREADY_ACTIVE", 409);
            if (string.IsNullOrWhiteSpace(experimentId) || experimentId.Length > 128)
                throw new SessionRejectedException("SESSION_EXPERIMENT_ID_INVALID", 400);
            if (lifetimeSeconds <= 0 || lifetimeSeconds > MaxLifetimeSeconds)
                throw new SessionRejectedException("SESSION_LIFETIME_INVALID", 400);
            if (minIntervalMs < AcceptedMinFrameIntervalMs)
                throw new SessionRejectedException("SESSION_PACING_BELOW_ACCEPTED_CEILING", 400);
            if (frameBudget <= 0 || frameBudget > MaxFrames)
                throw new SessionRejectedException("SESSION_FRAME_BUDGET_INVALID", 400);
            if (txByteBudget <= 0)
                throw new SessionRejectedException("SESSION_TX_BUDGET_INVALID", 400);
            if (LedgerContains(experimentId))
                throw new SessionRejectedException("AUTHORITY_ALREADY_CONSUMED", 409);

            ExperimentId = experimentId;
            SessionId = Convert.ToHexString(RandomNumberGenerator.GetBytes(6)).ToLowerInvariant();
            startedAt = DateTimeOffset.UtcNow;
            deadline = startedAt.AddSeconds(lifetimeSeconds);
            lastWorkerContact = startedAt;
            minFrameIntervalMs = minIntervalMs;
            maxFrames = frameBudget;
            maxTxBytes = txByteBudget;
            framesSent = packetsSent = txBytesSent = 0;
            releaseIssued = false;
            lastFrameStartedTicks = 0;
            terminalReason = terminalOutcome = "";
            displayState = "unknown_nothing_sent";
            acks.Clear();

            // Claimed on disk BEFORE the socket exists, so a crash during connect still
            // consumes the id rather than leaving it silently re-armable.
            Append("open", new { lifetimeSeconds, minIntervalMs, frameBudget, txByteBudget });

            PairedDitooTargetGuard.RequireAuthenticatedExactTarget();
            try
            {
                link = WindowsRfcommStaticImageTransport.DitooLink.Connect(null);
            }
            catch
            {
                Terminate("open_failed", "unknown");
                throw;
            }
            watchdog = new Timer(_ => Tick(), null, WatchdogIntervalMs, WatchdogIntervalMs);
            return new OpenResult(SessionId!, deadline.ToString("O"), minFrameIntervalMs);
        }
    }

    internal sealed record FrameResult(int Frame, string AckPayloadHex, string ImagePacketSha256,
                                       int PaletteColors, int PacketsSent, int TxBytesSent, string DeadlineUtc);

    internal static FrameResult SendFrame(string sessionId, byte[] rgb, string expectedPacketSha256)
    {
        lock (Gate)
        {
            RequireSession(sessionId);
            lastWorkerContact = DateTimeOffset.UtcNow;
            if (DateTimeOffset.UtcNow >= deadline)
            {
                Terminate("lifetime_expired", "stopped_clean");
                throw new SessionRejectedException("SESSION_LIFETIME_EXPIRED", 409);
            }
            if (framesSent + 1 > maxFrames)
            {
                Terminate("budget_exhausted", "stopped_clean");
                throw new SessionRejectedException("SESSION_FRAME_BUDGET_EXHAUSTED", 409);
            }
            var sinceLast = lastFrameStartedTicks == 0
                ? int.MaxValue
                : (int)((Environment.TickCount64 - lastFrameStartedTicks));
            if (sinceLast < minFrameIntervalMs)
                throw new SessionRejectedException("SESSION_PACING_VIOLATION", 429);

            var encoded = DitooStaticImageProtocol.EncodeRgb888(rgb);
            if (!encoded.PacketSha256.Equals(expectedPacketSha256, StringComparison.OrdinalIgnoreCase))
                throw new SessionRejectedException("IMAGE_ENCODER_HASH_MISMATCH", 400);
            var packets = DitooStaticImageProtocol.BuildTransaction(encoded.Packet);
            var frameBytes = packets.Sum(packet => packet.Length);
            if (txBytesSent + frameBytes > maxTxBytes)
            {
                Terminate("budget_exhausted", "stopped_clean");
                throw new SessionRejectedException("SESSION_TX_BUDGET_EXHAUSTED", 409);
            }

            // Anything already waiting on the link before we send means the canvas moved
            // under us. Check first, then send.
            foreach (var report in link!.PollIdle())
            {
                if (!report.IsAck) { YieldCanvas(report); throw new SessionRejectedException("SESSION_CANVAS_INVALIDATED", 409); }
            }

            lastFrameStartedTicks = Environment.TickCount64;
            DitooReport ack;
            try
            {
                link.SendFrameGroup(packets, null, framesSent);
                ack = link.ReadOneAck(DitooStaticImageProtocol.AckBudgetMs);
            }
            catch (DitooTakeoverException takeover)
            {
                YieldCanvas(takeover.Report);
                throw new SessionRejectedException("SESSION_CANVAS_INVALIDATED", 409);
            }
            catch (Exception ex)
            {
                // Ambiguous or failed: the session is over and its outcome is unknown.
                // No resend, no reconnect, no reclaim frame.
                Terminate("transport_fault", "unknown", ex.Message);
                throw;
            }

            framesSent++;
            packetsSent += packets.Length;
            txBytesSent += frameBytes;
            displayState = "ours_last_acked";
            var hex = $"0x{ack.Payload[0]:X2}";
            acks.Add(hex);
            return new FrameResult(framesSent, hex, encoded.PacketSha256, encoded.PaletteColors,
                                   packetsSent, txBytesSent, deadline.ToString("O"));
        }
    }

    internal static object Close(string sessionId, string reason)
    {
        lock (Gate)
        {
            RequireSession(sessionId);
            Terminate(string.IsNullOrWhiteSpace(reason) ? "operator_stop" : reason, "stopped_clean");
            return Snapshot();
        }
    }

    internal static object Snapshot()
    {
        lock (Gate)
        {
            return new
            {
                active = IsActive,
                experimentId = ExperimentId,
                sessionId = SessionId,
                startedAtUtc = startedAt == default ? null : startedAt.ToString("O"),
                deadlineUtc = deadline == default ? null : deadline.ToString("O"),
                minFrameIntervalMs,
                framesSent,
                packetsSent,
                txBytesSent,
                maxFrames,
                maxTxBytes,
                ackPayloadHexOrdered = acks.ToArray(),
                displayState,
                terminalReason = terminalReason == "" ? null : terminalReason,
                terminalOutcome = terminalOutcome == "" ? null : terminalOutcome,
                retry = false,
                reconnect = false,
                reclaim = false,
            };
        }
    }

    private static void RequireSession(string sessionId)
    {
        if (!IsActive) throw new SessionRejectedException("SESSION_NOT_ACTIVE", 409);
        if (!string.Equals(sessionId, SessionId, StringComparison.Ordinal))
            throw new SessionRejectedException("SESSION_ID_MISMATCH", 409);
    }

    private static void YieldCanvas(DitooReport report)
    {
        displayState = "unknown_not_ours";
        Terminate("canvas_invalidated", "stopped_yielded_to_stock", report.Describe());
    }

    /// <summary>Watchdog: the Host's own bound, independent of the worker's existence.</summary>
    private static void Tick()
    {
        lock (Gate)
        {
            if (!IsActive) return;
            var now = DateTimeOffset.UtcNow;
            if (now >= deadline) { Terminate("lifetime_expired", "stopped_clean"); return; }
            if ((now - lastWorkerContact).TotalMilliseconds > WorkerSilenceGraceMs)
            {
                Terminate("worker_silent", "stopped_clean");
                return;
            }
            try
            {
                foreach (var report in link!.PollIdle())
                {
                    if (!report.IsAck) { YieldCanvas(report); return; }
                }
            }
            catch (Exception ex)
            {
                Terminate("transport_fault", "unknown", ex.Message);
            }
        }
    }

    private static void Terminate(string reason, string outcome, string detail = "")
    {
        if (terminalReason == "") { terminalReason = reason; terminalOutcome = outcome; }
        else if (SessionId is null) return;  // already torn down; never release twice
        try { watchdog?.Dispose(); } catch { /* a dead timer cannot revive the session */ }
        watchdog = null;
        try { link?.Dispose(); } catch { /* the socket is gone either way */ }
        link = null;
        Append("terminal", new { reason, outcome, detail, framesSent, packetsSent, txBytesSent, displayState });
        SessionId = null;
        if (!releaseIssued) { releaseIssued = true; OnRelease?.Invoke(); }
    }
}

sealed class SessionRejectedException(string code, int statusCode) : Exception(code)
{
    internal string Code { get; } = code;
    internal int StatusCode { get; } = statusCode;
}
