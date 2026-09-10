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
if (args.Length == 3 && args[0] == "live-policy") return await LivePolicy(args[1], args[2]);
if (args.Length == 2 && args[0] == "dryrun" && int.TryParse(args[1], out var drySeconds) && drySeconds is > 0 and <= 900)
    return await DryRun(drySeconds);
Console.Error.WriteLine("usage: preview | dryrun <seconds> | live-policy <policy> <repository> | selftest | transform-selftest <cases> | encoder-selftest <cases> | live <manifest> <repository>");
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
        var client = HostClient(token); // disposed by the typed session
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

static HttpClient HostClient(string token)
{
    var client = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false, UseProxy = false })
    { Timeout = TimeSpan.FromSeconds(7) };
    client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
    return client;
}

// Back-to-back bounded sessions in one window. The next session starts only after a clean budget or
// lifetime end; operator stop, any fault or any ambiguous outcome ends the run -- never a retry.
// `begin` returns null to end, and a fresh client each time: TypedSession disposes the one it used.
static async Task<List<JsonObject>> SessionLoop(StudioCamera camera, StudioForm form, CancellationTokenSource stop,
    Func<int, Task<(Trial Trial, HttpClient Client)?>> begin, Action<JsonObject> finished)
{
    var results = new List<JsonObject>();
    for (var seq = 1; !stop.IsCancellationRequested; seq++)
    {
        if (await begin(seq) is not { } next) break;
        var n = seq;
        form.SetSessionStatus($"LIVE session {n} — Stop or close this window to return to the dashboard");
        var result = await StudioSender.Run(next.Trial, camera, next.Client, stop.Token,
            text => form.SetSessionStatus($"LIVE session {n}: {text}  — Stop or close to end"));
        result["experimentId"] = next.Trial.Id;
        result["framingAtEnd"] = JsonSerializer.SerializeToNode(form.CurrentFraming);
        results.Add(result);
        finished(result);
        if (result["outcome"]!.GetValue<string>() != "stopped_clean" ||
            result["terminalReason"]!.GetValue<string>() is not ("budget_exhausted" or "lifetime_expired")) break;
    }
    return results;
}

// W10C: the standing webcam policy. Each session is announced with a fresh nonce; the WSL coordinator
// picks a fresh id, takes its durable one-use claim, and only then answers execute:<id>:<nonce>.
static async Task<int> LivePolicy(string policyArgument, string rootArgument)
{
    using var stop = new CancellationTokenSource();
    Console.CancelKeyPress += (_, e) => { e.Cancel = true; stop.Cancel(); };
    StudioCamera? camera = null;
    StudioForm? form = null;
    Thread? ui = null;
    try
    {
        var path = Path.GetFullPath(policyArgument);
        var root = Path.GetFullPath(rootArgument);
        var envelope = StudioTrial.LoadPolicy(root, path);
        var policyHash = Trial.Hash(path);
        camera = await StudioCamera.Open(Framing.Load().ToPreset());
        using (var startup = new CancellationTokenSource(TimeSpan.FromSeconds(5)))
            while (camera.LatestMatrix is null)
            {
                if (camera.Fault is { } fault) throw new IOException(fault);
                await Task.Delay(20, startup.Token);
            }
        var liveCamera = camera;
        (ui, var shown) = StartUi(() => new StudioForm(liveCamera, "OpenDitoo Webcam — LIVE (close to return to the dashboard)", stop));
        form = await shown.WaitAsync(TimeSpan.FromSeconds(10));
        var token = File.ReadAllText(Path.Combine(root, ".openditoo-local/host.token")).Trim();
        Trial.Require(token.Length >= 32, "HOST_TOKEN_INVALID");
        var results = await SessionLoop(camera, form, stop, async seq =>
        {
            if (stop.IsCancellationRequested) return null;
            var nonce = Guid.NewGuid().ToString("N");
            Emit(new { kind = "session_ready", policy_sha256 = policyHash, seq, nonce });
            var line = await Console.In.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(15));
            if (line == "end") return null;
            var parts = line?.Split(':') ?? [];
            Trial.Require(parts.Length == 3 && parts[0] == "execute" && parts[2] == nonce &&
                StudioTrial.SessionId.IsMatch(parts[1]), "CLAIM_HANDSHAKE_MISSING");
            var id = parts[1];
            var claim = JsonNode.Parse(File.ReadAllText(Path.Combine(root, ".openditoo-local/session-claims", id + ".json")))!;
            Trial.Require(claim["experiment_id"]!.GetValue<string>() == id && claim["state"]!.GetValue<string>() == "claimed" &&
                claim["nonce"]!.GetValue<string>() == nonce && claim["policy_sha256"]!.GetValue<string>() == policyHash &&
                Trial.Hash(path) == policyHash, "DURABLE_CLAIM_MISMATCH");
            _ = StudioTrial.LoadPolicy(root, path); // revocation or drift between sessions ends the run
            Trial.Require(liveCamera.Fault is null, "CAMERA_FAILED_BEFORE_OPEN");
            return (new Trial(id, envelope.Seconds, envelope.MaxFrames, envelope.MaxBytes, envelope.IntervalMs), HostClient(token));
        }, result => Emit(new { kind = "session_result", experiment_id = result["experimentId"], result }));
        Emit(new { kind = "done", sessions = results.Count });
        return results.All(r => r["outcome"]!.GetValue<string>() is "stopped_clean" or "stopped_yielded_to_stock") ? 0 : 2;
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

// The live window path end to end -- real camera, real window, Stop/close, session rollover -- with
// the in-memory Host from the selftests. No policy, no token, no Host client: nothing leaves the process.
static async Task<int> DryRun(int seconds)
{
    using var stop = new CancellationTokenSource();
    Console.CancelKeyPress += (_, e) => { e.Cancel = true; stop.Cancel(); };
    var camera = await StudioCamera.Open(Framing.Load().ToPreset());
    var (ui, shown) = StartUi(() => new StudioForm(camera, "OpenDitoo Webcam Studio — DRY RUN (in-memory Host, nothing is sent)", stop));
    var form = await shown.WaitAsync(TimeSpan.FromSeconds(10));
    try
    {
        // Small per-session budget so rollover is visible within seconds; at most 5 sessions.
        var results = await SessionLoop(camera, form, stop, seq => Task.FromResult<(Trial, HttpClient)?>(seq > 5 ? null :
            (new Trial($"OFFLINE-W10-DRYRUN-{seq}", seconds, 60, 60 * Trial.WorstCaseFrameTxBytes, StudioModes.IntervalMs["max"]),
             new HttpClient(new StudioTests.HeartbeatHandler(new OfflineTests.FakeHandler())))),
            result => Emit(new { kind = "dryrun_session", result }));
        return results.All(r => r["outcome"]!.GetValue<string>() == "stopped_clean") ? 0 : 2;
    }
    finally
    {
        try { form.BeginInvoke(form.Close); } catch { /* already closed by the operator */ }
        ui.Join();
        await Task.Run(() => camera.DisposeAsync().AsTask());
    }
}
