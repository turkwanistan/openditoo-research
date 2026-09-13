using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;

static void Require(bool condition, string message)
{
    if (!condition) throw new InvalidOperationException(message);
}

static string Sha256File(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

static void WriteCreateNewJson(string path, object value)
{
    var json = JsonSerializer.Serialize(value, new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine;
    using var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None);
    using var sw = new StreamWriter(fs);
    sw.Write(json);
}

if (args.Length != 2 || args[0] != "--repo-root")
{
    Console.Error.WriteLine("VRAM8B_USAGE_REJECTED: only --repo-root <exact checkout> is accepted");
    return 64;
}

var repoRoot = Path.GetFullPath(args[1]);
var localDir = Path.Combine(repoRoot, ".openditoo-local", "vram8b-canary-001");
var grantPath = Path.Combine(localDir, "grant.json");
var handoverPath = Path.Combine(localDir, "handover.json");
var executionPath = Path.Combine(localDir, "execution.json");
var claimPath = Path.Combine(localDir, "claim.json");
var resultPath = Path.Combine(localDir, "result.json");
var manifestPath = Path.Combine(repoRoot, "experiments", "OPENDITOO-VRAM8B-CANARY-001.json");
var fixtureReportPath = Path.Combine(repoRoot, "artifacts", "analysis", "volatile_ram_api_vram8b_fixture.json");
var claimed = false;
string? assemblySha = null;

try
{
    FrozenVram8BProtocol.VerifyCommittedManifest(repoRoot);
    var fixtures = FrozenVram8BProtocol.LoadAndVerifyFixtures(repoRoot);
    Require(File.Exists(grantPath), "VRAM8B_EXACT_GRANT_NOT_MATERIALIZED");
    Require(File.Exists(handoverPath), "VRAM8B_RUNTIME018_HANDOVER_NOT_PROVEN");
    Require(File.Exists(executionPath), "VRAM8B_EXECUTION_SEAL_MISSING");
    Require(!File.Exists(claimPath), "VRAM8B_ONE_USE_CLAIM_ALREADY_EXISTS");
    Require(!File.Exists(resultPath), "VRAM8B_RESULT_ALREADY_EXISTS");

    using var grantDoc = JsonDocument.Parse(File.ReadAllText(grantPath));
    var grant = grantDoc.RootElement;
    Require(grant.GetProperty("experiment_id").GetString() == FrozenVram8BProtocol.ExperimentId, "VRAM8B_GRANT_ID_MISMATCH");
    Require(grant.GetProperty("grant_text").GetString() == FrozenVram8BProtocol.RequiredGrantText, "VRAM8B_GRANT_TEXT_MISMATCH");
    Require(grant.GetProperty("manual_stock_btplayer_selected").GetBoolean(), "VRAM8B_BTPLAYER_ATTESTATION_MISSING");
    Require(grant.GetProperty("granted_by").GetString() == "owner", "VRAM8B_GRANT_OWNER_MISMATCH");
    Require(grant.GetProperty("state").GetString() == "AUTHORIZED_UNCONSUMED", "VRAM8B_GRANT_STATE_REJECTED");
    Require(grant.GetProperty("manifest_sha256").GetString() == FrozenVram8BProtocol.ManifestSha256, "VRAM8B_GRANT_MANIFEST_HASH_MISMATCH");
    Require(grant.GetProperty("fixture_report_sha256").GetString() == FrozenVram8BProtocol.FixtureReportSha256, "VRAM8B_GRANT_FIXTURE_HASH_MISMATCH");
    var nonce = grant.GetProperty("one_use_nonce").GetString() ?? "";
    Require(nonce.Length == 64 && nonce.All(Uri.IsHexDigit), "VRAM8B_GRANT_NONCE_REJECTED");

    using var handoverDoc = JsonDocument.Parse(File.ReadAllText(handoverPath));
    var handover = handoverDoc.RootElement;
    Require(handover.GetProperty("experiment_id").GetString() == FrozenVram8BProtocol.ExperimentId, "VRAM8B_HANDOVER_ID_MISMATCH");
    Require(handover.GetProperty("one_use_nonce").GetString() == nonce, "VRAM8B_HANDOVER_NONCE_MISMATCH");
    Require(handover.GetProperty("manifest_sha256").GetString() == FrozenVram8BProtocol.ManifestSha256, "VRAM8B_HANDOVER_MANIFEST_HASH_MISMATCH");
    Require(handover.GetProperty("runtime018_service_inactive").GetBoolean(), "VRAM8B_RUNTIME018_NOT_INACTIVE");

    using var executionDoc = JsonDocument.Parse(File.ReadAllText(executionPath));
    var execution = executionDoc.RootElement;
    Require(execution.GetProperty("experiment_id").GetString() == FrozenVram8BProtocol.ExperimentId, "VRAM8B_EXECUTION_ID_MISMATCH");
    Require(execution.GetProperty("one_use_nonce").GetString() == nonce, "VRAM8B_EXECUTION_NONCE_MISMATCH");
    Require(execution.GetProperty("manifest_sha256").GetString() == FrozenVram8BProtocol.ManifestSha256, "VRAM8B_EXECUTION_MANIFEST_HASH_MISMATCH");
    Require(execution.GetProperty("fixture_report_sha256").GetString() == FrozenVram8BProtocol.FixtureReportSha256, "VRAM8B_EXECUTION_FIXTURE_HASH_MISMATCH");

    var assemblyPath = Assembly.GetExecutingAssembly().Location;
    assemblySha = Sha256File(assemblyPath);
    Require(execution.GetProperty("assembly_sha256").GetString() == assemblySha, "VRAM8B_EXECUTION_ASSEMBLY_HASH_MISMATCH");
    foreach (var item in execution.GetProperty("source_files").EnumerateArray())
    {
        var relative = item.GetProperty("path").GetString() ?? throw new InvalidOperationException("VRAM8B_EXECUTION_SOURCE_PATH_MISSING");
        var expected = item.GetProperty("sha256").GetString() ?? throw new InvalidOperationException("VRAM8B_EXECUTION_SOURCE_HASH_MISSING");
        var full = Path.Combine(repoRoot, relative.Replace('/', Path.DirectorySeparatorChar));
        Require(File.Exists(full), $"VRAM8B_EXECUTION_SOURCE_MISSING {relative}");
        Require(Sha256File(full) == expected, $"VRAM8B_EXECUTION_SOURCE_HASH_MISMATCH {relative}");
    }

    Directory.CreateDirectory(localDir);
    WriteCreateNewJson(claimPath, new
    {
        schema_version = 1,
        experiment_id = FrozenVram8BProtocol.ExperimentId,
        manifest_sha256 = FrozenVram8BProtocol.ManifestSha256,
        fixture_report_sha256 = FrozenVram8BProtocol.FixtureReportSha256,
        execution_assembly_sha256 = assemblySha,
        one_use_nonce = nonce,
        claimed_at_utc = DateTimeOffset.UtcNow,
        state = "CONSUMED_BEFORE_BLUETOOTH_OPEN_NO_RETRY"
    });
    claimed = true;

    var result = WindowsRfcommVram8BTransport.RunExactlyOnce(fixtures);
    WriteCreateNewJson(resultPath, new
    {
        schema_version = 1,
        experiment_id = FrozenVram8BProtocol.ExperimentId,
        outcome = "candidate_pass_typed_canary_transport",
        connections_attempted = result.ConnectionsAttempted,
        application_sends_completed = result.SendsCompleted,
        custom_0x6c_sends = result.CustomOverwriteSends,
        retry = false,
        reconnect = false,
        baseline_value = result.BaselineValue,
        post_stage0_value = result.PostValue,
        restored_value = result.RestoredValue,
        observation_ms = result.ObservationMilliseconds,
        connection_survived_observation = result.ConnectionSurvivedObservation,
        execution_assembly_sha256 = assemblySha,
        completed_at_utc = DateTimeOffset.UtcNow,
        note = "Runtime 018 restoration/liveness remains required before final PASS interpretation."
    });
    Console.WriteLine("VRAM8B_TRANSPORT_TYPED_CANARY=PASS");
    Console.WriteLine("VRAM8B_TYPED_VALUES=0->1->0");
    Console.WriteLine("VRAM8B_CONNECTIONS=1");
    Console.WriteLine("VRAM8B_APPLICATION_SENDS=8");
    Console.WriteLine("VRAM8B_CUSTOM_0X6C_SENDS=1");
    Console.WriteLine("VRAM8B_RETRY=false");
    return 0;
}
catch (WindowsRfcommVram8BTransport.TransportStopException ex)
{
    if (claimed && !File.Exists(resultPath))
    {
        try
        {
            WriteCreateNewJson(resultPath, new
            {
                schema_version = 1,
                experiment_id = FrozenVram8BProtocol.ExperimentId,
                outcome = "stopped_no_retry",
                error = ex.Message,
                connections_attempted = ex.ConnectionsAttempted,
                application_sends_completed = ex.SendsCompleted,
                custom_0x6c_sends = ex.CustomOverwriteSends,
                retry = false,
                reconnect = false,
                execution_assembly_sha256 = assemblySha,
                completed_at_utc = DateTimeOffset.UtcNow
            });
        }
        catch { }
    }
    Console.Error.WriteLine($"VRAM8B_STOP_NO_RETRY: {ex.Message}");
    return 31;
}
catch (Exception ex)
{
    if (claimed && !File.Exists(resultPath))
    {
        try
        {
            WriteCreateNewJson(resultPath, new
            {
                schema_version = 1,
                experiment_id = FrozenVram8BProtocol.ExperimentId,
                outcome = "stopped_no_retry_after_claim",
                error = ex.Message,
                retry = false,
                reconnect = false,
                execution_assembly_sha256 = assemblySha,
                completed_at_utc = DateTimeOffset.UtcNow
            });
        }
        catch { }
    }
    Console.Error.WriteLine($"VRAM8B_STOP_NO_RETRY: {ex.Message}");
    return 31;
}
