using System.Security.Cryptography;
using System.Text.Json;

internal static class FrozenControl007Protocol
{
    internal const string ExperimentId = "OPENDITOO-VRAM8B-CONTROL-007";
    internal const string RequiredGrantText = "Grant OPENDITOO-VRAM8B-CONTROL-007 -- stock btplayer selected";
    internal const string TargetMac = "11:75:58:CE:DE:C7";
    internal const ulong TargetBluetoothAddress = 0x117558CEDEC7;
    internal const uint TargetRfcommChannel = 1;
    internal const int ExpectedInstalledVersion = 42012;
    internal const string ManifestSha256 = "7660aee525515499c094c2bf5d124349efb9fdf36d46559ba8c88895b7366bae";
    internal const string FixtureReportSha256 = "95ad61a7de060ed6b53a31e74180cca803e48f98b1385f646c2dabbd8805cb34";
    internal const int ConnectBudgetMs = 15_000;
    internal const int InterPacketDelayMs = 40;
    internal const int CaptureWindowMs = 75_000;
    internal const int TotalBudgetMs = 95_000;
    internal const int ExactApplicationSends = 2;
    internal const int MaxReports = 64;
    internal const int MaxWireBytes = 64;
    internal const int MaxBufferedBytes = 4096;

    internal sealed record Fixture(string Key, string RelativePath, string Sha256, int WireLength);
    internal static readonly Fixture[] Fixtures =
    [
        new("prime", "experiments/fixtures/OPENDITOO-VRAM8B-CONTROL-007-01-prime.bin", "9f643ace4ce755ddcd04446c0cb21bbaa23b53f123788a225d1c9eda81e213ec", 8),
        new("voicetip", "experiments/fixtures/OPENDITOO-VRAM8B-CONTROL-007-02-voicetip.bin", "4cf9f3d0458664a2c99681e6a672b8eaefea3a043d83a2f15a751aabcd9d0316", 10),
    ];

    internal static string Sha256File(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    internal static byte[][] LoadAndVerifyFixtures(string repoRoot)
    {
        if (Fixtures.Length != ExactApplicationSends) throw new InvalidOperationException("CONTROL007_FIXTURE_COUNT_DRIFT");
        var data = new byte[Fixtures.Length][];
        for (var i = 0; i < Fixtures.Length; i++)
        {
            var f = Fixtures[i];
            var full = Path.Combine(repoRoot, f.RelativePath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(full)) throw new InvalidOperationException($"CONTROL007_FIXTURE_MISSING {f.RelativePath}");
            var bytes = File.ReadAllBytes(full);
            if (bytes.Length != f.WireLength) throw new InvalidOperationException($"CONTROL007_FIXTURE_LENGTH_DRIFT {f.Key}");
            var actual = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
            if (!StringComparer.Ordinal.Equals(actual, f.Sha256)) throw new InvalidOperationException($"CONTROL007_FIXTURE_HASH_DRIFT {f.Key}");
            data[i] = bytes;
        }
        return data;
    }

    internal static void VerifyCommittedManifest(string repoRoot)
    {
        var manifestPath = Path.Combine(repoRoot, "experiments", ExperimentId + ".json");
        var fixtureReportPath = Path.Combine(repoRoot, "artifacts", "analysis", "volatile_ram_api_vram8b_control_007.json");
        if (Sha256File(manifestPath) != ManifestSha256) throw new InvalidOperationException("CONTROL007_MANIFEST_HASH_DRIFT");
        if (Sha256File(fixtureReportPath) != FixtureReportSha256) throw new InvalidOperationException("CONTROL007_FIXTURE_REPORT_HASH_DRIFT");
        using var doc = JsonDocument.Parse(File.ReadAllText(manifestPath));
        var m = doc.RootElement;
        if (m.GetProperty("experiment_id").GetString() != ExperimentId || m.GetProperty("status").GetString() != "prepared_unauthorized") throw new InvalidOperationException("CONTROL007_MANIFEST_ID_OR_STATUS_DRIFT");
        var authority = m.GetProperty("authority");
        if (authority.GetProperty("required_grant_text").GetString() != RequiredGrantText || authority.GetProperty("transmission_authorized").GetBoolean()) throw new InvalidOperationException("CONTROL007_AUTHORITY_DRIFT");
        var budget = m.GetProperty("transport_budget");
        if (budget.GetProperty("max_connections").GetInt32() != 1 || budget.GetProperty("exact_application_sends").GetInt32() != 2 || budget.GetProperty("max_custom_0x6c_sends").GetInt32() != 0 || budget.GetProperty("retry").GetBoolean() || budget.GetProperty("reconnect").GetBoolean()) throw new InvalidOperationException("CONTROL007_TRANSPORT_BUDGET_DRIFT");
    }
}
