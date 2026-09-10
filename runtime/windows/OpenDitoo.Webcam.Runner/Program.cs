using System.Text.Json;
using System.Text.Json.Nodes;
using OpenDitoo.Webcam.Probe;
using OpenDitoo.Webcam.Runner;

static void Emit(object data) { Console.WriteLine(JsonSerializer.Serialize(data)); Console.Out.Flush(); }

if (args.Length == 1 && args[0] == "selftest") return await OfflineTests.Run();
if (args.Length == 2 && args[0] == "transform-selftest") return FrameTransform.SelfTest(args[1]);
if (args.Length == 2 && args[0] == "encoder-selftest") return DitooEncoder.SelfTest(args[1]);

try
{
    if (args.Length == 2 && args[0] == "host-status-selftest")
    {
        var statusRoot = Path.GetFullPath(args[1]);
        var statusToken = File.ReadAllText(Path.Combine(statusRoot, ".openditoo-local/host.token")).Trim();
        Trial.Require(statusToken.Length >= 32, "HOST_TOKEN_INVALID");
        using var session = TypedSession.Live(statusToken);
        var status = await session.GetStatus();
        Trial.Require(status["service"]?.GetValue<string>() == "OpenDitoo Day1 Host" &&
            status["hostRuntime"]?.GetValue<string>() == ".NET" &&
            status["bind"]?.GetValue<string>() == "127.0.0.1" &&
            status["port"]?.GetValue<int>() == 8796 &&
            status["target"]?.GetValue<string>() == Trial.Target &&
            status["rawSendEnabled"]?.GetValue<bool>() == false, "HOST_STATUS_IDENTITY_MISMATCH");
        Emit(new { kind = "host_status_selftest_pass", target = Trial.Target,
            status_has_ok_field = status.ContainsKey("ok"), device_io = false, host_session_io = false });
        return 0;
    }
    if (args.Length == 1 && args[0] == "soak")
    {
        await using var camera = await WebcamFrames.Open();
        var memory = new List<long>(); // exactly six samples, no frame history
        var started = WebcamFrames.NowMs;
        for (var minute = 0; minute < 5; minute++)
        {
            memory.Add(GC.GetTotalMemory(true));
            // Same typed sender/serialization/ACK path, using an in-memory handler only.
            var trial = new Trial("OFFLINE-SOAK", 60, 1000, 1054000);
            using var transport = new TypedSession(new HttpClient(new OfflineTests.FakeHandler()));
            var result = JsonSerializer.SerializeToNode(await Sender.Run(trial, camera, transport, CancellationToken.None))!;
            Trial.Require(result["outcome"]!.GetValue<string>() == "stopped_clean" &&
                result["frames"]!.GetValue<int>() >= 300, "SOAK_SENDER_FAILED");
            Emit(new { kind = "soak_checkpoint", minute = minute + 1, managedBytes = memory[^1] });
        }
        memory.Add(GC.GetTotalMemory(true));
        var growth = memory[^1] - memory[1]; // discard first-minute JIT/startup effects
        Trial.Require(growth < 8 * 1024 * 1024 && camera.Fault is null, "SOAK_MEMORY_OR_CAMERA_FAILED");
        Emit(new { kind = "soak_pass", seconds = (WebcamFrames.NowMs - started) / 1000,
            memoryBytes = memory, growthAfterWarmupBytes = growth, captured = camera.Captured,
            replaced = camera.Replaced, transformMs = camera.TransformMs.Snapshot(), device_io = false });
        return 0;
    }
    if (args.Length != 3 || args[0] != "live") throw new ArgumentException("live <manifest> <repository> | selftest | soak");
    var path = Path.GetFullPath(args[1]);
    var root = Path.GetFullPath(args[2]);
    var trialLive = Trial.Load(root, path); // named grant, envelope and all hashes before camera/Host
    var manifestHash = Trial.Hash(path);
    await using var frames = await WebcamFrames.Open();
    using var stop = new CancellationTokenSource();
    Console.CancelKeyPress += (_, e) => { e.Cancel = true; stop.Cancel(); };
    TimedFrame first;
    using (var startup = new CancellationTokenSource(TimeSpan.FromSeconds(5)))
    {
        while (!frames.TryTake(out first))
        {
            if (frames.Fault is { } fault) throw new IOException(fault);
            startup.Token.ThrowIfCancellationRequested();
            frames.Wait(startup.Token);
        }
    }
    Trial.Require(WebcamFrames.NowMs - first.CapturedQpcMs < 500, "CAMERA_STALE_BEFORE_CLAIM");
    _ = DitooEncoder.EncodeRgb888(first.Pixels);
    var nonce = Guid.NewGuid().ToString("N");
    Emit(new { kind = "camera_ready", experiment_id = trialLive.Id, manifest_sha256 = manifestHash, nonce });
    // EOF, silence, cancellation or any different message cannot cross the claim boundary.
    var command = await Console.In.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(15));
    Trial.Require(command == "execute:" + nonce, "CLAIM_HANDSHAKE_MISSING");
    var claim = JsonNode.Parse(File.ReadAllText(Path.Combine(root, ".openditoo-local/session-claims", trialLive.Id + ".json")))!;
    Trial.Require(claim["experiment_id"]!.GetValue<string>() == trialLive.Id &&
        claim["state"]!.GetValue<string>() == "claimed" && claim["nonce"]!.GetValue<string>() == nonce &&
        claim["manifest_sha256"]!.GetValue<string>() == manifestHash && Trial.Hash(path) == manifestHash,
        "DURABLE_CLAIM_MISMATCH");
    _ = Trial.Load(root, path); // recheck expiry, hashes and installed identity after readiness
    Trial.Require(frames.Fault is null, "CAMERA_FAILED_BEFORE_OPEN");
    var token = File.ReadAllText(Path.Combine(root, ".openditoo-local/host.token")).Trim();
    Trial.Require(token.Length >= 32, "HOST_TOKEN_INVALID");
    using var live = TypedSession.Live(token);
    var finished = await Sender.Run(trialLive, frames, live, stop.Token);
    Emit(new { kind = "result", experiment_id = trialLive.Id, result = finished,
        captured = frames.Captured, replaced = frames.Replaced, transformMs = frames.TransformMs.Snapshot() });
    return JsonSerializer.SerializeToNode(finished)!["outcome"]!.GetValue<string>() == "stopped_clean" ? 0 : 2;
}
catch (Exception ex)
{
    Emit(new { kind = "error", error = ex.Message, outcome = "unknown" });
    return 2;
}
