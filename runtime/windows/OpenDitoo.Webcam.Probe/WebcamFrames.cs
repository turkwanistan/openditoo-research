using System.Diagnostics;
using Windows.Media.Capture;
using Windows.Media.Capture.Frames;
using Windows.Media.MediaProperties;

namespace OpenDitoo.Webcam.Probe;

internal interface IFrameSource
{
    string? Fault { get; }
    /// <summary>Highest identity handed out by the camera so far; 0 before the first frame.</summary>
    long LastAcquiredSourceId { get; }
    bool TryTake(out TimedFrame frame);
    void Wait(CancellationToken token);
}

// Camera-only producer shared with the Windows adapter. No transport or credentials.
internal sealed class WebcamFrames : IFrameSource, IAsyncDisposable
{
    private readonly MediaCapture capture = new();
    private MediaFrameReader? reader;
    private readonly CancellationTokenSource stopping = new();
    private readonly LatestFrameSlot<TimedFrame> raw = new();
    private readonly LatestFrameSlot<TimedFrame> ready = new();
    private Task? processor;
    private string? fault;
    // Assigned at acquisition and never re-derived. Interlocked because FrameArrived runs on the
    // reader's thread while the sender reads the high-water mark from its own.
    private long sourceSequence;
    internal readonly Samples TransformMs = new();
    internal long Captured => raw.Offered;
    internal long RawReplaced => raw.Replaced;
    internal long Processed => ready.Offered;
    internal long Replaced => ready.Replaced;
    internal long Taken => ready.Taken;
    internal int RawMaxDepth => raw.MaxDepthObserved;
    internal int ReadyMaxDepth => ready.MaxDepthObserved;
    public string? Fault => Volatile.Read(ref fault);
    public long LastAcquiredSourceId => Interlocked.Read(ref sourceSequence);
    internal static double NowMs => Stopwatch.GetTimestamp() * 1000d / Stopwatch.Frequency;

    private void Fail(string reason)
    {
        Interlocked.CompareExchange(ref fault, reason, null);
        stopping.Cancel();
    }

    internal static async Task<WebcamFrames> Open()
    {
        var source = new WebcamFrames();
        try { await source.Start(); return source; }
        catch { await source.DisposeAsync(); throw; }
    }

    private async Task Start()
    {
        var groups = (await MediaFrameSourceGroup.FindAllAsync()).Where(g => g.SourceInfos.Any(i =>
            i.DeviceInformation?.Id.Contains("vid_0c45", StringComparison.OrdinalIgnoreCase) == true &&
            i.DeviceInformation.Id.Contains("pid_2690", StringComparison.OrdinalIgnoreCase))).ToArray();
        if (groups.Length != 1) throw new InvalidOperationException("CAMERA_EXACT_MATCH_REQUIRED");
        capture.Failed += (_, _) => Fail("camera_disconnected");
        await capture.InitializeAsync(new MediaCaptureInitializationSettings
        {
            SourceGroup = groups[0], SharingMode = MediaCaptureSharingMode.ExclusiveControl,
            MemoryPreference = MediaCaptureMemoryPreference.Cpu, StreamingCaptureMode = StreamingCaptureMode.Video,
        });
        var video = capture.FrameSources.Values.First(s =>
            s.Info.MediaStreamType is MediaStreamType.VideoRecord or MediaStreamType.VideoPreview);
        var format = video.SupportedFormats.FirstOrDefault(f =>
            f.Subtype == "NV12" && f.VideoFormat.Width == 640 && f.VideoFormat.Height == 480 &&
            f.FrameRate.Denominator != 0 && (double)f.FrameRate.Numerator / f.FrameRate.Denominator == 60);
        if (format is null) throw new InvalidOperationException("CAMERA_MODE_NOT_EXPOSED");
        await video.SetFormatAsync(format);
        reader = await capture.CreateFrameReaderAsync(video, MediaEncodingSubtypes.Bgra8);
        reader.AcquisitionMode = MediaFrameReaderAcquisitionMode.Realtime;
        reader.FrameArrived += (sender, _) =>
        {
            if (stopping.IsCancellationRequested) return;
            try
            {
                using var frame = sender.TryAcquireLatestFrame();
                var bitmap = frame?.VideoMediaFrame?.SoftwareBitmap;
                if (bitmap is null) return;
                if (frame!.SystemRelativeTime is not { } captured)
                    throw new InvalidOperationException("CAMERA_TIMESTAMP_MISSING");
                using var copy = bitmap.BitmapPixelFormat == Windows.Graphics.Imaging.BitmapPixelFormat.Bgra8
                    ? Windows.Graphics.Imaging.SoftwareBitmap.Copy(bitmap)
                    : Windows.Graphics.Imaging.SoftwareBitmap.Convert(bitmap, Windows.Graphics.Imaging.BitmapPixelFormat.Bgra8);
                var pixels = new byte[copy.PixelWidth * copy.PixelHeight * 4];
                var buffer = new Windows.Storage.Streams.Buffer((uint)pixels.Length);
                copy.CopyToBuffer(buffer);
                using (var data = Windows.Storage.Streams.DataReader.FromBuffer(buffer)) data.ReadBytes(pixels);
                // Identity is assigned here and only here: the moment a real N980P frame was
                // successfully acquired. A frame that failed to arrive never gets an id, so a
                // gap downstream always means "acquired but not selected", never "never existed".
                raw.Put(new(pixels, copy.PixelWidth, copy.PixelHeight, captured.TotalMilliseconds,
                    Interlocked.Increment(ref sourceSequence)));
            }
            catch { Fail("camera_disconnected"); }
        };
        processor = Task.Factory.StartNew(() =>
        {
            try
            {
                while (!stopping.IsCancellationRequested)
                {
                    if (!raw.Wait(stopping.Token) || !raw.TryTake(out var frame)) continue;
                    var started = NowMs;
                    var pixels = FrameTransform.Transform(frame.Pixels, frame.Width, frame.Height,
                        FrameTransform.Default, FrameTransform.SourceFormat.Bgra32);
                    TransformMs.Add(NowMs - started);
                    ready.Put(new(pixels, 16, 16, frame.CapturedQpcMs, frame.SourceId));
                }
            }
            catch { Fail("transform_fault"); }
        }, CancellationToken.None, TaskCreationOptions.LongRunning, TaskScheduler.Default);
        if (await reader.StartAsync() != MediaFrameReaderStartStatus.Success)
            throw new InvalidOperationException("CAMERA_START_FAILED");
    }

    public bool TryTake(out TimedFrame frame) => ready.TryTake(out frame);
    public void Wait(CancellationToken token) => ready.Wait(token, 50);

    public async ValueTask DisposeAsync()
    {
        stopping.Cancel();
        if (processor is not null) await processor;
        if (reader is not null)
        {
            try { await reader.StopAsync(); } catch { /* A disconnected reader is already stopped. */ }
            reader.Dispose();
        }
        capture.Dispose();
    }
}

// Bounded telemetry: cumulative count/mean/max, percentiles over the latest 2048 observations.
internal sealed class Samples
{
    private readonly double[] values = new double[2048];
    private long count;
    private double total, max;
    internal void Add(double value)
    {
        lock (values) { values[count++ % values.Length] = value; total += value; max = Math.Max(max, value); }
    }
    internal object Snapshot()
    {
        lock (values)
        {
            var sorted = values.Take((int)Math.Min(count, values.Length)).Order().ToArray();
            return new { count, mean = count == 0 ? 0 : total / count, max,
                percentileWindow = sorted.Length,
                p50 = sorted.Length == 0 ? 0 : sorted[sorted.Length / 2],
                p95 = sorted.Length == 0 ? 0 : sorted[Math.Min(sorted.Length - 1, (int)(sorted.Length * .95))] };
        }
    }
}
