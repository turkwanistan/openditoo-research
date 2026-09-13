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
    Console.Error.WriteLine("MODEL009_USAGE_REJECTED: only --repo-root <exact checkout> is accepted");
    return 64;
}

var repoRoot = Path.GetFullPath(args[1]);
var localDir = Path.Combine(repoRoot, ".openditoo-local", "vram8b-model-sentinel-009");
var grantPath = Path.Combine(localDir, "grant.json");
var handoverPath = Path.Combine(localDir, "handover.json");
var executionPath = Path.Combine(localDir, "execution.json");
var claimPath = Path.Combine(localDir, "claim.json");
var resultPath = Path.Combine(localDir, "result.json");
var claimed = false;
string? assemblySha = null;

try
{
    FrozenModelSentinel009Protocol.VerifyCommittedManifest(repoRoot);
    var fixtures = FrozenModelSentinel009Protocol.LoadAndVerifyFixtures(repoRoot);
    Require(File.Exists(grantPath), "MODEL009_EXACT_GRANT_NOT_MATERIALIZED");
    Require(File.Exists(handoverPath), "MODEL009_RUNTIME018_HANDOVER_NOT_PROVEN");
    Require(File.Exists(executionPath), "MODEL009_EXECUTION_SEAL_MISSING");
    Require(!File.Exists(claimPath), "MODEL009_ONE_USE_CLAIM_ALREADY_EXISTS");
    Require(!File.Exists(resultPath), "MODEL009_RESULT_ALREADY_EXISTS");

    using var grantDoc = JsonDocument.Parse(File.ReadAllText(grantPath));
    var grant = grantDoc.RootElement;
    Require(grant.GetProperty("experiment_id").GetString() == FrozenModelSentinel009Protocol.ExperimentId, "MODEL009_GRANT_ID_MISMATCH");
    Require(grant.GetProperty("grant_text").GetString() == FrozenModelSentinel009Protocol.RequiredGrantText, "MODEL009_GRANT_TEXT_MISMATCH");
    Require(grant.GetProperty("manual_stock_btplayer_selected").GetBoolean(), "MODEL009_BTPLAYER_ATTESTATION_MISSING");
    Require(grant.GetProperty("granted_by").GetString() == "owner", "MODEL009_GRANT_OWNER_MISMATCH");
    Require(grant.GetProperty("state").GetString() == "AUTHORIZED_UNCONSUMED", "MODEL009_GRANT_STATE_REJECTED");
    Require(grant.GetProperty("manifest_sha256").GetString() == FrozenModelSentinel009Protocol.ManifestSha256, "MODEL009_GRANT_MANIFEST_HASH_MISMATCH");
    Require(grant.GetProperty("fixture_report_sha256").GetString() == FrozenModelSentinel009Protocol.FixtureReportSha256, "MODEL009_GRANT_FIXTURE_HASH_MISMATCH");
    var nonce = grant.GetProperty("one_use_nonce").GetString() ?? "";
    Require(nonce.Length == 64 && nonce.All(Uri.IsHexDigit), "MODEL009_GRANT_NONCE_REJECTED");

    using var handoverDoc = JsonDocument.Parse(File.ReadAllText(handoverPath));
    var handover = handoverDoc.RootElement;
    Require(handover.GetProperty("experiment_id").GetString() == FrozenModelSentinel009Protocol.ExperimentId, "MODEL009_HANDOVER_ID_MISMATCH");
    Require(handover.GetProperty("one_use_nonce").GetString() == nonce, "MODEL009_HANDOVER_NONCE_MISMATCH");
    Require(handover.GetProperty("manifest_sha256").GetString() == FrozenModelSentinel009Protocol.ManifestSha256, "MODEL009_HANDOVER_MANIFEST_HASH_MISMATCH");
    Require(handover.GetProperty("runtime018_service_inactive").GetBoolean(), "MODEL009_RUNTIME018_NOT_INACTIVE");

    using var executionDoc = JsonDocument.Parse(File.ReadAllText(executionPath));
    var execution = executionDoc.RootElement;
    Require(execution.GetProperty("experiment_id").GetString() == FrozenModelSentinel009Protocol.ExperimentId, "MODEL009_EXECUTION_ID_MISMATCH");
    Require(execution.GetProperty("one_use_nonce").GetString() == nonce, "MODEL009_EXECUTION_NONCE_MISMATCH");
    Require(execution.GetProperty("manifest_sha256").GetString() == FrozenModelSentinel009Protocol.ManifestSha256, "MODEL009_EXECUTION_MANIFEST_HASH_MISMATCH");
    Require(execution.GetProperty("fixture_report_sha256").GetString() == FrozenModelSentinel009Protocol.FixtureReportSha256, "MODEL009_EXECUTION_FIXTURE_HASH_MISMATCH");

    var assemblyPath = Assembly.GetExecutingAssembly().Location;
    assemblySha = Sha256File(assemblyPath);
    Require(execution.GetProperty("assembly_sha256").GetString() == assemblySha, "MODEL009_EXECUTION_ASSEMBLY_HASH_MISMATCH");
    foreach (var item in execution.GetProperty("source_files").EnumerateArray())
    {
        var relative = item.GetProperty("path").GetString() ?? throw new InvalidOperationException("MODEL009_EXECUTION_SOURCE_PATH_MISSING");
        var expected = item.GetProperty("sha256").GetString() ?? throw new InvalidOperationException("MODEL009_EXECUTION_SOURCE_HASH_MISSING");
        var full = Path.Combine(repoRoot, relative.Replace('/', Path.DirectorySeparatorChar));
        Require(File.Exists(full), $"MODEL009_EXECUTION_SOURCE_MISSING {relative}");
        Require(Sha256File(full) == expected, $"MODEL009_EXECUTION_SOURCE_HASH_MISMATCH {relative}");
    }

    Directory.CreateDirectory(localDir);
    WriteCreateNewJson(claimPath, new
    {
        schema_version = 1,
        experiment_id = FrozenModelSentinel009Protocol.ExperimentId,
        manifest_sha256 = FrozenModelSentinel009Protocol.ManifestSha256,
        fixture_report_sha256 = FrozenModelSentinel009Protocol.FixtureReportSha256,
        execution_assembly_sha256 = assemblySha,
        one_use_nonce = nonce,
        claimed_at_utc = DateTimeOffset.UtcNow,
        state = "CONSUMED_BEFORE_BLUETOOTH_OPEN_NO_RETRY"
    });
    claimed = true;

    var result = WindowsRfcommModelSentinel009Transport.RunExactlyOnce(fixtures);
    WriteCreateNewJson(resultPath, new
    {
        schema_version = 1,
        experiment_id = FrozenModelSentinel009Protocol.ExperimentId,
        outcome = "model_sentinel_differential_transcript_complete",
        connections_attempted = result.ConnectionsAttempted,
        application_sends_completed = result.SendsCompleted,
        custom_0x6c_sends = result.CustomOverwriteSends,
        retry = false,
        reconnect = false,
        overwrite_elapsed_ms_from_a5 = result.OverwriteElapsedMs,
        observation_ms = result.ObservationMilliseconds,
        connection_survived_observation = result.ConnectionSurvivedObservation,
        reports = result.Reports,
        report_count = result.Reports.Count,
        execution_assembly_sha256 = assemblySha,
        completed_at_utc = DateTimeOffset.UtcNow,
        interpretation = "MODEL-SENTINEL differential transcript only: one 0x411-byte data-only 0x6c copy reaches exactly the predicted runtime50 model byte +0x08 under later-branch geometry and remains far short of callback +0x34. Compare with PREMODEL-008/CONTROL-007 before any exact-v42012 placement claim."
    });
    Console.WriteLine("MODEL009_TRANSCRIPT=COMPLETE");
    Console.WriteLine($"MODEL009_OVERWRITE_ELAPSED_MS={result.OverwriteElapsedMs}");
    Console.WriteLine($"MODEL009_REPORT_COUNT={result.Reports.Count}");
    Console.WriteLine($"MODEL009_OBSERVATION_MS={result.ObservationMilliseconds}");
    Console.WriteLine("MODEL009_APPLICATION_SENDS=3");
    Console.WriteLine("MODEL009_CUSTOM_0X6C_SENDS=1");
    Console.WriteLine("MODEL009_RETRY=false");
    return 0;
}
catch (WindowsRfcommModelSentinel009Transport.TransportStopException ex)
{
    if (claimed && !File.Exists(resultPath))
    {
        try
        {
            WriteCreateNewJson(resultPath, new
            {
                schema_version = 1,
                experiment_id = FrozenModelSentinel009Protocol.ExperimentId,
                outcome = "stopped_no_retry",
                error = ex.Message,
                connections_attempted = ex.ConnectionsAttempted,
                application_sends_completed = ex.SendsCompleted,
                custom_0x6c_sends = ex.CustomOverwriteSends,
                retry = false,
                reconnect = false,
                reports = ex.Reports,
                report_count = ex.Reports.Count,
                execution_assembly_sha256 = assemblySha,
                completed_at_utc = DateTimeOffset.UtcNow
            });
        }
        catch { }
    }
    Console.Error.WriteLine($"MODEL009_STOP_NO_RETRY: {ex.Message}");
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
                experiment_id = FrozenModelSentinel009Protocol.ExperimentId,
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
    Console.Error.WriteLine($"MODEL009_STOP_NO_RETRY: {ex.Message}");
    return 31;
}
