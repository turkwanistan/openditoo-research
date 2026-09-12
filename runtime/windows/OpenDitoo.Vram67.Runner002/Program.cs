using System.Security.Cryptography;
using System.Text.Json;

static string Sha256File(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
static void Require(bool condition, string message)
{
    if (!condition) throw new InvalidOperationException(message);
}

if (args.Length != 2 || args[0] != "--repo-root")
{
    Console.Error.WriteLine("VRAM67_USAGE_REJECTED: only --repo-root <exact checkout> is accepted");
    return 64;
}

var repoRoot = Path.GetFullPath(args[1]);
var manifestPath = Path.Combine(repoRoot, "experiments", "OPENDITOO-VRAM67-BXLR-002.json");
var fixturePath = Path.Combine(repoRoot, "artifacts", "analysis", "volatile_ram_api_vram67_fixture_002.json");
var localDir = Path.Combine(repoRoot, ".openditoo-local", "vram67-bxlr-002");
var grantPath = Path.Combine(localDir, "grant.json");
var handoverPath = Path.Combine(localDir, "handover.json");
var claimPath = Path.Combine(localDir, "claim.json");
var resultPath = Path.Combine(localDir, "result.json");

try
{
    FrozenVram67Protocol.VerifyFrozenConstants();
    Require(File.Exists(manifestPath), "VRAM67_MANIFEST_MISSING");
    Require(File.Exists(fixturePath), "VRAM67_FIXTURE_REPORT_MISSING");
    Require(File.Exists(grantPath), "VRAM67_EXACT_GRANT_NOT_MATERIALIZED");
    Require(File.Exists(handoverPath), "VRAM67_RUNTIME018_HANDOVER_NOT_PROVEN");
    Require(!File.Exists(claimPath), "VRAM67_ONE_USE_CLAIM_ALREADY_EXISTS");

    using var manifestDoc = JsonDocument.Parse(File.ReadAllText(manifestPath));
    var manifest = manifestDoc.RootElement;
    Require(manifest.GetProperty("experiment_id").GetString() == FrozenVram67Protocol.ExperimentId, "VRAM67_MANIFEST_ID_MISMATCH");
    Require(manifest.GetProperty("status").GetString() == "grant_ready_awaiting_named_grant", "VRAM67_MANIFEST_STATUS_REJECTED");
    Require(manifest.GetProperty("authority").GetProperty("required_grant_text").GetString() == FrozenVram67Protocol.RequiredGrantText, "VRAM67_MANIFEST_GRANT_TEXT_DRIFT");
    Require(manifest.GetProperty("authority").GetProperty("transmission_authorized").GetBoolean() is false, "VRAM67_COMMITTED_MANIFEST_MUST_REMAIN_UNAUTHORIZED");
    Require(manifest.GetProperty("transport_budget").GetProperty("max_connections").GetInt32() == 1, "VRAM67_MANIFEST_CONNECTION_BUDGET_DRIFT");
    Require(manifest.GetProperty("transport_budget").GetProperty("exact_application_sends").GetInt32() == 3, "VRAM67_MANIFEST_SEND_BUDGET_DRIFT");
    Require(manifest.GetProperty("transport_budget").GetProperty("max_custom_0x6c_sends").GetInt32() == 1, "VRAM67_MANIFEST_CUSTOM_SEND_BUDGET_DRIFT");
    Require(manifest.GetProperty("transport_budget").GetProperty("retry").GetBoolean() is false, "VRAM67_MANIFEST_RETRY_DRIFT");
    Require(manifest.GetProperty("target").GetProperty("mac").GetString() == FrozenVram67Protocol.TargetMac, "VRAM67_MANIFEST_TARGET_DRIFT");
    Require(manifest.GetProperty("target").GetProperty("rfcomm_channel").GetInt32() == FrozenVram67Protocol.TargetRfcommChannel, "VRAM67_MANIFEST_CHANNEL_DRIFT");
    Require(manifest.GetProperty("target").GetProperty("installed_firmware_version_assumption").GetInt32() == FrozenVram67Protocol.ExpectedInstalledVersion, "VRAM67_MANIFEST_VERSION_DRIFT");
    Require(manifest.GetProperty("fixture_report").GetProperty("sha256").GetString() == Sha256File(fixturePath), "VRAM67_MANIFEST_FIXTURE_HASH_DRIFT");
    foreach (var item in manifest.GetProperty("execution_surface").GetProperty("files").EnumerateArray())
    {
        var relative = item.GetProperty("path").GetString() ?? throw new InvalidOperationException("VRAM67_EXECUTION_PATH_MISSING");
        var expected = item.GetProperty("sha256").GetString() ?? throw new InvalidOperationException("VRAM67_EXECUTION_HASH_MISSING");
        var full = Path.Combine(repoRoot, relative.Replace('/', Path.DirectorySeparatorChar));
        Require(File.Exists(full), $"VRAM67_EXECUTION_FILE_MISSING {relative}");
        Require(Sha256File(full) == expected, $"VRAM67_EXECUTION_FILE_HASH_MISMATCH {relative}");
    }

    using var grantDoc = JsonDocument.Parse(File.ReadAllText(grantPath));
    var grant = grantDoc.RootElement;
    Require(grant.GetProperty("experiment_id").GetString() == FrozenVram67Protocol.ExperimentId, "VRAM67_GRANT_ID_MISMATCH");
    Require(grant.GetProperty("grant_text").GetString() == FrozenVram67Protocol.RequiredGrantText, "VRAM67_GRANT_TEXT_MISMATCH");
    Require(grant.GetProperty("manual_stock_btplayer_selected").GetBoolean(), "VRAM67_BTPLAYER_ATTESTATION_MISSING");
    Require(grant.GetProperty("manifest_sha256").GetString() == Sha256File(manifestPath), "VRAM67_GRANT_MANIFEST_HASH_MISMATCH");
    Require(grant.GetProperty("fixture_report_sha256").GetString() == Sha256File(fixturePath), "VRAM67_GRANT_FIXTURE_HASH_MISMATCH");
    var nonce = grant.GetProperty("one_use_nonce").GetString() ?? "";
    Require(nonce.Length == 64 && nonce.All(Uri.IsHexDigit), "VRAM67_GRANT_NONCE_REJECTED");

    using var handoverDoc = JsonDocument.Parse(File.ReadAllText(handoverPath));
    var handover = handoverDoc.RootElement;
    Require(handover.GetProperty("experiment_id").GetString() == FrozenVram67Protocol.ExperimentId, "VRAM67_HANDOVER_ID_MISMATCH");
    Require(handover.GetProperty("one_use_nonce").GetString() == nonce, "VRAM67_HANDOVER_NONCE_MISMATCH");
    Require(handover.GetProperty("runtime018_service_inactive").GetBoolean(), "VRAM67_RUNTIME018_NOT_INACTIVE");
    Require(handover.GetProperty("manifest_sha256").GetString() == Sha256File(manifestPath), "VRAM67_HANDOVER_MANIFEST_HASH_MISMATCH");

    Directory.CreateDirectory(localDir);
    var claim = JsonSerializer.Serialize(new
    {
        schema_version = 1,
        experiment_id = FrozenVram67Protocol.ExperimentId,
        manifest_sha256 = Sha256File(manifestPath),
        fixture_report_sha256 = Sha256File(fixturePath),
        one_use_nonce = nonce,
        claimed_at_utc = DateTimeOffset.UtcNow,
        state = "CONSUMED_BEFORE_BLUETOOTH_OPEN_NO_RETRY"
    }, new JsonSerializerOptions { WriteIndented = true });
    using (var fs = new FileStream(claimPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
    using (var sw = new StreamWriter(fs))
        sw.Write(claim);

    var result = WindowsRfcommVram67Transport.RunExactlyOnce();
    var resultJson = JsonSerializer.Serialize(new
    {
        schema_version = 1,
        experiment_id = FrozenVram67Protocol.ExperimentId,
        outcome = "candidate_pass_transport_observation",
        connections_attempted = result.ConnectionsAttempted,
        application_sends_completed = result.SendsCompleted,
        custom_0x6c_sends = result.CustomOverwriteSends,
        retry = false,
        observation_ms = result.ObservationMilliseconds,
        connection_survived_observation = result.ConnectionSurvivedObservation,
        completed_at_utc = DateTimeOffset.UtcNow,
        note = "Runtime 018 restoration/liveness remains required before final PASS interpretation."
    }, new JsonSerializerOptions { WriteIndented = true });
    File.WriteAllText(resultPath, resultJson + Environment.NewLine);
    Console.WriteLine("VRAM67_TRANSPORT_OBSERVATION=PASS");
    Console.WriteLine("VRAM67_CONNECTIONS=1");
    Console.WriteLine("VRAM67_APPLICATION_SENDS=3");
    Console.WriteLine($"VRAM67_CUSTOM_0X6C_SENDS={result.CustomOverwriteSends}");
    Console.WriteLine("VRAM67_RETRY=false");
    Console.WriteLine($"VRAM67_OBSERVATION_MS={result.ObservationMilliseconds}");
    return 0;
}
catch (WindowsRfcommVram67Transport.TransportStopException ex)
{
    try
    {
        Directory.CreateDirectory(localDir);
        File.WriteAllText(resultPath, JsonSerializer.Serialize(new
        {
            schema_version = 1,
            experiment_id = FrozenVram67Protocol.ExperimentId,
            outcome = "stopped_no_retry",
            error = ex.Message,
            connections_attempted = ex.ConnectionsAttempted,
            application_sends_completed = ex.SendsCompleted,
            custom_0x6c_sends = ex.CustomOverwriteSends,
            completed_at_utc = DateTimeOffset.UtcNow,
            retry = false,
        }, new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine);
    }
    catch { }
    Console.Error.WriteLine($"VRAM67_STOP_NO_RETRY: {ex.Message}");
    return 31;
}
catch (Exception ex)
{
    try
    {
        Directory.CreateDirectory(localDir);
        File.WriteAllText(resultPath, JsonSerializer.Serialize(new
        {
            schema_version = 1,
            experiment_id = FrozenVram67Protocol.ExperimentId,
            outcome = "stopped_no_retry_pretransport_or_validation",
            error = ex.Message,
            completed_at_utc = DateTimeOffset.UtcNow,
            retry = false,
        }, new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine);
    }
    catch { }
    Console.Error.WriteLine($"VRAM67_STOP_NO_RETRY: {ex.Message}");
    return 31;
}
