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
    // Product operating floor after the exact-unit R1-R5 ladder. R4 sustained full-colour
    // motion at 131.0 ms/frame (7.63 fps) for 67 s; R5 reached 54.2 ms (18.46 fps) with
    // no sleeps. 150 ms (6.67 fps) keeps jitter headroom and yields a readable ~0.60 s
    // four-stage crown pulse. The Host refuses anything faster, whatever the caller asks.
    internal const int AcceptedMinFrameIntervalMs = 150;
    // R2b/R3/R4 physically accepted 10 ms spacing. Retaining that small proven gap gives
    // the 150 ms frame-start budget ample ACK/jitter headroom without running at R5's
    // zero-idle ceiling. This is fixed for the activity session, not caller-configurable.
    internal const int ActivitySendSpacingMs = 10;

    // -- session profiles --------------------------------------------------
    //
    // Two shapes, both already physically accepted, selected by NAME rather than by
    // caller-supplied timing. A caller may pick a profile; it may never hand us numbers.
    //
    // "activity" is the MCP dashboard: 150 ms floor, 10 ms packet spacing. Unchanged, and
    // what an absent profile resolves to, so every existing caller keeps its exact
    // behaviour.
    //
    // "streaming_ack_clock" is R5's shape: zero packet spacing, and pacing governed by the
    // ACK rather than by a clock. R5 ran 1024 full-colour frames this way in 55.5 s with
    // one ACK per frame and no tearing.
    //
    // Why the floor drops but does not vanish: OPENDITOO-S2-STREAM-RATE-001 died on frame
    // 10 with a pacing violation because a client dispatching AT the floor can arrive a
    // millisecond early, and a violation is terminal. Under an ACK clock that race cannot
    // happen -- the client physically cannot send before the previous ACK returns, so it
    // cannot be early. The floor is therefore no longer the pacing mechanism, but it is
    // kept as a BACKSTOP: the Host, not the client, must remain the thing that bounds the
    // rate, and 40 ms sits comfortably under R5's 53 ms median ACK so it never gates a
    // healthy link. If ACKs ever returned instantly, this is what still holds.
    internal const string ProfileActivity = "activity";
    internal const string ProfileStreamingAckClock = "streaming_ack_clock";
    internal const int StreamingMinFrameIntervalMs = 40;
    internal const int StreamingSendSpacingMs = 0;

    private static string profile = ProfileActivity;

    internal static int FloorFor(string? requested) =>
        Normalize(requested) == ProfileStreamingAckClock
            ? StreamingMinFrameIntervalMs : AcceptedMinFrameIntervalMs;

    internal static int SpacingFor(string? requested) =>
        Normalize(requested) == ProfileStreamingAckClock
            ? StreamingSendSpacingMs : ActivitySendSpacingMs;

    /// <summary>An unknown profile name is a refusal, never a silent fallback.</summary>
    internal static string Normalize(string? requested)
    {
        if (string.IsNullOrWhiteSpace(requested)) return ProfileActivity;
        if (requested == ProfileActivity || requested == ProfileStreamingAckClock) return requested;
        throw new SessionRejectedException("SESSION_PROFILE_UNKNOWN", 400);
    }

    internal const int MaxLifetimeSeconds = 900;
    internal const int MaxFrames = 500;
    internal const int WatchdogIntervalMs = 250;
    // If the worker disappears entirely we end the session rather than hold the link
    // open. Liveness is proved by /v1/session/heartbeat, NOT by sending a frame: a
    // change-only display is legitimately silent for long stretches, and treating that
    // silence as a dead worker is what ended OPENDITOO-M9-ACTIVATION-001 at 30 s.
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
                                    int frameBudget, int txByteBudget, string? sessionProfile = null)
    {
        lock (Gate)
        {
            var requestedProfile = Normalize(sessionProfile);
            if (IsActive) throw new SessionRejectedException("SESSION_ALREADY_ACTIVE", 409);
            if (string.IsNullOrWhiteSpace(experimentId) || experimentId.Length > 128)
                throw new SessionRejectedException("SESSION_EXPERIMENT_ID_INVALID", 400);
            if (lifetimeSeconds <= 0 || lifetimeSeconds > MaxLifetimeSeconds)
                throw new SessionRejectedException("SESSION_LIFETIME_INVALID", 400);
            if (minIntervalMs < FloorFor(requestedProfile))
                throw new SessionRejectedException("SESSION_PACING_BELOW_ACCEPTED_CEILING", 400);
            if (frameBudget <= 0 || frameBudget > MaxFrames)
                throw new SessionRejectedException("SESSION_FRAME_BUDGET_INVALID", 400);
            if (txByteBudget <= 0)
                throw new SessionRejectedException("SESSION_TX_BUDGET_INVALID", 400);
            if (LedgerContains(experimentId))
                throw new SessionRejectedException("AUTHORITY_ALREADY_CONSUMED", 409);

            ExperimentId = experimentId;
            profile = requestedProfile;
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
            Append("open", new { lifetimeSeconds, minIntervalMs, frameBudget, txByteBudget,
                                 sessionProfile = profile, sendSpacingMs = SpacingFor(profile) });

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
                                       int PaletteColors, int PacketsSent, int TxBytesSent,
                                       string DeadlineUtc, int HostFrameElapsedMs);

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
                link.SendFrameGroup(packets, null, framesSent, SpacingFor(profile));
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
            // The Host's own send-to-ACK figure. A client can only measure HTTP round trip,
            // which folds in transport it does not own; S2 had to infer the difference.
            var hostElapsedMs = (int)(Environment.TickCount64 - lastFrameStartedTicks);
            return new FrameResult(framesSent, hex, encoded.PacketSha256, encoded.PaletteColors,
                                   packetsSent, txBytesSent, deadline.ToString("O"), hostElapsedMs);
        }
    }

    /// <summary>
    /// Worker liveness plus a read of the session's own state. No device I/O and no
    /// send: this is how a change-only worker stays alive through a quiet scene, and
    /// how it learns within one poll that the session has ended -- rather than finding
    /// out only when it next has something to draw.
    /// </summary>
    internal static object Heartbeat(string sessionId)
    {
        lock (Gate)
        {
            if (IsActive && string.Equals(sessionId, SessionId, StringComparison.Ordinal))
                lastWorkerContact = DateTimeOffset.UtcNow;
            return Snapshot();
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
                sessionProfile = profile,
                sendSpacingMs = SpacingFor(profile),
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
