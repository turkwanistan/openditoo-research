using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using OpenDitoo.Webcam.Runner;

namespace OpenDitoo.Webcam.Studio;

/// <summary>
/// The W10 live envelope, re-checked on the Windows side before the camera and again after the
/// claim. It mirrors host/webcam_studio.py: exact named grant, exact target, streaming profile
/// with the 40 ms Host floor, a reviewed slot interval, budgets derived from lifetime and
/// interval under the Host's 500-frame cap, and every producer file plus this very binary
/// hash-frozen. Framing is operator-adjustable by design; it changes pixels, never the envelope.
/// </summary>
internal static class StudioTrial
{
    internal static Trial Load(string root, string path)
    {
        var doc = JsonNode.Parse(File.ReadAllText(path))!;
        var id = doc["experiment_id"]!.GetValue<string>();
        Trial.Require(Regex.IsMatch(id, "^OPENDITOO-WEBCAM-W10-[0-9]{3}$"), "EXPERIMENT_ID_INVALID");
        var authority = doc["authority"]!;
        Trial.Require(authority["experiment_id"]!.GetValue<string>() == id &&
            authority["transmission_authorized"]!.GetValue<bool>() &&
            !authority["authorization_consumed"]!.GetValue<bool>() &&
            authority["grant_text"]?.GetValue<string>() == "Grant " + id &&
            !string.IsNullOrWhiteSpace(authority["granted_by"]?.GetValue<string>()) &&
            DateTimeOffset.TryParse(authority["expires_at"]?.GetValue<string>(), out var expiry) &&
            expiry > DateTimeOffset.UtcNow, "NAMED_GRANT_REQUIRED");
        Trial.Require(doc["readiness"]!["grant_ready"]!.GetValue<bool>() &&
            doc["readiness"]!["blockers"]!.AsArray().Count == 0, "TRIAL_NOT_READY");
        Trial.Require(doc["target"]!["exact_unit_id"]!.GetValue<string>() == Trial.Target &&
            doc["target"]!["installed_firmware"]!.GetValue<string>() == "v42012" &&
            doc["kind"]!.GetValue<string>() == "frame_stream", "TARGET_OR_KIND_MISMATCH");
        var stream = doc["stream"]!;
        var session = doc["session"]!;
        var budgets = doc["budgets"]!;
        var interval = stream["playback_interval_ms"]!.GetValue<int>();
        Trial.Require(StudioModes.IntervalMs.Values.Contains(interval), "CLIENT_INTERVAL_NOT_REVIEWED");
        var lifetime = session["lifetime_seconds"]!.GetValue<int>();
        Trial.Require(lifetime is > 0 and <= 900, "LIFETIME_INVALID");
        var frames = Math.Min(lifetime * 1000 / interval + 1, 500);
        Trial.Require(stream["source_kind"]!.GetValue<string>() == "live" &&
            stream["session_profile"]!.GetValue<string>() == Trial.Profile &&
            session["min_frame_interval_ms"]!.GetValue<int>() == Trial.HostFloor &&
            budgets["max_frames"]!.GetValue<int>() == frames &&
            budgets["max_application_packets"]!.GetValue<int>() == frames * 3 &&
            budgets["max_tx_bytes"]!.GetValue<int>() == frames * Trial.WorstCaseFrameTxBytes &&
            budgets["connection_attempts"]!.GetValue<int>() == 1 &&
            budgets["ack_timeout_ms_per_frame"]!.GetValue<int>() == Trial.AckTimeoutMs, "TRIAL_ENVELOPE_MISMATCH");
        foreach (var flag in new[] { "automatic_retry", "automatic_reconnect", "stock_screen_reclaim", "replay_after_interruption" })
            Trial.Require(!session[flag]!.GetValue<bool>(), "RETRY_OR_RECLAIM_FORBIDDEN");
        var camera = stream["live_source"]!["camera"]!;
        Trial.Require(camera["usb_vid"]!.GetValue<string>() == "0C45" && camera["usb_pid"]!.GetValue<string>() == "2690" &&
            camera["subtype"]!.GetValue<string>() == "NV12" && camera["width"]!.GetValue<int>() == 640 &&
            camera["height"]!.GetValue<int>() == 480 && camera["requested_fps"]!.GetValue<int>() == 60 &&
            camera["acquisition_mode"]!.GetValue<string>() == "Realtime", "CAMERA_ENVELOPE_MISMATCH");
        Trial.Require(stream["live_source"]!["transform"]!["preset"]!.GetValue<string>() == "srgb_area",
            "TRANSFORM_ENVELOPE_MISMATCH");
        VerifyBuild(root, stream["live_source"]!["producer_code_sha256"]!.AsObject(), doc["build"]!["host_dll_sha256"]!.GetValue<string>());
        return new(id, lifetime, frames, frames * Trial.WorstCaseFrameTxBytes, interval);
    }

    /// <summary>Every producer file, this very binary, and the repository + installed Host DLL.</summary>
    private static void VerifyBuild(string root, JsonObject files, string expectedHost)
    {
        var ownDllVerified = false;
        foreach (var (relative, expected) in files)
        {
            Trial.Require(relative != "" && !Path.IsPathRooted(relative) && !relative.Split('/').Contains(".."), "HASH_PATH_INVALID");
            Trial.Require(Trial.Hash(Path.Combine(root, relative)) == expected!.GetValue<string>(), "PRODUCER_HASH_DRIFT");
            if (relative.Contains("OpenDitoo.Webcam.Studio/bin/"))
            {
                var name = Path.GetFileName(relative);
                Trial.Require(Trial.Hash(Path.Combine(AppContext.BaseDirectory, name)) == expected.GetValue<string>(), "DEPLOYED_STUDIO_HASH_DRIFT");
                ownDllVerified |= name == "OpenDitoo.Webcam.Studio.dll";
            }
        }
        Trial.Require(ownDllVerified, "STUDIO_BUILD_NOT_FROZEN");
        Trial.Require(Trial.Hash(Path.Combine(root, "runtime/windows/OpenDitoo.Day1.Host/bin/Release/net8.0/OpenDitoo.Day1.Host.dll")) == expectedHost &&
            Trial.Hash(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "OpenDitoo/Day1Host/OpenDitoo.Day1.Host.dll")) == expectedHost, "HOST_HASH_DRIFT");
    }

    internal const string PolicyId = "OPENDITOO-WEBCAM-PRODUCT-005";
    // One 30-minute connection per launch (Runtime 004 Host streaming ceiling): lifetime / 50 ms slots + 1.
    internal const int PolicySeconds = 1800;
    internal const int PolicyFrames = PolicySeconds * 1000 / 50 + 1;
    internal static readonly Regex SessionId = new("^OPENDITOO-WEBCAM-LIVE-[0-9a-f]{8}-[0-9]{3}$");

    /// <summary>
    /// W10C standing webcam policy (local, mode 0600, materialized only after the owner's exact
    /// grant). Returns the per-session envelope; each session still gets its own fresh id and
    /// durable one-use claim from the WSL coordinator.
    /// </summary>
    internal static (int Seconds, int MaxFrames, int MaxBytes, int IntervalMs) LoadPolicy(string root, string path)
    {
        var doc = JsonNode.Parse(File.ReadAllText(path))!;
        var authority = doc["authority"]!;
        Trial.Require(doc["policy_id"]!.GetValue<string>() == PolicyId &&
            authority["webcam_product_authorized"]!.GetValue<bool>() &&
            !authority["revoked"]!.GetValue<bool>() &&
            authority["grant_text"]?.GetValue<string>() == "Grant " + PolicyId &&
            !string.IsNullOrWhiteSpace(authority["granted_by"]?.GetValue<string>()), "WEBCAM_PRODUCT_GRANT_REQUIRED");
        Trial.Require(doc["target"]!["exact_unit_id"]!.GetValue<string>() == Trial.Target &&
            doc["target"]!["installed_firmware"]!.GetValue<string>() == "v42012", "TARGET_MISMATCH");
        var e = doc["envelope"]!;
        int Get(string key) => e[key]!.GetValue<int>();
        Trial.Require(e["session_profile"]!.GetValue<string>() == Trial.Profile && Get("host_floor_ms") == Trial.HostFloor &&
            Get("slot_interval_ms") == StudioModes.IntervalMs["max"] && Get("session_lifetime_seconds") == PolicySeconds &&
            Get("max_frames") == PolicyFrames && Get("max_application_packets") == PolicyFrames * 3 &&
            Get("max_tx_bytes") == PolicyFrames * Trial.WorstCaseFrameTxBytes && Get("ack_timeout_ms_per_frame") == Trial.AckTimeoutMs &&
            Get("max_sessions_per_launch") == 1,
            "WEBCAM_PRODUCT_ENVELOPE_MISMATCH");
        foreach (var flag in new[] { "automatic_retry", "automatic_reconnect", "stock_screen_reclaim" })
            Trial.Require(!doc["behavior"]![flag]!.GetValue<bool>(), "RETRY_OR_RECLAIM_FORBIDDEN");
        VerifyBuild(root, doc["build"]!["producer_code_sha256"]!.AsObject(), doc["build"]!["host_dll_sha256"]!.GetValue<string>());
        return (PolicySeconds, PolicyFrames, PolicyFrames * Trial.WorstCaseFrameTxBytes, StudioModes.IntervalMs["max"]);
    }
}
