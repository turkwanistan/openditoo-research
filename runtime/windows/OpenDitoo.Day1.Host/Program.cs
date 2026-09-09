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
    purpose = "typed_runtime_static_image_control"
}));

app.MapPost("/v1/image/show", (ShowImageRequest request) =>
{
    if (!imageGate.Wait(0))
        return Results.Json(new { ok = false, errorCode = "IMAGE_BUSY" }, statusCode: StatusCodes.Status409Conflict);
    try
    {
        if (string.IsNullOrWhiteSpace(request.PixelsRgb888Hex))
            return Results.BadRequest(new { ok = false, errorCode = "IMAGE_RGB_REQUIRED" });
        byte[] rgb;
        try
        {
            rgb = Convert.FromHexString(request.PixelsRgb888Hex);
        }
        catch (FormatException)
        {
            return Results.BadRequest(new { ok = false, errorCode = "IMAGE_RGB_INVALID_HEX" });
        }
        if (rgb.Length != DitooStaticImageProtocol.RgbBytes)
            return Results.BadRequest(new { ok = false, errorCode = "IMAGE_RGB_LENGTH", expectedBytes = DitooStaticImageProtocol.RgbBytes, actualBytes = rgb.Length });

        DitooStaticImageProtocol.EncodedImage encoded;
        try
        {
            encoded = DitooStaticImageProtocol.EncodeRgb888(rgb);
        }
        catch (ArgumentException ex)
        {
            return Results.BadRequest(new { ok = false, errorCode = "IMAGE_ENCODING_REJECTED", message = ex.Message });
        }
        if (string.IsNullOrWhiteSpace(request.ExpectedImagePacketSha256) ||
            !encoded.PacketSha256.Equals(request.ExpectedImagePacketSha256, StringComparison.OrdinalIgnoreCase))
        {
            return Results.BadRequest(new
            {
                ok = false,
                errorCode = "IMAGE_ENCODER_HASH_MISMATCH",
                hostImagePacketSha256 = encoded.PacketSha256,
            });
        }

        try
        {
            PairedDitooTargetGuard.RequireAuthenticatedExactTarget();
        }
        catch (PairingRequiredException ex)
        {
            return Results.Json(new { ok = false, errorCode = "IMAGE_PAIRING_REQUIRED", message = ex.Message }, statusCode: StatusCodes.Status409Conflict);
        }

        var packets = DitooStaticImageProtocol.BuildTransaction(encoded.Packet);
        try
        {
            var ack = WindowsRfcommStaticImageTransport.ExchangeOnce(packets);
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
            });
        }
        catch (Exception ex)
        {
            return Results.Json(new
            {
                ok = false,
                errorCode = "IMAGE_TRANSPORT_FAIL_CLOSED",
                message = $"{ex.GetType().Name}: {ex.Message}",
                retry = false,
            }, statusCode: StatusCodes.Status502BadGateway);
        }
    }
    finally
    {
        imageGate.Release();
    }
});

await app.RunAsync();
return 0;

sealed record ShowImageRequest(string PixelsRgb888Hex, string ExpectedImagePacketSha256);
