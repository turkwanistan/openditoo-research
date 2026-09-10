using System.Runtime.CompilerServices;
using OpenDitoo.Webcam.Probe;
using Windows.Media.Capture;
using Windows.Media.Capture.Frames;
using Windows.Media.MediaProperties;

namespace OpenDitoo.Webcam.Studio;

/// <summary>
/// The exact N980P, same mode and freshest-frame slots as the frozen WebcamFrames, plus the two
/// things the product needs: a preset the operator can change while frames flow, and read-only
/// copies of the latest source and 16x16 frame for preview that never steal from the sender.
/// ponytail: duplicates WebcamFrames' acquisition because that file is hash-frozen by the parked
/// W9B-007 manifest; fold the two together once 007 is retired.
/// </summary>
internal sealed class StudioCamera : IFrameSource, IAsyncDisposable
{
    private readonly MediaCapture capture = new();
    private MediaFrameReader? reader;
    private readonly CancellationTokenSource stopping = new();
    private readonly LatestFrameSlot<TimedFrame> raw = new();
    private readonly LatestFrameSlot<TimedFrame> ready = new();
    private Task? processor;
    private string? fault;
    private long sourceSequence;
    private FrameTransform.Preset preset;
    // Boxed so preview reads are atomic; a struct written from another thread can tear.
    private StrongBox<TimedFrame>? latestSource, latestMatrix;
    internal readonly Samples TransformMs = new();
    internal string Name { get; private set; } = "";
    internal string Mode { get; private set; } = "";
    internal long Captured => raw.Offered;
    internal long Replaced => ready.Replaced;
    public string? Fault => Volatile.Read(ref fault);
    public long LastAcquiredSourceId => Interlocked.Read(ref sourceSequence);
    /// <summary>Read by the transform thread per frame; replaced whole, never mutated.</summary>
    internal FrameTransform.Preset Preset { get => Volatile.Read(ref preset); set => Volatile.Write(ref preset, value); }
    /// <summary>Preview only. BGRA at camera resolution.</summary>
    internal TimedFrame? LatestSource => Volatile.Read(ref latestSource)?.Value;
    /// <summary>Preview only. The exact 768 RGB888 bytes the sender would transmit.</summary>
    internal TimedFrame? LatestMatrix => Volatile.Read(ref latestMatrix)?.Value;

    private StudioCamera(FrameTransform.Preset preset) => this.preset = preset;

    private void Fail(string reason)
    {
        Interlocked.CompareExchange(ref fault, reason, null);
        stopping.Cancel();
    }

    internal static async Task<StudioCamera> Open(FrameTransform.Preset preset)
    {
        var camera = new StudioCamera(preset);
        try { await camera.Start(); return camera; }
        catch { await camera.DisposeAsync(); throw; }
    }

    private async Task Start()
    {
        var groups = (await MediaFrameSourceGroup.FindAllAsync()).Where(g => g.SourceInfos.Any(i =>
            i.DeviceInformation?.Id.Contains("vid_0c45", StringComparison.OrdinalIgnoreCase) == true &&
            i.DeviceInformation.Id.Contains("pid_2690", StringComparison.OrdinalIgnoreCase))).ToArray();
        if (groups.Length != 1) throw new InvalidOperationException("CAMERA_EXACT_MATCH_REQUIRED");
        Name = groups[0].DisplayName;
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
        Mode = "NV12 640x480 @ 60 requested, Realtime (USB 0C45:2690)";
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
                var item = new TimedFrame(pixels, copy.PixelWidth, copy.PixelHeight, captured.TotalMilliseconds,
                    Interlocked.Increment(ref sourceSequence));
                Volatile.Write(ref latestSource, new StrongBox<TimedFrame>(item));
                raw.Put(item);
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
                    var started = WebcamFrames.NowMs;
                    var pixels = FrameTransform.Transform(frame.Pixels, frame.Width, frame.Height,
                        Preset, FrameTransform.SourceFormat.Bgra32);
                    TransformMs.Add(WebcamFrames.NowMs - started);
                    var item = new TimedFrame(pixels, 16, 16, frame.CapturedQpcMs, frame.SourceId);
                    Volatile.Write(ref latestMatrix, new StrongBox<TimedFrame>(item));
                    ready.Put(item);
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
