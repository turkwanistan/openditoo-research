using System.Diagnostics;

namespace OpenDitoo.Webcam.Probe;

/// <summary>
/// A slot holding exactly one item: the newest. Never a queue.
///
/// This is the whole freshest-frame policy in one type. A camera produces faster than the Ditoo
/// consumes, so something must be discarded; discarding the OLDEST is the only defensible
/// choice, because a frame that was current two frames ago is stale, and showing stale live
/// video is worse than skipping it. A queue here would convert a rate mismatch into unbounded
/// latency, which is exactly the failure the plan's Realtime acquisition mode avoids upstream.
///
/// Replacements are counted rather than hidden: the drop count is the headroom measurement.
/// </summary>
internal sealed class LatestFrameSlot<T>
{
    private readonly object gate = new();
    // Consumers wait on this instead of polling. Task.Delay/Sleep have ~15.6 ms granularity on
    // Windows, so a "1 ms" poll actually costs ~15 ms and shows up as pipeline latency that is
    // really just the timer.
    private readonly ManualResetEventSlim available = new(false);
    private T? item;
    private bool occupied;

    internal long Offered { get; private set; }
    internal long Replaced { get; private set; }
    internal long Taken { get; private set; }
    internal int MaxDepthObserved { get; private set; }

    /// <summary>Depth is 0 or 1, by construction. Asserted by the caller's invariant checks.</summary>
    internal int Depth { get { lock (gate) return occupied ? 1 : 0; } }

    internal void Put(T value)
    {
        lock (gate)
        {
            Offered++;
            if (occupied) Replaced++;   // the previous frame is dropped, not queued
            item = value;
            occupied = true;
            MaxDepthObserved = Math.Max(MaxDepthObserved, 1);
            available.Set();
        }
    }

    /// <summary>Block until something is available, or the token trips.</summary>
    internal bool Wait(CancellationToken token, int timeoutMs = 50)
    {
        try { return available.Wait(timeoutMs, token); }
        catch (OperationCanceledException) { return false; }
    }

    /// <summary>Take the newest item, or false if nothing new since the last take.</summary>
    internal bool TryTake(out T value)
    {
        lock (gate)
        {
            if (!occupied) { value = default!; return false; }
            value = item!;
            item = default;
            occupied = false;
            available.Reset();
            Taken++;
            return true;
        }
    }
}

/// <summary>
/// A wait that actually waits the requested time. Thread.Sleep and Task.Delay round up to the
/// system timer granularity (~15.6 ms), which turns a simulated 54 ms ACK into ~64 ms and makes
/// the harness, rather than the pipeline, fail the rate criterion. Sleep the bulk, spin the
/// remainder.
/// </summary>
internal static class PreciseDelay
{
    [System.Runtime.InteropServices.DllImport("winmm.dll", EntryPoint = "timeBeginPeriod")]
    private static extern uint TimeBeginPeriod(uint ms);

    [System.Runtime.InteropServices.DllImport("winmm.dll", EntryPoint = "timeEndPeriod")]
    private static extern uint TimeEndPeriod(uint ms);

    /// <summary>
    /// Raise the system timer resolution for the life of the returned scope.
    ///
    /// This exists only because we SIMULATE the ACK with a timer. The default ~15.6 ms tick
    /// turned a 54 ms simulated cycle into ~61 ms, which failed the rate criterion for reasons
    /// that had nothing to do with the pipeline. Real streaming waits on an actual HTTP
    /// response and needs none of this.
    /// </summary>
    internal static IDisposable HighResolutionScope() => new TimerScope();

    private sealed class TimerScope : IDisposable
    {
        internal TimerScope() => TimeBeginPeriod(1);
        public void Dispose() => TimeEndPeriod(1);
    }

    internal static void Wait(double milliseconds, CancellationToken token)
    {
        var deadline = Stopwatch.GetTimestamp() + (long)(milliseconds / 1000.0 * Stopwatch.Frequency);
        // With 1 ms timer resolution the coarse wait lands within ~1 ms, so the spin that
        // follows is short. A long spin burns a core and perturbs the very transform timings
        // this harness is measuring.
        var coarse = milliseconds - 1.5;
        if (coarse > 0)
        {
            try { Task.Delay(TimeSpan.FromMilliseconds(coarse), token).Wait(token); }
            catch (OperationCanceledException) { return; }
            catch (AggregateException) { return; }
        }
        var spinner = new SpinWait();
        while (Stopwatch.GetTimestamp() < deadline && !token.IsCancellationRequested)
            spinner.SpinOnce();
    }
}

internal readonly record struct TimedFrame(byte[] Pixels, int Width, int Height, double CapturedQpcMs);
