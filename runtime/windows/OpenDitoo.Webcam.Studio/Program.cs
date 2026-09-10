using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Nodes;
using OpenDitoo.Webcam.Probe;
using OpenDitoo.Webcam.Runner;
using OpenDitoo.Webcam.Studio;

// Preview and the selftests never read the Host token and never construct a Host client: they
// cannot reach the Ditoo. Only `live` does, and only under a granted W10 manifest, after the WSL
// coordinator has taken the durable one-use claim against this process's camera-ready nonce.
if (args.Length == 1 && args[0] == "selftest") return await StudioTests.Run();
if (args.Length == 2 && args[0] == "transform-selftest") return FrameTransform.SelfTest(args[1]);
if (args.Length == 2 && args[0] == "encoder-selftest") return DitooEncoder.SelfTest(args[1]);
if (args.Length == 1 && args[0] == "preview")
{
    var (thread, shown) = StartUi(() =>
    {
        var preview = new StudioForm(null, "OpenDitoo Webcam Studio — preview");
        preview.Shown += async (_, _) => await preview.Reconnect();
        return preview;
    });
    var form = await shown;
    thread.Join();
    // Off the UI thread: the camera lives in the MTA.
    if (form.Camera is { } previewCamera) await Task.Run(() => previewCamera.DisposeAsync().AsTask());
    return 0;
}
if (args.Length == 3 && args[0] == "live") return await Live(args[1], args[2]);
if (args.Length == 2 && args[0] == "dryrun" && int.TryParse(args[1], out var drySeconds) && drySeconds is > 0 and <= 900)
    return await DryRun(drySeconds);
Console.Error.WriteLine("usage: preview | dryrun <seconds> | selftest | transform-selftest <cases> | encoder-selftest <cases> | live <manifest> <repository>");
return 2;

static void Emit(object data) { Console.WriteLine(JsonSerializer.Serialize(data)); Console.Out.Flush(); }

static (Thread Thread, Task<StudioForm> Shown) StartUi(Func<StudioForm> create)
{
    var shown = new TaskCompletionSource<StudioForm>(TaskCreationOptions.RunContinuationsAsynchronously);
    var thread = new Thread(() =>
    {
        Application.EnableVisualStyles();
        Application.SetHighDpiMode(HighDpiMode.SystemAware);
        var form = create();
        form.Shown += (_, _) => shown.TrySetResult(form);
        Application.Run(form);
        shown.TrySetException(new InvalidOperationException("UI_CLOSED_BEFORE_SHOWN"));
    });
    thread.SetApartmentState(ApartmentState.STA);
    thread.Start();
    return (thread, shown.Task);
}

static async Task<int> Live(string manifestArgument, string rootArgument)
{
    using var stop = new CancellationTokenSource();
    Console.CancelKeyPress += (_, e) => { e.Cancel = true; stop.Cancel(); };
    StudioCamera? camera = null;
    StudioForm? form = null;
    Thread? ui = null;
    try
    {
        var path = Path.GetFullPath(manifestArgument);
        var root = Path.GetFullPath(rootArgument);
        var trial = StudioTrial.Load(root, path); // named grant, envelope and hashes before the camera
        var manifestHash = Trial.Hash(path);
        var framingAtStart = Framing.Load();
        camera = await StudioCamera.Open(framingAtStart.ToPreset()); // this thread is MTA
        using (var startup = new CancellationTokenSource(TimeSpan.FromSeconds(5)))
            while (camera.LatestMatrix is null)
            {
                if (camera.Fault is { } fault) throw new IOException(fault);
                await Task.Delay(20, startup.Token);
            }
        Trial.Require(WebcamFrames.NowMs - camera.LatestMatrix!.Value.CapturedQpcMs < 500, "CAMERA_STALE_BEFORE_CLAIM");
        var liveCamera = camera;
        (ui, var shown) = StartUi(() => new StudioForm(liveCamera, $"OpenDitoo Webcam Studio — LIVE {trial.Id}", stop));
        form = await shown.WaitAsync(TimeSpan.FromSeconds(10));
        var nonce = Guid.NewGuid().ToString("N");
        Emit(new { kind = "camera_ready", experiment_id = trial.Id, manifest_sha256 = manifestHash, nonce });
        // EOF, silence, cancellation or any different message cannot cross the claim boundary.
        var command = await Console.In.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(15));
        Trial.Require(command == "execute:" + nonce, "CLAIM_HANDSHAKE_MISSING");
        var claim = JsonNode.Parse(File.ReadAllText(Path.Combine(root, ".openditoo-local/session-claims", trial.Id + ".json")))!;
        Trial.Require(claim["experiment_id"]!.GetValue<string>() == trial.Id &&
            claim["state"]!.GetValue<string>() == "claimed" && claim["nonce"]!.GetValue<string>() == nonce &&
            claim["manifest_sha256"]!.GetValue<string>() == manifestHash && Trial.Hash(path) == manifestHash,
            "DURABLE_CLAIM_MISMATCH");
        _ = StudioTrial.Load(root, path); // recheck expiry, hashes and installed identity after readiness
        Trial.Require(camera.Fault is null, "CAMERA_FAILED_BEFORE_OPEN");
        var token = File.ReadAllText(Path.Combine(root, ".openditoo-local/host.token")).Trim();
        Trial.Require(token.Length >= 32, "HOST_TOKEN_INVALID");
        using var client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false, UseProxy = false })
        { Timeout = TimeSpan.FromSeconds(7) };
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
        form.SetSessionStatus($"LIVE {trial.Id} — streaming to the Ditoo. Stop or close this window to end.");
        var result = await StudioSender.Run(trial, camera, client, stop.Token, form.SetSessionStatus);
        result["camera"] = camera.Name;
        result["captured"] = camera.Captured;
        result["replaced"] = camera.Replaced;
        result["transformMs"] = JsonSerializer.SerializeToNode(camera.TransformMs.Snapshot());
        result["framingAtStart"] = JsonSerializer.SerializeToNode(framingAtStart);
        result["framingAtEnd"] = JsonSerializer.SerializeToNode(form.CurrentFraming);
        Emit(new { kind = "result", experiment_id = trial.Id, result });
        form.SetSessionStatus($"Session ended: {result["outcome"]} / {result["terminalReason"]}");
        return result["outcome"]!.GetValue<string>() == "stopped_clean" ? 0 : 2;
    }
    catch (Exception ex)
    {
        Emit(new { kind = "error", error = ex.Message, outcome = "unknown" });
        return 2;
    }
    finally
    {
        try { form?.BeginInvoke(form.Close); } catch { /* already closed by the operator */ }
        ui?.Join();
        if (camera is not null) await Task.Run(() => camera.DisposeAsync().AsTask());
    }
}

// The live window path end to end -- real camera, real window, Stop/close, the W10 sender -- with the
// in-memory Host from the selftests. No manifest, no token, no Host client: nothing leaves the process.
static async Task<int> DryRun(int seconds)
{
    using var stop = new CancellationTokenSource();
    Console.CancelKeyPress += (_, e) => { e.Cancel = true; stop.Cancel(); };
    var camera = await StudioCamera.Open(Framing.Load().ToPreset());
    var (ui, shown) = StartUi(() => new StudioForm(camera, "OpenDitoo Webcam Studio — DRY RUN (in-memory Host, nothing is sent)", stop));
    var form = await shown.WaitAsync(TimeSpan.FromSeconds(10));
    try
    {
        var host = new StudioTests.HeartbeatHandler(new OfflineTests.FakeHandler());
        var trial = new Trial("OFFLINE-W10-DRYRUN", seconds, 500, 500 * Trial.WorstCaseFrameTxBytes, StudioModes.IntervalMs["max"]);
        var result = await StudioSender.Run(trial, camera, new HttpClient(host), stop.Token, form.SetSessionStatus);
        result["framingAtEnd"] = JsonSerializer.SerializeToNode(form.CurrentFraming);
        Emit(new { kind = "dryrun_result", result });
        return result["outcome"]!.GetValue<string>() == "stopped_clean" ? 0 : 2;
    }
    finally
    {
        try { form.BeginInvoke(form.Close); } catch { /* already closed by the operator */ }
        ui.Join();
        await Task.Run(() => camera.DisposeAsync().AsTask());
    }
}
