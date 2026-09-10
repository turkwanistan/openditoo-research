using System.Security.Cryptography;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace OpenDitoo.Webcam.Runner;

internal sealed record Trial(string Id, int Seconds, int MaxFrames, int MaxBytes, int ClientIntervalMs = 90)
{
    internal const string Target = "11:75:58:CE:DE:C7";
    internal const string Profile = "streaming_ack_clock";
    internal const int HostFloor = 40;
    internal const int W7ClientInterval = 90;
    internal const int W8ClientInterval = 40;
    internal const int WorstCaseFrameTxBytes = 1054;
    internal static string Hash(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
    internal static void Require(bool condition, string reason)
    { if (!condition) throw new InvalidOperationException(reason); }

    internal static Trial Load(string root, string path)
    {
        var doc = JsonNode.Parse(File.ReadAllText(path))!;
        var id = doc["experiment_id"]!.GetValue<string>();
        Require(Regex.IsMatch(id, "^OPENDITOO-WEBCAM-N980P-[0-9]{3}$"), "EXPERIMENT_ID_INVALID");
        var authority = doc["authority"]!;
        Require(authority["experiment_id"]!.GetValue<string>() == id &&
            authority["transmission_authorized"]!.GetValue<bool>() &&
            !authority["authorization_consumed"]!.GetValue<bool>() &&
            authority["grant_text"]?.GetValue<string>() == "Grant " + id &&
            !string.IsNullOrWhiteSpace(authority["granted_by"]?.GetValue<string>()) &&
            DateTimeOffset.TryParse(authority["expires_at"]?.GetValue<string>(), out var expiry) &&
            expiry > DateTimeOffset.UtcNow, "NAMED_GRANT_REQUIRED");
        Require(doc["readiness"]!["grant_ready"]!.GetValue<bool>() &&
            doc["readiness"]!["blockers"]!.AsArray().Count == 0, "TRIAL_NOT_READY");
        Require(doc["target"]!["exact_unit_id"]!.GetValue<string>() == Target &&
            doc["target"]!["installed_firmware"]!.GetValue<string>() == "v42012" &&
            doc["kind"]!.GetValue<string>() == "frame_stream", "TARGET_OR_KIND_MISMATCH");
        var stream = doc["stream"]!;
        var settings = doc["session"]!;
        var budgets = doc["budgets"]!;
        var clientInterval = stream["playback_interval_ms"]!.GetValue<int>();
        Require(clientInterval == W7ClientInterval || clientInterval == W8ClientInterval,
            "CLIENT_INTERVAL_NOT_REVIEWED");
        var expectedFrames = Math.Min(10_000 / clientInterval + 1, 500);
        var expectedPackets = expectedFrames * 3;
        var expectedBytes = expectedFrames * WorstCaseFrameTxBytes;
        Require(stream["source_kind"]!.GetValue<string>() == "live" &&
            stream["session_profile"]!.GetValue<string>() == Profile &&
            stream["loop"]!.GetValue<bool>() == false &&
            settings["min_frame_interval_ms"]!.GetValue<int>() == HostFloor &&
            settings["lifetime_seconds"]!.GetValue<int>() == 10 &&
            budgets["max_frames"]!.GetValue<int>() == expectedFrames &&
            budgets["max_tx_bytes"]!.GetValue<int>() == expectedBytes &&
            budgets["max_application_packets"]!.GetValue<int>() == expectedPackets &&
            budgets["connection_attempts"]!.GetValue<int>() == 1 &&
            budgets["ack_timeout_ms_per_frame"]!.GetValue<int>() == 5000, "TRIAL_ENVELOPE_MISMATCH");
        foreach (var flag in new[] { "automatic_retry", "automatic_reconnect", "stock_screen_reclaim", "replay_after_interruption" })
            Require(!settings[flag]!.GetValue<bool>(), "RETRY_OR_RECLAIM_FORBIDDEN");
        var producer = stream["live_source"]!;
        var camera = producer["camera"]!;
        var transform = producer["transform"]!;
        Require(camera["usb_vid"]!.GetValue<string>() == "0C45" && camera["usb_pid"]!.GetValue<string>() == "2690" &&
            camera["subtype"]!.GetValue<string>() == "NV12" && camera["width"]!.GetValue<int>() == 640 &&
            camera["height"]!.GetValue<int>() == 480 && camera["requested_fps"]!.GetValue<int>() == 60 &&
            camera["acquisition_mode"]!.GetValue<string>() == "Realtime", "CAMERA_ENVELOPE_MISMATCH");
        Require(transform["preset"]!.GetValue<string>() == "srgb_area" &&
            !transform["linear_light"]!.GetValue<bool>() && transform["zoom"]!.GetValue<double>() == 1 &&
            transform["offset_x"]!.GetValue<double>() == 0 && transform["offset_y"]!.GetValue<double>() == 0 &&
            transform["mirror"]!.GetValue<bool>() && transform["quarter_turns"]!.GetValue<int>() == 0,
            "TRANSFORM_ENVELOPE_MISMATCH");
        var files = producer["producer_code_sha256"]!.AsObject();
        Require(files.Count > 0, "PRODUCER_HASHES_MISSING");
        var ownDllVerified = false;
        foreach (var (relative, expected) in files)
        {
            Require(relative != "" && !Path.IsPathRooted(relative) && !relative.Split('/').Contains(".."), "HASH_PATH_INVALID");
            Require(Hash(Path.Combine(root, relative)) == expected!.GetValue<string>(), "PRODUCER_HASH_DRIFT");
            if (relative.Contains("OpenDitoo.Webcam.Runner/bin/"))
            {
                var name = Path.GetFileName(relative);
                Require(Hash(Path.Combine(AppContext.BaseDirectory, name)) == expected.GetValue<string>(), "DEPLOYED_ADAPTER_HASH_DRIFT");
                ownDllVerified |= name == "OpenDitoo.Webcam.Runner.dll";
            }
        }
        Require(ownDllVerified, "ADAPTER_BUILD_NOT_FROZEN");
        var expectedHost = doc["build"]!["host_dll_sha256"]!.GetValue<string>();
        Require(Hash(Path.Combine(root, "runtime/windows/OpenDitoo.Day1.Host/bin/Release/net8.0/OpenDitoo.Day1.Host.dll")) == expectedHost &&
            Hash(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "OpenDitoo/Day1Host/OpenDitoo.Day1.Host.dll")) == expectedHost, "HOST_HASH_DRIFT");
        return new(id, 10, expectedFrames, expectedBytes, clientInterval);
    }
}
