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
    masterTransmitEnabled = false,
    bluetoothTouched = false,
    transportConfigured = false,
    targetBound = false,
    capabilities = new[] { "status" },
    deviceIo = false,
    purpose = "offline_environment_readiness_only"
}));

// Deliberately no discovery, pairing, Bluetooth, target, raw-send or device routes.
await app.RunAsync();
return 0;
