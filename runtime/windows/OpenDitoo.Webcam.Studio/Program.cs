using OpenDitoo.Webcam.Studio;

// Preview never reads the Host token and never constructs an HTTP client: it cannot reach the
// Ditoo. A live mode is added only together with its reviewed manifest and grant.
if (args.Length == 1 && args[0] == "selftest") return await StudioTests.Run();
if (args.Length == 1 && args[0] == "preview") return RunUi(() => new StudioForm(null, "OpenDitoo Webcam Studio — preview"));
Console.Error.WriteLine("usage: selftest | preview");
return 2;

static int RunUi(Func<StudioForm> create)
{
    StudioForm? form = null;
    var ui = new Thread(() =>
    {
        Application.EnableVisualStyles();
        Application.SetHighDpiMode(HighDpiMode.SystemAware);
        form = create();
        form.Shown += async (_, _) => await form.Reconnect();
        Application.Run(form);
    });
    ui.SetApartmentState(ApartmentState.STA);
    ui.Start();
    ui.Join();
    // Off the UI thread: DisposeAsync awaits without ConfigureAwait and would deadlock there.
    if (form?.Camera is { } camera) Task.Run(() => camera.DisposeAsync().AsTask()).Wait();
    return 0;
}
