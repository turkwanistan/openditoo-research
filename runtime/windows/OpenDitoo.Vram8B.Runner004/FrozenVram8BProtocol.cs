using System.Security.Cryptography;
using System.Text.Json;

internal static class FrozenVram8BProtocol
{
    internal const string ExperimentId = "OPENDITOO-VRAM8B-CANARY-004";
    internal const string RequiredGrantText = "Grant OPENDITOO-VRAM8B-CANARY-004 -- stock btplayer selected";
    internal const string TargetMac = "11:75:58:CE:DE:C7";
    internal const ulong TargetBluetoothAddress = 0x117558CEDEC7;
    internal const uint TargetRfcommChannel = 1;
    internal const int ExpectedInstalledVersion = 42012;

    internal const string ManifestSha256 = "0906626243dd1859ce52cef62261ddee0bd14df72043c966d3a06b8665a26c24";
    internal const string FixtureReportSha256 = "b85b0f104d6ed8b1d2781080bb8fa3acbe1a7c89c06d90a1bfd842e1564b9e2e";
    internal const int ConnectBudgetMs = 15_000;
    internal const int ResponseBudgetMs = 2_000;
    internal const int ObservationHoldMs = 75_000;
    internal const int TotalBudgetMs = 100_000;
    internal const int InterPacketDelayMs = 40;
    internal const int ExactApplicationSends = 8;
    internal const int MaxCustomOverwriteSends = 1;
    internal const int ExpectedB3WireBytes = 10;

    internal sealed record Fixture(string Key, string RelativePath, string Sha256, int WireLength, bool IsB3Query, int? ExpectedB3Value, bool IsCustomOverwrite);

    internal static readonly Fixture[] Fixtures =
    [
        new("baseline_set", "experiments/fixtures/OPENDITOO-VRAM8B-CANARY-004-01-baseline-set.bin", "3f98ef3e2af07ccd2151bd06ae96ad8bdfc82d8fb1ed94c0f66d3580ae75ca47", 8, false, null, false),
        new("baseline_get", "experiments/fixtures/OPENDITOO-VRAM8B-CANARY-004-02-baseline-get.bin", "6fe20a0815b73bb62acf228634f664379efae9983842eeca6ac7974c2f2bea7c", 7, true, 0, false),
        new("prime", "experiments/fixtures/OPENDITOO-VRAM8B-CANARY-004-03-prime.bin", "9f643ace4ce755ddcd04446c0cb21bbaa23b53f123788a225d1c9eda81e213ec", 8, false, null, false),
        new("voicetip", "experiments/fixtures/OPENDITOO-VRAM8B-CANARY-004-04-voicetip.bin", "4cf9f3d0458664a2c99681e6a672b8eaefea3a043d83a2f15a751aabcd9d0316", 10, false, null, false),
        new("overwrite", "experiments/fixtures/OPENDITOO-VRAM8B-CANARY-004-05-overwrite.bin", "298f1901ea9cc94fd172302117cd2e5cf411eacb578b16be5de3ecf1c52e0906", 1099, false, null, true),
        new("post_get", "experiments/fixtures/OPENDITOO-VRAM8B-CANARY-004-06-post-get.bin", "6fe20a0815b73bb62acf228634f664379efae9983842eeca6ac7974c2f2bea7c", 7, true, 1, false),
        new("restore_set", "experiments/fixtures/OPENDITOO-VRAM8B-CANARY-004-07-restore-set.bin", "3f98ef3e2af07ccd2151bd06ae96ad8bdfc82d8fb1ed94c0f66d3580ae75ca47", 8, false, null, false),
        new("restore_get", "experiments/fixtures/OPENDITOO-VRAM8B-CANARY-004-08-restore-get.bin", "6fe20a0815b73bb62acf228634f664379efae9983842eeca6ac7974c2f2bea7c", 7, true, 0, false),
    ];

    internal static string Sha256File(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    internal static byte[][] LoadAndVerifyFixtures(string repoRoot)
    {
        if (Fixtures.Length != ExactApplicationSends)
            throw new InvalidOperationException("VRAM8B_FIXTURE_COUNT_DRIFT");
        var data = new byte[Fixtures.Length][];
        var custom = 0;
        for (var i = 0; i < Fixtures.Length; i++)
        {
            var f = Fixtures[i];
            var full = Path.Combine(repoRoot, f.RelativePath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(full)) throw new InvalidOperationException($"VRAM8B_FIXTURE_MISSING {f.RelativePath}");
            var bytes = File.ReadAllBytes(full);
            if (bytes.Length != f.WireLength) throw new InvalidOperationException($"VRAM8B_FIXTURE_LENGTH_DRIFT {f.Key}");
            var actual = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
            if (!StringComparer.Ordinal.Equals(actual, f.Sha256)) throw new InvalidOperationException($"VRAM8B_FIXTURE_HASH_DRIFT {f.Key}");
            data[i] = bytes;
            if (f.IsCustomOverwrite) custom++;
        }
        if (custom != MaxCustomOverwriteSends) throw new InvalidOperationException("VRAM8B_CUSTOM_OVERWRITE_COUNT_DRIFT");
        return data;
    }

    internal static void VerifyCommittedManifest(string repoRoot)
    {
        var manifestPath = Path.Combine(repoRoot, "experiments", "OPENDITOO-VRAM8B-CANARY-004.json");
        var fixtureReportPath = Path.Combine(repoRoot, "artifacts", "analysis", "volatile_ram_api_vram8b_fixture_004.json");
        if (Sha256File(manifestPath) != ManifestSha256) throw new InvalidOperationException("VRAM8B_MANIFEST_HASH_DRIFT");
        if (Sha256File(fixtureReportPath) != FixtureReportSha256) throw new InvalidOperationException("VRAM8B_FIXTURE_REPORT_HASH_DRIFT");
        using var doc = JsonDocument.Parse(File.ReadAllText(manifestPath));
        var m = doc.RootElement;
        if (m.GetProperty("experiment_id").GetString() != ExperimentId) throw new InvalidOperationException("VRAM8B_MANIFEST_ID_DRIFT");
        if (m.GetProperty("status").GetString() != "prepared_unauthorized") throw new InvalidOperationException("VRAM8B_MANIFEST_STATUS_DRIFT");
        var authority = m.GetProperty("authority");
        if (authority.GetProperty("required_grant_text").GetString() != RequiredGrantText) throw new InvalidOperationException("VRAM8B_GRANT_TEXT_DRIFT");
        if (authority.GetProperty("transmission_authorized").GetBoolean()) throw new InvalidOperationException("VRAM8B_COMMITTED_MANIFEST_MUST_REMAIN_UNAUTHORIZED");
        if (!authority.GetProperty("one_use").GetBoolean() || authority.GetProperty("retry").GetBoolean()) throw new InvalidOperationException("VRAM8B_AUTHORITY_BUDGET_DRIFT");
        var target = m.GetProperty("target");
        if (target.GetProperty("mac").GetString() != TargetMac || target.GetProperty("rfcomm_channel").GetInt32() != TargetRfcommChannel || target.GetProperty("installed_firmware_version_assumption").GetInt32() != ExpectedInstalledVersion)
            throw new InvalidOperationException("VRAM8B_TARGET_DRIFT");
        var budget = m.GetProperty("transport_budget");
        if (budget.GetProperty("max_connections").GetInt32() != 1 || budget.GetProperty("exact_application_sends").GetInt32() != ExactApplicationSends || budget.GetProperty("max_custom_0x6c_sends").GetInt32() != MaxCustomOverwriteSends || budget.GetProperty("retry").GetBoolean() || budget.GetProperty("reconnect").GetBoolean())
            throw new InvalidOperationException("VRAM8B_TRANSPORT_BUDGET_DRIFT");
    }

    internal static byte[] ValidateWrappedResponse(ReadOnlySpan<byte> wire, byte expectedInnerCommand, byte? exactSinglePayload)
    {
        if (wire.Length < 9 || wire.Length > 64) throw new InvalidOperationException($"VRAM8B_RESPONSE_LENGTH_REJECTED COUNT={wire.Length}");
        if (wire[0] != 0x01 || wire[^1] != 0x02) throw new InvalidOperationException("VRAM8B_RESPONSE_BOUNDARY_REJECTED");
        var innerLength = wire[1] | (wire[2] << 8);
        if (wire.Length != innerLength + 4 || innerLength < 5) throw new InvalidOperationException($"VRAM8B_RESPONSE_INNER_LENGTH_REJECTED VALUE={innerLength}");
        var checksumIndex = 3 + innerLength - 2;
        ushort sum = 0;
        for (var i = 1; i < checksumIndex; i++) sum = unchecked((ushort)(sum + wire[i]));
        var observedChecksum = (ushort)(wire[checksumIndex] | (wire[checksumIndex + 1] << 8));
        if (sum != observedChecksum) throw new InvalidOperationException($"VRAM8B_RESPONSE_CHECKSUM_REJECTED OBSERVED=0x{observedChecksum:X4} EXPECTED=0x{sum:X4}");
        if (wire[3] != 0x04 || wire[4] != expectedInnerCommand || wire[5] != 0x55)
            throw new InvalidOperationException($"VRAM8B_RESPONSE_WRAPPER_REJECTED OUTER=0x{wire[3]:X2} INNER=0x{wire[4]:X2} TAG=0x{wire[5]:X2} EXPECTED_INNER=0x{expectedInnerCommand:X2}");
        var payloadLength = checksumIndex - 6;
        var payload = wire.Slice(6, payloadLength).ToArray();
        if (exactSinglePayload is byte expected)
        {
            if (payload.Length != 1 || payload[0] != expected)
                throw new InvalidOperationException($"VRAM8B_RESPONSE_PAYLOAD_REJECTED INNER=0x{expectedInnerCommand:X2} LENGTH={payload.Length} VALUE={(payload.Length == 1 ? payload[0] : -1)} EXPECTED={expected}");
        }
        return payload;
    }

}
