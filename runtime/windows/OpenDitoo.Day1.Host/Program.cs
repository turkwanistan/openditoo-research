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
for (var i = 0; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--token-file" when i + 1 < args.Length:
            tokenFile = args[++i];
            break;
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
    capabilities = new[] { "status", "image-show" },
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

await app.RunAsync();
return 0;

sealed record ShowImageRequest(string PixelsRgb888Hex, string ExpectedImagePacketSha256);
