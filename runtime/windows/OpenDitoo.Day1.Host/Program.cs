using System.Net;
using System.Security.Cryptography;
using System.Text;

const int ApiVersion = 1;
const int Port = 8796;
const int MinTokenChars = 32;

static int Fail(string message)
{
    Console.Error.WriteLine($"OpenDitoo Day1 Host configuration error: {message}");
    return 2;
}

string? tokenFile = null;
string? sessionLedger = null;
for (var i = 0; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--token-file" when i + 1 < args.Length:
            tokenFile = args[++i];
            break;
        case "--session-ledger" when i + 1 < args.Length:
            sessionLedger = args[++i];
            break;
        // Offline receive-assembler self-check over a shared fixture. Starts no server,
        // opens no socket, needs no token: it is how the C# receive path is exercised
        // from the repository without a device or a test framework.
        case "--selftest" when i + 1 < args.Length:
            return DitooReportAssembler.SelfTest(args[++i]);
        default:
            return Fail($"unknown or incomplete argument: {args[i]}");
    }
}

if (string.IsNullOrWhiteSpace(tokenFile))
    return Fail("--token-file is required");
if (!File.Exists(tokenFile))
    return Fail($"token file not found: {tokenFile}");

var token = (await File.ReadAllTextAsync(tokenFile)).Trim();
if (token.Length < MinTokenChars)
    return Fail($"token must contain at least {MinTokenChars} characters");

var builder = WebApplication.CreateSlimBuilder(args: Array.Empty<string>());
builder.WebHost.ConfigureKestrel(options => options.Listen(IPAddress.Loopback, Port));
var app = builder.Build();
var imageGate = new SemaphoreSlim(1, 1);

// A display session holds the SAME single-operation gate as image-show and
// image-sequence, so the three can never overlap on one device link.
ActivitySessionHost.ConfigureLedger(sessionLedger
    ?? Path.Combine(Path.GetDirectoryName(tokenFile)!, "session-ledger.jsonl"));
ActivitySessionHost.OnRelease = () => imageGate.Release();

app.Use(async (context, next) =>
{
    var supplied = context.Request.Headers.Authorization.ToString();
    const string Prefix = "Bearer ";
    if (!supplied.StartsWith(Prefix, StringComparison.Ordinal))
    {
        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        return;
    }
    var expectedBytes = Encoding.UTF8.GetBytes(token);
    var candidateBytes = Encoding.UTF8.GetBytes(supplied[Prefix.Length..]);
    var valid = expectedBytes.Length == candidateBytes.Length &&
        CryptographicOperations.FixedTimeEquals(expectedBytes, candidateBytes);
    if (!valid)
    {
        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        return;
    }
    await next();
});

app.MapGet("/v1/status", () => Results.Json(new
{
    apiVersion = ApiVersion,
    service = "OpenDitoo Day1 Host",
    hostRuntime = ".NET",
    bind = "127.0.0.1",
    port = Port,
    masterTransmitEnabled = true,
    bluetoothTouched = false,
    transportConfigured = true,
    targetBound = true,
    rawSendEnabled = false,
    capabilities = new[] { "status", "image-show", "image-sequence", "activity-session" },
    deviceIo = false,
    target = DitooStaticImageProtocol.TargetMac,
    purpose = "typed_runtime_static_image_control",

    // Diagnostics: Host readiness only. Status never touches Bluetooth, so it
    // cannot report device connectivity; a past success is not present truth.
    statusPerformsDeviceIo = false,
    hostStartedAtUtc = ImageOperationLog.HostStartedAtUtc.ToString("O"),
    hostUptimeSeconds = (long)(DateTimeOffset.UtcNow - ImageOperationLog.HostStartedAtUtc).TotalSeconds,
    deviceConnectivity = "unknown",
    deviceConnectivityBasis = "no_active_observation",
    operationHistoryScope = "volatile_since_host_start",
    diagnostics = ImageOperationLog.Snapshot(),
    activitySession = ActivitySessionHost.Snapshot(),
}));

app.MapPost("/v1/image/show", (ShowImageRequest request) =>
{
    if (!imageGate.Wait(0))
        return Results.Json(new { ok = false, errorCode = "IMAGE_BUSY" }, statusCode: StatusCodes.Status409Conflict);
    var operation = ImageOperationLog.Begin();
    try
    {
        IResult Reject(string errorCode, object body, int statusCode)
        {
            operation.Finish("rejected", null, errorCode);
            return Results.Json(body, statusCode: statusCode);
        }

        if (string.IsNullOrWhiteSpace(request.PixelsRgb888Hex))
            return Reject("IMAGE_RGB_REQUIRED", new { ok = false, errorCode = "IMAGE_RGB_REQUIRED" }, StatusCodes.Status400BadRequest);
        byte[] rgb;
        try
        {
            rgb = Convert.FromHexString(request.PixelsRgb888Hex);
        }
        catch (FormatException)
        {
            return Reject("IMAGE_RGB_INVALID_HEX", new { ok = false, errorCode = "IMAGE_RGB_INVALID_HEX" }, StatusCodes.Status400BadRequest);
        }
        if (rgb.Length != DitooStaticImageProtocol.RgbBytes)
            return Reject("IMAGE_RGB_LENGTH", new { ok = false, errorCode = "IMAGE_RGB_LENGTH", expectedBytes = DitooStaticImageProtocol.RgbBytes, actualBytes = rgb.Length }, StatusCodes.Status400BadRequest);

        DitooStaticImageProtocol.EncodedImage encoded;
        try
        {
            encoded = DitooStaticImageProtocol.EncodeRgb888(rgb);
        }
        catch (ArgumentException ex)
        {
            return Reject("IMAGE_ENCODING_REJECTED", new { ok = false, errorCode = "IMAGE_ENCODING_REJECTED", message = ex.Message }, StatusCodes.Status400BadRequest);
        }
        if (string.IsNullOrWhiteSpace(request.ExpectedImagePacketSha256) ||
            !encoded.PacketSha256.Equals(request.ExpectedImagePacketSha256, StringComparison.OrdinalIgnoreCase))
        {
            return Reject("IMAGE_ENCODER_HASH_MISMATCH", new
            {
                ok = false,
                errorCode = "IMAGE_ENCODER_HASH_MISMATCH",
                hostImagePacketSha256 = encoded.PacketSha256,
            }, StatusCodes.Status400BadRequest);
        }
        operation.Encoded(encoded.PacketSha256, encoded.PaletteColors);

        try
        {
            PairedDitooTargetGuard.RequireAuthenticatedExactTarget();
        }
        catch (PairingRequiredException ex)
        {
            return Reject("IMAGE_PAIRING_REQUIRED", new { ok = false, errorCode = "IMAGE_PAIRING_REQUIRED", message = ex.Message }, StatusCodes.Status409Conflict);
        }
        operation.StageCompleted("target_precheck");

        var packets = DitooStaticImageProtocol.BuildTransaction(encoded.Packet);
        operation.Planned(packets);
        try
        {
            var ack = WindowsRfcommStaticImageTransport.ExchangeOnce(packets, operation);
            operation.Finish("ok", $"0x{ack:X2}", null);
            return Results.Json(new
            {
                ok = true,
                apiVersion = ApiVersion,
                command = "image-show",
                target = DitooStaticImageProtocol.TargetMac,
                deviceIo = true,
                packetCount = packets.Length,
                txBytesTotal = packets.Sum(packet => packet.Length),
                imagePacketSha256 = encoded.PacketSha256,
                paletteColors = encoded.PaletteColors,
                ackPayloadHex = $"0x{ack:X2}",
                connectionsAttempted = 1,
                socketClosed = true,
                retry = false,
                operationId = operation.OperationId,
                lastCompletedStage = operation.LastCompletedStage,
            });
        }
        catch (Exception ex)
        {
            operation.Finish("failed", null, ex is TimeoutException ? "IMAGE_TRANSPORT_TIMEOUT" : "IMAGE_TRANSPORT_FAIL_CLOSED");
            return Results.Json(new
            {
                ok = false,
                errorCode = "IMAGE_TRANSPORT_FAIL_CLOSED",
                message = $"{ex.GetType().Name}: {ex.Message}",
                retry = false,
                operationId = operation.OperationId,
                lastCompletedStage = operation.LastCompletedStage,
                packetsSentComplete = operation.PacketsSentComplete,
                txBytesSentComplete = operation.TxBytesSentComplete,
                inFlightPacketBytesUnknown = operation.InFlightPacketBytesUnknown,
            }, statusCode: StatusCodes.Status502BadGateway);
        }
    }
    finally
    {
        ImageOperationLog.End(operation);
        imageGate.Release();
    }
});

app.MapPost("/v1/image/sequence", (ShowSequenceRequest request) =>
{
    // M8 bounded sequence: one connection, ordered frames, one ACK each, then close.
    // Same single-operation gate as image-show, so it can never overlap one.
    if (!imageGate.Wait(0))
        return Results.Json(new { ok = false, errorCode = "IMAGE_BUSY" }, statusCode: StatusCodes.Status409Conflict);
    var operation = ImageOperationLog.Begin();
    try
    {
        IResult Reject(string errorCode, object body, int statusCode)
        {
            operation.Finish("rejected", null, errorCode);
            return Results.Json(body, statusCode: statusCode);
        }

        var requested = request.Frames ?? Array.Empty<SequenceFrameRequest>();
        if (requested.Length < 1 || requested.Length > DitooStaticImageProtocol.MaxSequenceFrames)
            return Reject("IMAGE_SEQUENCE_FRAME_COUNT", new { ok = false, errorCode = "IMAGE_SEQUENCE_FRAME_COUNT", maxFrames = DitooStaticImageProtocol.MaxSequenceFrames }, StatusCodes.Status400BadRequest);
        var delay = request.InterFrameDelayMs;
        if (delay < DitooStaticImageProtocol.MinInterFrameDelayMs || delay > DitooStaticImageProtocol.MaxInterFrameDelayMs)
            return Reject("IMAGE_SEQUENCE_DELAY", new { ok = false, errorCode = "IMAGE_SEQUENCE_DELAY", minMs = DitooStaticImageProtocol.MinInterFrameDelayMs, maxMs = DitooStaticImageProtocol.MaxInterFrameDelayMs }, StatusCodes.Status400BadRequest);
        // Absent means the stock-derived default; a reviewed manifest may lower it to
        // measure whether that value is load-bearing, never raise it.
        var spacing = request.SendSpacingMs ?? DitooStaticImageProtocol.DefaultSendSpacingMs;
        if (spacing < DitooStaticImageProtocol.MinSendSpacingMs || spacing > DitooStaticImageProtocol.MaxSendSpacingMs)
            return Reject("IMAGE_SEND_SPACING", new { ok = false, errorCode = "IMAGE_SEND_SPACING", minMs = DitooStaticImageProtocol.MinSendSpacingMs, maxMs = DitooStaticImageProtocol.MaxSendSpacingMs }, StatusCodes.Status400BadRequest);

        // Every frame is validated and hash-checked before ANY device I/O, so a bad
        // second frame can never be discovered halfway through a live sequence.
        var encoded = new DitooStaticImageProtocol.EncodedImage[requested.Length];
        for (var i = 0; i < requested.Length; i++)
        {
            var frame = requested[i];
            if (string.IsNullOrWhiteSpace(frame.PixelsRgb888Hex))
                return Reject("IMAGE_RGB_REQUIRED", new { ok = false, errorCode = "IMAGE_RGB_REQUIRED", frame = i + 1 }, StatusCodes.Status400BadRequest);
            byte[] rgb;
            try
            {
                rgb = Convert.FromHexString(frame.PixelsRgb888Hex);
            }
            catch (FormatException)
            {
                return Reject("IMAGE_RGB_INVALID_HEX", new { ok = false, errorCode = "IMAGE_RGB_INVALID_HEX", frame = i + 1 }, StatusCodes.Status400BadRequest);
            }
            if (rgb.Length != DitooStaticImageProtocol.RgbBytes)
                return Reject("IMAGE_RGB_LENGTH", new { ok = false, errorCode = "IMAGE_RGB_LENGTH", frame = i + 1, expectedBytes = DitooStaticImageProtocol.RgbBytes, actualBytes = rgb.Length }, StatusCodes.Status400BadRequest);
            try
            {
                encoded[i] = DitooStaticImageProtocol.EncodeRgb888(rgb);
            }
            catch (ArgumentException ex)
            {
                return Reject("IMAGE_ENCODING_REJECTED", new { ok = false, errorCode = "IMAGE_ENCODING_REJECTED", frame = i + 1, message = ex.Message }, StatusCodes.Status400BadRequest);
            }
            if (string.IsNullOrWhiteSpace(frame.ExpectedImagePacketSha256) ||
                !encoded[i].PacketSha256.Equals(frame.ExpectedImagePacketSha256, StringComparison.OrdinalIgnoreCase))
            {
                return Reject("IMAGE_ENCODER_HASH_MISMATCH", new { ok = false, errorCode = "IMAGE_ENCODER_HASH_MISMATCH", frame = i + 1, hostImagePacketSha256 = encoded[i].PacketSha256 }, StatusCodes.Status400BadRequest);
            }
        }
        if (encoded.Select(item => item.PacketSha256).Distinct(StringComparer.OrdinalIgnoreCase).Count() < 2 && requested.Length > 1)
            return Reject("IMAGE_SEQUENCE_FRAMES_IDENTICAL", new { ok = false, errorCode = "IMAGE_SEQUENCE_FRAMES_IDENTICAL", message = "an A->B order test needs two different frames" }, StatusCodes.Status400BadRequest);
        operation.Encoded(encoded[0].PacketSha256, encoded[0].PaletteColors);

        try
        {
            PairedDitooTargetGuard.RequireAuthenticatedExactTarget();
        }
        catch (PairingRequiredException ex)
        {
            return Reject("IMAGE_PAIRING_REQUIRED", new { ok = false, errorCode = "IMAGE_PAIRING_REQUIRED", message = ex.Message }, StatusCodes.Status409Conflict);
        }
        operation.StageCompleted("target_precheck");

        var groups = encoded.Select(item => DitooStaticImageProtocol.BuildTransaction(item.Packet)).ToArray();
        operation.Planned(groups.SelectMany(group => group).ToArray());
        try
        {
            var startedAt = DateTimeOffset.UtcNow;
            var acks = WindowsRfcommStaticImageTransport.ExchangeSequenceOnce(groups, delay, operation, request.TotalBudgetMs, spacing);
            operation.Finish("ok", string.Join(",", acks.Select(ack => $"0x{ack:X2}")), null);
            return Results.Json(new
            {
                ok = true,
                apiVersion = ApiVersion,
                command = "image-sequence",
                target = DitooStaticImageProtocol.TargetMac,
                deviceIo = true,
                frameCount = groups.Length,
                packetCount = groups.Sum(group => group.Length),
                txBytesTotal = groups.Sum(group => group.Sum(packet => packet.Length)),
                imagePacketSha256Ordered = encoded.Select(item => item.PacketSha256).ToArray(),
                paletteColorsOrdered = encoded.Select(item => item.PaletteColors).ToArray(),
                ackPayloadHexOrdered = acks.Select(ack => $"0x{ack:X2}").ToArray(),
                interFrameDelayMs = delay,
                sendSpacingMs = spacing,
                connectionsAttempted = 1,
                socketClosed = true,
                retry = false,
                reconnect = false,
                operationId = operation.OperationId,
                lastCompletedStage = operation.LastCompletedStage,
                frameTimings = operation.FrameTimings,
                elapsedMs = (long)(DateTimeOffset.UtcNow - startedAt).TotalMilliseconds,
            });
        }
        catch (Exception ex)
        {
            operation.Finish("failed", null, ex is TimeoutException ? "IMAGE_SEQUENCE_TIMEOUT" : "IMAGE_SEQUENCE_FAIL_CLOSED");
            return Results.Json(new
            {
                ok = false,
                errorCode = "IMAGE_SEQUENCE_FAIL_CLOSED",
                message = $"{ex.GetType().Name}: {ex.Message}",
                retry = false,
                reconnect = false,
                operationId = operation.OperationId,
                lastCompletedStage = operation.LastCompletedStage,
                packetsSentComplete = operation.PacketsSentComplete,
                txBytesSentComplete = operation.TxBytesSentComplete,
                inFlightPacketBytesUnknown = operation.InFlightPacketBytesUnknown,
            }, statusCode: StatusCodes.Status502BadGateway);
        }
    }
    finally
    {
        ImageOperationLog.End(operation);
        imageGate.Release();
    }
});


// --------------------------------------------------------------------------
// Bounded activity display session (M9). Open once against a reviewed experiment
// id, push only CHANGED frames, close. The Host owns the bounds: lifetime, pacing
// floor and budgets are enforced here by a watchdog that outlives the caller, and
// the experiment id is consumed on disk before the socket exists.
// --------------------------------------------------------------------------

IResult SessionFault(SessionRejectedException ex) =>
    Results.Json(new { ok = false, errorCode = ex.Code, retry = false, reconnect = false, reclaim = false },
                 statusCode: ex.StatusCode);

app.MapPost("/v1/session/open", (OpenSessionRequest request) =>
{
    if (!imageGate.Wait(0))
        return Results.Json(new { ok = false, errorCode = "IMAGE_BUSY" }, statusCode: StatusCodes.Status409Conflict);
    try
    {
        // An absent profile is the activity dashboard's, so every existing caller keeps its
        // exact behaviour; an unrecognised one is refused rather than quietly defaulted.
        var opened = ActivitySessionHost.Open(request.ExperimentId, request.LifetimeSeconds,
                                              request.MinFrameIntervalMs, request.MaxFrames,
                                              request.MaxTxBytes, request.SessionProfile);
        return Results.Json(new
        {
            ok = true,
            apiVersion = ApiVersion,
            command = "session-open",
            target = DitooStaticImageProtocol.TargetMac,
            deviceIo = true,
            experimentId = request.ExperimentId,
            sessionId = opened.SessionId,
            deadlineUtc = opened.DeadlineUtc,
            minFrameIntervalMs = opened.MinFrameIntervalMs,
            sessionProfile = ActivitySessionHost.Normalize(request.SessionProfile),
            sendSpacingMs = ActivitySessionHost.SpacingFor(request.SessionProfile),
            connectionsAttempted = 1,
            retry = false,
            reconnect = false,
        });
    }
    catch (SessionRejectedException ex)
    {
        imageGate.Release();
        return SessionFault(ex);
    }
    catch (PairingRequiredException ex)
    {
        imageGate.Release();
        return Results.Json(new { ok = false, errorCode = "IMAGE_PAIRING_REQUIRED", message = ex.Message },
                            statusCode: StatusCodes.Status409Conflict);
    }
    catch (Exception ex)
    {
        // Open failed after the id was consumed. The gate is released by the terminal
        // record; the authority is not, and never will be.
        return Results.Json(new
        {
            ok = false,
            errorCode = "SESSION_OPEN_FAIL_CLOSED",
            message = $"{ex.GetType().Name}: {ex.Message}",
            retry = false,
            reconnect = false,
            session = ActivitySessionHost.Snapshot(),
        }, statusCode: StatusCodes.Status502BadGateway);
    }
});

app.MapPost("/v1/session/frame", (SessionFrameRequest request) =>
{
    byte[] rgb;
    try
    {
        rgb = Convert.FromHexString(request.PixelsRgb888Hex ?? "");
    }
    catch (FormatException)
    {
        return Results.Json(new { ok = false, errorCode = "IMAGE_RGB_INVALID_HEX" }, statusCode: StatusCodes.Status400BadRequest);
    }
    if (rgb.Length != DitooStaticImageProtocol.RgbBytes)
        return Results.Json(new { ok = false, errorCode = "IMAGE_RGB_LENGTH", expectedBytes = DitooStaticImageProtocol.RgbBytes },
                            statusCode: StatusCodes.Status400BadRequest);
    try
    {
        var sent = ActivitySessionHost.SendFrame(request.SessionId ?? "", rgb, request.ExpectedImagePacketSha256 ?? "");
        return Results.Json(new
        {
            ok = true,
            apiVersion = ApiVersion,
            command = "session-frame",
            deviceIo = true,
            frame = sent.Frame,
            ackPayloadHex = sent.AckPayloadHex,
            imagePacketSha256 = sent.ImagePacketSha256,
            paletteColors = sent.PaletteColors,
            packetCount = 3,
            packetsSentTotal = sent.PacketsSent,
            txBytesSentTotal = sent.TxBytesSent,
            // The Host's own send-to-ACK time. A client can only see HTTP round trip, which
            // folds in transport it does not own; S2 had to infer the difference.
            hostFrameElapsedMs = sent.HostFrameElapsedMs,
            deadlineUtc = sent.DeadlineUtc,
            retry = false,
            reconnect = false,
        });
    }
    catch (SessionRejectedException ex)
    {
        return Results.Json(new
        {
            ok = false,
            errorCode = ex.Code,
            retry = false,
            reconnect = false,
            reclaim = false,
            session = ActivitySessionHost.Snapshot(),
        }, statusCode: ex.StatusCode);
    }
    catch (Exception ex)
    {
        return Results.Json(new
        {
            ok = false,
            errorCode = "SESSION_FRAME_FAIL_CLOSED",
            message = $"{ex.GetType().Name}: {ex.Message}",
            retry = false,
            reconnect = false,
            session = ActivitySessionHost.Snapshot(),
        }, statusCode: StatusCodes.Status502BadGateway);
    }
});

app.MapPost("/v1/session/heartbeat", (CloseSessionRequest request) => Results.Json(new
{
    ok = true,
    apiVersion = ApiVersion,
    command = "session-heartbeat",
    deviceIo = false,
    session = ActivitySessionHost.Heartbeat(request.SessionId ?? ""),
}));

app.MapPost("/v1/session/close", (CloseSessionRequest request) =>
{
    try
    {
        return Results.Json(new
        {
            ok = true,
            apiVersion = ApiVersion,
            command = "session-close",
            deviceIo = false,
            socketClosed = true,
            session = ActivitySessionHost.Close(request.SessionId ?? "", request.Reason ?? "operator_stop"),
        });
    }
    catch (SessionRejectedException ex)
    {
        return SessionFault(ex);
    }
});

await app.RunAsync();
return 0;

sealed record ShowImageRequest(string PixelsRgb888Hex, string ExpectedImagePacketSha256);
sealed record SequenceFrameRequest(string PixelsRgb888Hex, string ExpectedImagePacketSha256);
sealed record ShowSequenceRequest(SequenceFrameRequest[] Frames, int InterFrameDelayMs, int TotalBudgetMs, int? SendSpacingMs);
sealed record OpenSessionRequest(string ExperimentId, int LifetimeSeconds, int MinFrameIntervalMs, int MaxFrames, int MaxTxBytes, string? SessionProfile);
sealed record SessionFrameRequest(string SessionId, string PixelsRgb888Hex, string ExpectedImagePacketSha256);
sealed record CloseSessionRequest(string SessionId, string Reason);
