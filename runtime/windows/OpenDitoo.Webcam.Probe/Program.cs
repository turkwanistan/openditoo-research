// W1: enumerate what the owner's webcam actually exposes, and measure frame arrival.
//
// This tool exists because the implementation plan's recommended capture mode
// (640x480@60 YUY2) is a hypothesis about this device, and ~37 MB/s of YUY2 against
// roughly 40 MB/s of practical USB 2.0 bandwidth is too close to assume. It reaches no
// Ditoo, holds no token, and links nothing from the Host project.
using System.Diagnostics;
using System.Text.Json;
using Windows.Media.Capture;
using Windows.Media.Capture.Frames;
using Windows.Media.MediaProperties;

// Both pipeline loops block for long stretches. On the thread pool they compete with the
// MediaFrameReader callback; dedicated threads keep capture off the critical path.
static Task RunOnDedicatedThread(Action body)
{
    var completion = new TaskCompletionSource();
    var thread = new Thread(() =>
    {
        try { body(); completion.SetResult(); }
        catch (Exception ex) { completion.SetException(ex); }
    }) { IsBackground = true, Priority = ThreadPriority.AboveNormal };
    thread.Start();
    return completion.Task;
}

static int Fail(string message)
{
    Console.Error.WriteLine($"WEBCAM_PROBE_FAIL: {message}");
    return 2;
}

// Initialization is the fragile step: a SourceGroup that enumerates fine can still refuse
// ExclusiveControl with "Element not found". Try the least invasive settings first and report
// which one worked, rather than hiding a fallback.
static async Task<(MediaCapture? Capture, string Strategy, List<string> Errors)> TryInitialize(
    MediaFrameSourceGroup group, bool exclusive)
{
    var errors = new List<string>();
    var attempts = new List<(string Name, MediaCaptureInitializationSettings Settings)>();
    if (!exclusive)
        attempts.Add(("sourceGroup+sharedReadOnly", new MediaCaptureInitializationSettings
        {
            SourceGroup = group,
            SharingMode = MediaCaptureSharingMode.SharedReadOnly,
            MemoryPreference = MediaCaptureMemoryPreference.Cpu,
            StreamingCaptureMode = StreamingCaptureMode.Video,
        }));
    attempts.Add(("sourceGroup+exclusive", new MediaCaptureInitializationSettings
    {
        SourceGroup = group,
        SharingMode = MediaCaptureSharingMode.ExclusiveControl,
        MemoryPreference = MediaCaptureMemoryPreference.Cpu,
        StreamingCaptureMode = StreamingCaptureMode.Video,
    }));
    var videoDeviceId = group.SourceInfos
        .FirstOrDefault(i => i.SourceKind == MediaFrameSourceKind.Color)?.DeviceInformation?.Id;
    if (videoDeviceId is not null)
        attempts.Add(("videoDeviceId+exclusive", new MediaCaptureInitializationSettings
        {
            VideoDeviceId = videoDeviceId,
            SharingMode = MediaCaptureSharingMode.ExclusiveControl,
            MemoryPreference = MediaCaptureMemoryPreference.Cpu,
            StreamingCaptureMode = StreamingCaptureMode.Video,
        }));

    foreach (var (name, settings) in attempts)
    {
        var capture = new MediaCapture();
        try
        {
            await capture.InitializeAsync(settings);
            return (capture, name, errors);
        }
        catch (Exception ex)
        {
            errors.Add($"{name}: {ex.GetType().Name} 0x{ex.HResult:X8} {ex.Message.Trim()}");
            capture.Dispose();
        }
    }
    return (null, "none", errors);
}

var mode = args.Length > 0 ? args[0] : "enumerate";

// Offline parity check against the Python reference. Starts no camera and touches nothing.
if (mode == "encoder-selftest")
{
    if (args.Length < 2) return Fail("encoder-selftest <fixture.json>");
    return OpenDitoo.Webcam.Probe.DitooEncoder.SelfTest(args[1]);
}

if (mode == "transform-selftest")
{
    if (args.Length < 2) return Fail("transform-selftest <fixture.json>");
    return OpenDitoo.Webcam.Probe.FrameTransform.SelfTest(args[1]);
}

var groups = await MediaFrameSourceGroup.FindAllAsync();
if (groups.Count == 0) return Fail("no MediaFrameSourceGroup present");

// --------------------------------------------------------------------------
// enumerate
// --------------------------------------------------------------------------
if (mode == "enumerate")
{
    var report = new List<object>();
    foreach (var group in groups)
    {
        var sources = new List<object>();
        foreach (var info in group.SourceInfos)
        {
            // SupportedFormats needs an initialized MediaCapture, so this is the cheapest
            // honest enumeration: initialize once per group, read, dispose.
            sources.Add(new
            {
                id = info.Id,
                kind = info.SourceKind.ToString(),
                mediaStreamType = info.MediaStreamType.ToString(),
                deviceId = info.DeviceInformation?.Id,
            });
        }
        report.Add(new { group.Id, group.DisplayName, sources });
    }

    var formats = new List<object>();
    var target = groups.FirstOrDefault(g => g.DisplayName.Contains("NexiGo", StringComparison.OrdinalIgnoreCase))
                 ?? groups[0];
    var (capture, strategy, initErrors) = await TryInitialize(target, exclusive: false);
    if (capture is null)
    {
        // The device list is still evidence, so report it rather than dying with nothing.
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            ok = false,
            command = "enumerate",
            errorCode = "CAMERA_INITIALIZE_FAILED",
            deviceIo = false,
            ditooTouched = false,
            selectedGroup = target.DisplayName,
            groups = report,
            initErrors,
        }, new JsonSerializerOptions { WriteIndented = true }));
        return 2;
    }
    using (capture)
    foreach (var (key, source) in capture.FrameSources)
    {
        foreach (var format in source.SupportedFormats)
        {
            var fps = format.FrameRate.Denominator == 0
                ? 0d
                : (double)format.FrameRate.Numerator / format.FrameRate.Denominator;
            formats.Add(new
            {
                sourceId = key,
                mediaStreamType = source.Info.MediaStreamType.ToString(),
                subtype = format.Subtype,
                width = format.VideoFormat.Width,
                height = format.VideoFormat.Height,
                fps = Math.Round(fps, 3),
                // Uncompressed bandwidth at this mode, which is the USB question for YUY2.
                approxBytesPerSecond = format.Subtype.Equals("YUY2", StringComparison.OrdinalIgnoreCase)
                    ? (long)(format.VideoFormat.Width * format.VideoFormat.Height * 2 * fps)
                    : 0,
            });
        }
    }
    Console.WriteLine(JsonSerializer.Serialize(new
    {
        ok = true,
        command = "enumerate",
        deviceIo = false,
        ditooTouched = false,
        selectedGroup = target.DisplayName,
        initStrategy = strategy,
        initErrors,
        groups = report,
        formatCount = formats.Count,
        formats,
    }, new JsonSerializerOptions { WriteIndented = true }));
    return 0;
}

// --------------------------------------------------------------------------
// benchmark <subtype> <width> <height> <fps> <seconds>
// --------------------------------------------------------------------------
if (mode == "benchmark")
{
    if (args.Length < 6) return Fail("benchmark <subtype> <width> <height> <fps> <seconds>");
    var wantSubtype = args[1];
    var wantWidth = uint.Parse(args[2]);
    var wantHeight = uint.Parse(args[3]);
    var wantFps = double.Parse(args[4]);
    var seconds = int.Parse(args[5]);

    var target = groups.FirstOrDefault(g => g.DisplayName.Contains("NexiGo", StringComparison.OrdinalIgnoreCase))
                 ?? groups[0];
    // A benchmark must set the format, which needs exclusive control.
    var (capture, strategy, initErrors) = await TryInitialize(target, exclusive: true);
    if (capture is null) return Fail($"camera initialize failed: {string.Join(" | ", initErrors)}");
    using var owned = capture;

    var source = capture.FrameSources.Values.FirstOrDefault(s =>
        s.Info.MediaStreamType == MediaStreamType.VideoRecord ||
        s.Info.MediaStreamType == MediaStreamType.VideoPreview);
    if (source is null) return Fail("no video frame source");

    // Mode selection must never silently fall back: an unenumerated mode is a refusal, so a
    // benchmark can never quietly measure something other than what it claims.
    var chosen = source.SupportedFormats.FirstOrDefault(f =>
        f.Subtype.Equals(wantSubtype, StringComparison.OrdinalIgnoreCase) &&
        f.VideoFormat.Width == wantWidth && f.VideoFormat.Height == wantHeight &&
        f.FrameRate.Denominator != 0 &&
        Math.Abs((double)f.FrameRate.Numerator / f.FrameRate.Denominator - wantFps) < 0.51);
    if (chosen is null) return Fail($"mode not exposed: {wantSubtype} {wantWidth}x{wantHeight}@{wantFps}");
    await source.SetFormatAsync(chosen);

    // Exposure is the prime suspect whenever a 60 fps mode delivers far less: a UVC camera
    // lengthens exposure in dim light and the frame rate falls out of that, silently. Report
    // it always, and optionally pin it, so "the camera is slow" is never left as a guess.
    var exposure = capture.VideoDeviceController.ExposureControl;
    object exposureBefore = exposure.Supported
        ? new { supported = true, auto = exposure.Auto, valueMs = exposure.Value.TotalMilliseconds,
                minMs = exposure.Min.TotalMilliseconds, maxMs = exposure.Max.TotalMilliseconds,
                stepMs = exposure.Step.TotalMilliseconds }
        : new { supported = false, auto = false, valueMs = 0d, minMs = 0d, maxMs = 0d, stepMs = 0d };
    string exposureAction = "left_as_found";
    if (args.Length > 6 && double.TryParse(args[6], out var wantExposureMs))
    {
        if (!exposure.Supported) exposureAction = "unsupported";
        else
        {
            await exposure.SetAutoAsync(false);
            var clamped = Math.Clamp(wantExposureMs, exposure.Min.TotalMilliseconds,
                                     exposure.Max.TotalMilliseconds);
            await exposure.SetValueAsync(TimeSpan.FromMilliseconds(clamped));
            exposureAction = $"manual_{clamped:0.###}ms";
        }
    }

    using var reader = await capture.CreateFrameReaderAsync(source);
    // Realtime is the whole point: it drops frames when the consumer cannot keep up rather
    // than building a FIFO of stale ones. Buffered would invalidate every age measurement.
    reader.AcquisitionMode = MediaFrameReaderAcquisitionMode.Realtime;

    var interarrival = new List<double>();
    var ages = new List<double>();
    var callbacks = new List<double>();
    long frames = 0, nulls = 0;
    var clock = Stopwatch.StartNew();
    double lastArrival = -1;
    var stallAges = new List<double>();
    var stallPending = 0;

    reader.FrameArrived += (sender, _) =>
    {
        var callbackStart = clock.Elapsed.TotalMilliseconds;
        using var frame = sender.TryAcquireLatestFrame();
        if (frame is null) { Interlocked.Increment(ref nulls); return; }
        var now = clock.Elapsed.TotalMilliseconds;
        lock (interarrival)
        {
            if (lastArrival >= 0) interarrival.Add(now - lastArrival);
            lastArrival = now;
            // SystemRelativeTime is the capture instant on the QPC clock, whose origin is
            // boot -- and Stopwatch.GetTimestamp() reads that same counter. So the age is a
            // direct subtraction, with no anchoring and no drift between two clocks.
            if (frame.SystemRelativeTime is { } captured)
            {
                var qpcNowMs = Stopwatch.GetTimestamp() * 1000.0 / Stopwatch.Frequency;
                var age = qpcNowMs - captured.TotalMilliseconds;
                ages.Add(age);
                if (stallPending > 0) { stallAges.Add(age); stallPending--; }
            }
            frames++;
            callbacks.Add(clock.Elapsed.TotalMilliseconds - callbackStart);
        }
    };

    await reader.StartAsync();

    // Deliberately stall the consumer: frame age must recover immediately afterwards. If it
    // climbs instead, we are being fed a queue and every latency number is a lie.
    for (var i = 0; i < seconds; i++)
    {
        await Task.Delay(1000);
        if (i is 2 or 5 or 8)
        {
            Thread.Sleep(100);
            lock (interarrival) stallPending = 3;
        }
    }
    await reader.StopAsync();

    static object Stats(List<double> values)
    {
        if (values.Count == 0) return new { count = 0 };
        var sorted = values.OrderBy(v => v).ToList();
        return new
        {
            count = sorted.Count,
            p50 = Math.Round(sorted[sorted.Count / 2], 2),
            p95 = Math.Round(sorted[Math.Min(sorted.Count - 1, (int)(sorted.Count * 0.95))], 2),
            max = Math.Round(sorted[^1], 2),
        };
    }

    Console.WriteLine(JsonSerializer.Serialize(new
    {
        ok = true,
        command = "benchmark",
        deviceIo = false,
        ditooTouched = false,
        requestedMode = new { subtype = chosen.Subtype, width = chosen.VideoFormat.Width,
                             height = chosen.VideoFormat.Height,
                             fps = Math.Round((double)chosen.FrameRate.Numerator / chosen.FrameRate.Denominator, 3) },
        negotiatedMode = new
        {
            subtype = source.CurrentFormat.Subtype,
            width = source.CurrentFormat.VideoFormat.Width,
            height = source.CurrentFormat.VideoFormat.Height,
            fps = source.CurrentFormat.FrameRate.Denominator == 0 ? 0d
                  : Math.Round((double)source.CurrentFormat.FrameRate.Numerator
                               / source.CurrentFormat.FrameRate.Denominator, 3),
        },
        acquisitionMode = reader.AcquisitionMode.ToString(),
        exposureBefore,
        exposureAction,
        elapsedSeconds = Math.Round(clock.Elapsed.TotalSeconds, 2),
        frames,
        nullAcquisitions = nulls,
        measuredFps = Math.Round(frames / clock.Elapsed.TotalSeconds, 2),
        interarrivalMs = Stats(interarrival),
        sourceAgeMs = Stats(ages),
        callbackMs = Stats(callbacks),
        ageAfterDeliberateStallMs = Stats(stallAges),
    }, new JsonSerializerOptions { WriteIndented = true }));
    return 0;
}

// --------------------------------------------------------------------------
// snapshot <subtype> <width> <height> <fps> <count> <outDir>
// --------------------------------------------------------------------------
// Saves representative stills for the 16x16 downscale shootout, and reports mean luma --
// which is how "the camera only delivers 20 fps" gets separated from "the room is dark and
// the sensor is holding the shutter open", on a camera whose exposure WinRT cannot read.
if (mode == "snapshot")
{
    if (args.Length < 7) return Fail("snapshot <subtype> <width> <height> <fps> <count> <outDir>");
    var wantSubtype = args[1];
    var wantWidth = uint.Parse(args[2]);
    var wantHeight = uint.Parse(args[3]);
    var wantFps = double.Parse(args[4]);
    var count = int.Parse(args[5]);
    var outDir = args[6];
    Directory.CreateDirectory(outDir);

    var target = groups.FirstOrDefault(g => g.DisplayName.Contains("NexiGo", StringComparison.OrdinalIgnoreCase))
                 ?? groups[0];
    var (capture, _, initErrors) = await TryInitialize(target, exclusive: true);
    if (capture is null) return Fail($"camera initialize failed: {string.Join(" | ", initErrors)}");
    using var owned = capture;
    var source = capture.FrameSources.Values.FirstOrDefault(s =>
        s.Info.MediaStreamType is MediaStreamType.VideoRecord or MediaStreamType.VideoPreview);
    if (source is null) return Fail("no video frame source");
    var chosen = source.SupportedFormats.FirstOrDefault(f =>
        f.Subtype.Equals(wantSubtype, StringComparison.OrdinalIgnoreCase) &&
        f.VideoFormat.Width == wantWidth && f.VideoFormat.Height == wantHeight &&
        f.FrameRate.Denominator != 0 &&
        Math.Abs((double)f.FrameRate.Numerator / f.FrameRate.Denominator - wantFps) < 0.51);
    if (chosen is null) return Fail($"mode not exposed: {wantSubtype} {wantWidth}x{wantHeight}@{wantFps}");
    await source.SetFormatAsync(chosen);

    using var reader = await capture.CreateFrameReaderAsync(source, MediaEncodingSubtypes.Bgra8);
    reader.AcquisitionMode = MediaFrameReaderAcquisitionMode.Realtime;
    await reader.StartAsync();

    var saved = new List<object>();
    for (var index = 0; index < count; index++)
    {
        await Task.Delay(400);
        using var frame = reader.TryAcquireLatestFrame();
        var bitmap = frame?.VideoMediaFrame?.SoftwareBitmap;
        if (bitmap is null) continue;
        using var converted = bitmap.BitmapPixelFormat == Windows.Graphics.Imaging.BitmapPixelFormat.Bgra8
            ? Windows.Graphics.Imaging.SoftwareBitmap.Copy(bitmap)
            : Windows.Graphics.Imaging.SoftwareBitmap.Convert(
                bitmap, Windows.Graphics.Imaging.BitmapPixelFormat.Bgra8);

        // Mean luma straight off the pixels, so brightness is measured rather than eyeballed.
        // Copied through a WinRT buffer rather than locked with unsafe COM interop: this runs
        // a handful of times, so clarity beats avoiding one copy.
        var bytes = new byte[converted.PixelWidth * converted.PixelHeight * 4];
        var pixelBuffer = new Windows.Storage.Streams.Buffer((uint)bytes.Length);
        converted.CopyToBuffer(pixelBuffer);
        using (var dataReader = Windows.Storage.Streams.DataReader.FromBuffer(pixelBuffer))
            dataReader.ReadBytes(bytes);
        double lumaSum = 0;
        long pixels = 0;
        for (var offset = 0; offset + 3 < bytes.Length; offset += 4)
        {
            // BGRA order.
            lumaSum += 0.0722 * bytes[offset] + 0.7152 * bytes[offset + 1] + 0.2126 * bytes[offset + 2];
            pixels++;
        }

        var path = Path.Combine(outDir, $"still-{index:000}.png");
        using var stream = new FileStream(path, FileMode.Create);
        var encoder = await Windows.Graphics.Imaging.BitmapEncoder.CreateAsync(
            Windows.Graphics.Imaging.BitmapEncoder.PngEncoderId, stream.AsRandomAccessStream());
        encoder.SetSoftwareBitmap(converted);
        await encoder.FlushAsync();
        saved.Add(new { file = path, width = converted.PixelWidth, height = converted.PixelHeight,
                        meanLuma0To255 = Math.Round(pixels == 0 ? 0 : lumaSum / pixels, 2) });
    }
    await reader.StopAsync();
    Console.WriteLine(JsonSerializer.Serialize(new
    {
        ok = saved.Count > 0, command = "snapshot", deviceIo = false, ditooTouched = false,
        mode = new { chosen.Subtype, chosen.VideoFormat.Width, chosen.VideoFormat.Height },
        saved,
    }, new JsonSerializerOptions { WriteIndented = true }));
    return saved.Count > 0 ? 0 : 2;
}

// --------------------------------------------------------------------------
// pipeline <subtype> <width> <height> <fps> <seconds> <fakeAckMs>
// --------------------------------------------------------------------------
// W3: camera -> latest raw slot -> transform -> latest processed slot -> simulated ACK sender.
// Reaches NO Ditoo and holds no Host token: the transport here is a delay, deliberately, so
// the freshest-frame semantics can be proven before any device is involved.
if (mode == "pipeline")
{
    if (args.Length < 7) return Fail("pipeline <subtype> <width> <height> <fps> <seconds> <fakeAckMs>");
    var wantSubtype = args[1];
    var wantWidth = uint.Parse(args[2]);
    var wantHeight = uint.Parse(args[3]);
    var wantFps = double.Parse(args[4]);
    var seconds = int.Parse(args[5]);
    var fakeAckMs = int.Parse(args[6]);
    if (fakeAckMs is < 40 or > 100) return Fail("fakeAckMs must be 40..100");

    var target = groups.FirstOrDefault(g => g.DisplayName.Contains("NexiGo", StringComparison.OrdinalIgnoreCase))
                 ?? groups[0];
    var (capture, _, initErrors) = await TryInitialize(target, exclusive: true);
    if (capture is null) return Fail($"camera initialize failed: {string.Join(" | ", initErrors)}");
    using var owned = capture;
    var source = capture.FrameSources.Values.FirstOrDefault(s =>
        s.Info.MediaStreamType is MediaStreamType.VideoRecord or MediaStreamType.VideoPreview);
    if (source is null) return Fail("no video frame source");
    var chosen = source.SupportedFormats.FirstOrDefault(f =>
        f.Subtype.Equals(wantSubtype, StringComparison.OrdinalIgnoreCase) &&
        f.VideoFormat.Width == wantWidth && f.VideoFormat.Height == wantHeight &&
        f.FrameRate.Denominator != 0 &&
        Math.Abs((double)f.FrameRate.Numerator / f.FrameRate.Denominator - wantFps) < 0.51);
    if (chosen is null) return Fail($"mode not exposed: {wantSubtype} {wantWidth}x{wantHeight}@{wantFps}");
    await source.SetFormatAsync(chosen);

    var rawSlot = new OpenDitoo.Webcam.Probe.LatestFrameSlot<OpenDitoo.Webcam.Probe.TimedFrame>();
    var processedSlot = new OpenDitoo.Webcam.Probe.LatestFrameSlot<OpenDitoo.Webcam.Probe.TimedFrame>();
    var transformMs = new List<double>();
    var senderCycleMs = new List<double>();
    var ageAtSendMs = new List<double>();
    var senderIterations = 0L;
    double senderFirstSendMs = 0, senderLastSendMs = 0;
    var senderIdle = 0L;
    var maxRawDepth = 0;
    var maxProcessedDepth = 0;
    var preset = OpenDitoo.Webcam.Probe.FrameTransform.Default;

    static double QpcNowMs() => Stopwatch.GetTimestamp() * 1000.0 / Stopwatch.Frequency;

    using var reader = await capture.CreateFrameReaderAsync(source, MediaEncodingSubtypes.Bgra8);
    reader.AcquisitionMode = MediaFrameReaderAcquisitionMode.Realtime;
    reader.FrameArrived += (sender, _) =>
    {
        using var frame = sender.TryAcquireLatestFrame();
        var bitmap = frame?.VideoMediaFrame?.SoftwareBitmap;
        if (bitmap is null) return;
        using var converted = bitmap.BitmapPixelFormat == Windows.Graphics.Imaging.BitmapPixelFormat.Bgra8
            ? Windows.Graphics.Imaging.SoftwareBitmap.Copy(bitmap)
            : Windows.Graphics.Imaging.SoftwareBitmap.Convert(bitmap, Windows.Graphics.Imaging.BitmapPixelFormat.Bgra8);
        // Keep the callback cheap: copy the native BGRA out and leave every conversion to the
        // processor. (An earlier comment here blamed this conversion for a ~29 fps camera rate.
        // A control run with no Bgra8 conversion measured the same 28.35 fps, so that was
        // wrong: camera rate tracks exposure/lighting, per the W1 findings. Doing less work on
        // the callback thread is still right, and it halved transform p95.)
        var bgra = new byte[converted.PixelWidth * converted.PixelHeight * 4];
        var buffer = new Windows.Storage.Streams.Buffer((uint)bgra.Length);
        converted.CopyToBuffer(buffer);
        using (var dr = Windows.Storage.Streams.DataReader.FromBuffer(buffer)) dr.ReadBytes(bgra);
        var captured = frame!.SystemRelativeTime?.TotalMilliseconds ?? QpcNowMs();
        rawSlot.Put(new OpenDitoo.Webcam.Probe.TimedFrame(bgra, converted.PixelWidth, converted.PixelHeight, captured));
        maxRawDepth = Math.Max(maxRawDepth, rawSlot.Depth);
    };

    using var stopping = new CancellationTokenSource(TimeSpan.FromSeconds(seconds));
    // Only needed because the ACK here is simulated with a timer; see PreciseDelay.
    using var timerResolution = OpenDitoo.Webcam.Probe.PreciseDelay.HighResolutionScope();
    await reader.StartAsync();

    var processor = RunOnDedicatedThread(() =>
    {
        while (!stopping.IsCancellationRequested)
        {
            if (!rawSlot.Wait(stopping.Token)) continue;
            if (rawSlot.TryTake(out var raw))
            {
                var started = QpcNowMs();
                var pixels = OpenDitoo.Webcam.Probe.FrameTransform.Transform(
                    raw.Pixels, raw.Width, raw.Height, preset,
                    OpenDitoo.Webcam.Probe.FrameTransform.SourceFormat.Bgra32);
                lock (transformMs) transformMs.Add(QpcNowMs() - started);
                processedSlot.Put(new OpenDitoo.Webcam.Probe.TimedFrame(pixels, 16, 16, raw.CapturedQpcMs));
                maxProcessedDepth = Math.Max(maxProcessedDepth, processedSlot.Depth);
            }
        }
    });

    var senderTask = RunOnDedicatedThread(() =>
    {
        while (!stopping.IsCancellationRequested)
        {
            // Only ever select AFTER the previous simulated ACK: one frame in flight, and no
            // catch-up burst is possible because nothing is queued behind it.
            if (processedSlot.TryTake(out var ready))
            {
                var cycleStart = QpcNowMs();
                if (senderIterations == 0) senderFirstSendMs = cycleStart;
                senderLastSendMs = cycleStart;
                senderIterations++;
                lock (ageAtSendMs) ageAtSendMs.Add(QpcNowMs() - ready.CapturedQpcMs);
                OpenDitoo.Webcam.Probe.PreciseDelay.Wait(fakeAckMs, stopping.Token);
                lock (senderCycleMs) senderCycleMs.Add(QpcNowMs() - cycleStart);
            }
            else
            {
                senderIdle++;   // nothing newer: never resend the same frame
                // Block for the next frame rather than poll. A 10 ms poll here cost the sender
                // ~4% of its achievable rate whenever a frame landed just after a check.
                if (!processedSlot.Wait(stopping.Token, 1000)) continue;
            }
        }
    });

    try { await Task.WhenAll(processor, senderTask); } catch (OperationCanceledException) { }
    await reader.StopAsync();

    static object Stats(List<double> values)
    {
        if (values.Count == 0) return new { count = 0 };
        var sorted = values.OrderBy(v => v).ToList();
        return new
        {
            count = sorted.Count,
            p50 = Math.Round(sorted[sorted.Count / 2], 2),
            p95 = Math.Round(sorted[Math.Min(sorted.Count - 1, (int)(sorted.Count * 0.95))], 2),
            max = Math.Round(sorted[^1], 2),
        };
    }

    var transformStats = Stats(transformMs);
    var ageStats = Stats(ageAtSendMs);
    // Rate over the sender's OWN active span, not wall clock: camera start-up and the trailing
    // partial cycle are not part of a sustained-rate measurement and made a saturated sender
    // look 4% slow.
    var senderSpanSeconds = (senderLastSendMs - senderFirstSendMs) / 1000.0;
    var sendersPerSecond = senderIterations > 1 && senderSpanSeconds > 0
        ? Math.Round((senderIterations - 1) / senderSpanSeconds, 2)
        : 0.0;
    Console.WriteLine(JsonSerializer.Serialize(new
    {
        ok = true,
        command = "pipeline",
        deviceIo = false,
        ditooTouched = false,
        note = "the transport is a delay, not a device; no Host token is held and no Ditoo is reachable",
        requestedMode = new { chosen.Subtype, chosen.VideoFormat.Width, chosen.VideoFormat.Height,
                             fps = Math.Round((double)chosen.FrameRate.Numerator / chosen.FrameRate.Denominator, 3) },
        negotiatedMode = new
        {
            subtype = source.CurrentFormat.Subtype,
            width = source.CurrentFormat.VideoFormat.Width,
            height = source.CurrentFormat.VideoFormat.Height,
            fps = source.CurrentFormat.FrameRate.Denominator == 0 ? 0d
                  : Math.Round((double)source.CurrentFormat.FrameRate.Numerator
                               / source.CurrentFormat.FrameRate.Denominator, 3),
        },
        preset = preset.Name,
        seconds,
        fakeAckMs,
        camera = new { offered = rawSlot.Offered, replacedBeforeUse = rawSlot.Replaced, taken = rawSlot.Taken },
        processed = new { offered = processedSlot.Offered, replacedBeforeUse = processedSlot.Replaced,
                          taken = processedSlot.Taken },
        senderIterations,
        senderIterationsPerSecond = sendersPerSecond,
        senderActiveSpanSeconds = Math.Round(senderSpanSeconds, 2),
        senderIterationsPerSecondWallClock = Math.Round(senderIterations / (double)seconds, 2),
        senderIdlePolls = senderIdle,
        transformMs = transformStats,
        senderCycleMs = Stats(senderCycleMs),
        cameraFps = Math.Round(rawSlot.Offered / (double)seconds, 2),
        sourceAgeAtFakeSendMs = ageStats,
        queueDepth = new { maxRaw = maxRawDepth, maxProcessed = maxProcessedDepth },
        exitCriteria = new
        {
            transformP95Under5ms = transformMs.Count > 0 && ((dynamic)transformStats).p95 <= 5.0,
            senderIterationsPerSecondAtLeast18 = sendersPerSecond >= 18.0,
            sourceAgeP95Under50ms = ageAtSendMs.Count > 0 && ((dynamic)ageStats).p95 <= 50.0,
            queueDepthNeverAboveOne = maxRawDepth <= 1 && maxProcessedDepth <= 1,
        },
    }, new JsonSerializerOptions { WriteIndented = true }));
    return 0;
}

// --------------------------------------------------------------------------
// dryrun <subtype> <width> <height> <fps> <seconds> <fakeAckMs>
// --------------------------------------------------------------------------
// W5: the full application path -- capture, latest slot, transform, palette guard, canonical
// encoder + hash, typed session semantics, ACK clock -- with an IN-MEMORY Host stand-in.
// No Bluetooth, no socket, no token, no Ditoo. The fake enforces the same budgets, pacing
// floor and encoder-hash check the real Host does, so refusals surface here rather than live.
if (mode == "dryrun")
{
    if (args.Length < 7) return Fail("dryrun <subtype> <width> <height> <fps> <seconds> <fakeAckMs>");
    var wantSubtype = args[1];
    var wantWidth = uint.Parse(args[2]);
    var wantHeight = uint.Parse(args[3]);
    var wantFps = double.Parse(args[4]);
    var seconds = int.Parse(args[5]);
    var fakeAckMs = int.Parse(args[6]);

    var target = groups.FirstOrDefault(g => g.DisplayName.Contains("NexiGo", StringComparison.OrdinalIgnoreCase))
                 ?? groups[0];
    var (capture, _, initErrors) = await TryInitialize(target, exclusive: true);
    if (capture is null) return Fail($"camera initialize failed: {string.Join(" | ", initErrors)}");
    using var owned = capture;
    var source = capture.FrameSources.Values.FirstOrDefault(s =>
        s.Info.MediaStreamType is MediaStreamType.VideoRecord or MediaStreamType.VideoPreview);
    if (source is null) return Fail("no video frame source");
    var chosen = source.SupportedFormats.FirstOrDefault(f =>
        f.Subtype.Equals(wantSubtype, StringComparison.OrdinalIgnoreCase) &&
        f.VideoFormat.Width == wantWidth && f.VideoFormat.Height == wantHeight &&
        f.FrameRate.Denominator != 0 &&
        Math.Abs((double)f.FrameRate.Numerator / f.FrameRate.Denominator - wantFps) < 0.51);
    if (chosen is null) return Fail($"mode not exposed: {wantSubtype} {wantWidth}x{wantHeight}@{wantFps}");
    await source.SetFormatAsync(chosen);

    var preset = OpenDitoo.Webcam.Probe.FrameTransform.Default;
    var rawSlot = new OpenDitoo.Webcam.Probe.LatestFrameSlot<OpenDitoo.Webcam.Probe.TimedFrame>();
    var readySlot = new OpenDitoo.Webcam.Probe.LatestFrameSlot<(OpenDitoo.Webcam.Probe.TimedFrame Frame, string Sha)>();
    var transformMs = new List<double>();
    var encodeMs = new List<double>();
    var ageAtSendMs = new List<double>();
    var hostElapsedMs = new List<double>();
    var refusals = new Dictionary<string, int>();
    var memorySamples = new List<long>();
    var maxRawDepth = 0; var maxReadyDepth = 0;

    static double QpcNowMs() => Stopwatch.GetTimestamp() * 1000.0 / Stopwatch.Frequency;

    // Budgets sized exactly as a reviewed manifest would: lifetime at the floor, capped by the
    // Host's own 500-frame ceiling, and the encoder's worst-case bytes per frame.
    var floorMs = 40;
    var frameCeiling = Math.Min(seconds * 1000 / floorMs + 1, 500);
    var session = new OpenDitoo.Webcam.Probe.FakeTypedHostSession(
        OpenDitoo.Webcam.Probe.FakeTypedHostSession.ProfileStreamingAckClock,
        seconds, floorMs, frameCeiling, frameCeiling * 1054, fakeAckMs);

    using var reader = await capture.CreateFrameReaderAsync(source, MediaEncodingSubtypes.Bgra8);
    reader.AcquisitionMode = MediaFrameReaderAcquisitionMode.Realtime;
    reader.FrameArrived += (sender, _) =>
    {
        using var frame = sender.TryAcquireLatestFrame();
        var bitmap = frame?.VideoMediaFrame?.SoftwareBitmap;
        if (bitmap is null) return;
        using var converted = bitmap.BitmapPixelFormat == Windows.Graphics.Imaging.BitmapPixelFormat.Bgra8
            ? Windows.Graphics.Imaging.SoftwareBitmap.Copy(bitmap)
            : Windows.Graphics.Imaging.SoftwareBitmap.Convert(bitmap, Windows.Graphics.Imaging.BitmapPixelFormat.Bgra8);
        var bgra = new byte[converted.PixelWidth * converted.PixelHeight * 4];
        var buffer = new Windows.Storage.Streams.Buffer((uint)bgra.Length);
        converted.CopyToBuffer(buffer);
        using (var dr = Windows.Storage.Streams.DataReader.FromBuffer(buffer)) dr.ReadBytes(bgra);
        rawSlot.Put(new OpenDitoo.Webcam.Probe.TimedFrame(
            bgra, converted.PixelWidth, converted.PixelHeight,
            frame!.SystemRelativeTime?.TotalMilliseconds ?? QpcNowMs()));
        maxRawDepth = Math.Max(maxRawDepth, rawSlot.Depth);
    };

    using var stopping = new CancellationTokenSource(TimeSpan.FromSeconds(seconds));
    using var timerResolution = OpenDitoo.Webcam.Probe.PreciseDelay.HighResolutionScope();
    await reader.StartAsync();

    var processor = RunOnDedicatedThread(() =>
    {
        while (!stopping.IsCancellationRequested)
        {
            if (!rawSlot.Wait(stopping.Token)) continue;
            if (!rawSlot.TryTake(out var raw)) continue;
            var t0 = QpcNowMs();
            var pixels = OpenDitoo.Webcam.Probe.FrameTransform.Transform(
                raw.Pixels, raw.Width, raw.Height, preset,
                OpenDitoo.Webcam.Probe.FrameTransform.SourceFormat.Bgra32);
            var t1 = QpcNowMs();
            var (packet, _) = OpenDitoo.Webcam.Probe.DitooEncoder.EncodeRgb888(pixels);
            var sha = OpenDitoo.Webcam.Probe.DitooEncoder.Sha256Hex(packet);
            var t2 = QpcNowMs();
            lock (transformMs) { transformMs.Add(t1 - t0); encodeMs.Add(t2 - t1); }
            readySlot.Put((new OpenDitoo.Webcam.Probe.TimedFrame(pixels, 16, 16, raw.CapturedQpcMs), sha));
            maxReadyDepth = Math.Max(maxReadyDepth, readySlot.Depth);
        }
    });

    var sender = RunOnDedicatedThread(() =>
    {
        while (!stopping.IsCancellationRequested && !session.Expired)
        {
            if (!readySlot.TryTake(out var ready))
            {
                if (!readySlot.Wait(stopping.Token, 1000)) continue;
                continue;
            }
            var age = QpcNowMs() - ready.Frame.CapturedQpcMs;
            var outcome = session.SendFrame(ready.Frame.Pixels, ready.Sha, stopping.Token);
            if (outcome.Ok)
            {
                lock (ageAtSendMs) { ageAtSendMs.Add(age); hostElapsedMs.Add(outcome.HostElapsedMs); }
            }
            else
            {
                lock (refusals)
                    refusals[outcome.ErrorCode!] = refusals.GetValueOrDefault(outcome.ErrorCode!) + 1;
                if (outcome.ErrorCode is "SESSION_LIFETIME_EXPIRED" or "SESSION_FRAME_BUDGET_EXHAUSTED"
                    or "SESSION_TX_BUDGET_EXHAUSTED") break;
            }
            lock (memorySamples) memorySamples.Add(GC.GetTotalMemory(false));
        }
    });

    try { await Task.WhenAll(processor, sender); } catch (OperationCanceledException) { }
    await reader.StopAsync();
    session.Close("operator_stop");

    static object Stats(List<double> values)
    {
        if (values.Count == 0) return new { count = 0 };
        var sorted = values.OrderBy(v => v).ToList();
        return new { count = sorted.Count, p50 = Math.Round(sorted[sorted.Count / 2], 2),
                     p95 = Math.Round(sorted[Math.Min(sorted.Count - 1, (int)(sorted.Count * 0.95))], 2),
                     max = Math.Round(sorted[^1], 2) };
    }

    var transformStats = Stats(transformMs);
    var ageStats = Stats(ageAtSendMs);
    var cameraFps = Math.Round(rawSlot.Offered / (double)seconds, 2);
    var throughputFps = transformMs.Count > 0 && transformMs.Sum() > 0
        ? Math.Round(transformMs.Count / ((transformMs.Sum() + encodeMs.Sum()) / 1000.0), 1) : 0;
    var memoryFirst = memorySamples.Count > 0 ? memorySamples[0] : 0;
    var memoryLast = memorySamples.Count > 0 ? memorySamples[^1] : 0;

    Console.WriteLine(JsonSerializer.Serialize(new
    {
        ok = true, command = "dryrun", deviceIo = false, ditooTouched = false, bluetoothTouched = false,
        note = "in-memory typed-Host stand-in; the ACK is a delay and no socket is opened",
        negotiatedMode = new { subtype = source.CurrentFormat.Subtype,
                               width = source.CurrentFormat.VideoFormat.Width,
                               height = source.CurrentFormat.VideoFormat.Height,
                               fps = source.CurrentFormat.FrameRate.Denominator == 0 ? 0d
                                     : Math.Round((double)source.CurrentFormat.FrameRate.Numerator
                                                  / source.CurrentFormat.FrameRate.Denominator, 3) },
        preset = preset.Name,
        sessionProfile = session.SessionProfile,
        seconds, fakeAckMs,
        cameraFps,
        framesSent = session.FramesSent,
        packetsSent = session.PacketsSent,
        txBytesSent = session.TxBytesSent,
        terminalReason = session.TerminalReason,
        terminalOutcome = session.TerminalOutcome,
        refusals,
        transformMs = transformStats,
        encodeMs = Stats(encodeMs),
        hostTransactionMs = Stats(hostElapsedMs),
        sourceAgeAtSimulatedSendMs = ageStats,
        processingThroughputFps = throughputFps,
        replacement = new { rawOffered = rawSlot.Offered, rawReplaced = rawSlot.Replaced,
                            readyOffered = readySlot.Offered, readyReplaced = readySlot.Replaced },
        queueDepth = new { maxRaw = maxRawDepth, maxReady = maxReadyDepth },
        managedMemoryBytes = new { first = memoryFirst, last = memoryLast,
                                   deltaKb = Math.Round((memoryLast - memoryFirst) / 1024.0, 1) },
        thresholds = new
        {
            transformP95Under5ms = transformMs.Count > 0 && ((dynamic)transformStats).p95 <= 5.0,
            sourceAgeP95Under75ms = ageAtSendMs.Count > 0 && ((dynamic)ageStats).p95 <= 75.0,
            queueDepthNeverAboveOne = maxRawDepth <= 1 && maxReadyDepth <= 1,
            processingThroughputOver100Fps = throughputFps > 100.0,
            noEncoderHashMismatch = !refusals.ContainsKey("IMAGE_ENCODER_HASH_MISMATCH"),
            cameraFpsAtLeast58 = cameraFps >= 58.0,
        },
    }, new JsonSerializerOptions { WriteIndented = true }));
    return 0;
}

return Fail($"unknown mode: {mode}");
