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

/// <summary>
/// One frame plus the identity it was born with.
///
/// <paramref name="SourceId"/> is assigned once, at successful acquisition from the camera, and
/// is never re-derived downstream. That is the whole point: timestamps and nominal FPS cannot
/// tell a genuinely new scene sample apart from the same sample selected twice, so W9A carries
/// an identity instead of inferring one. It survives the raw slot, the transform and the ready
/// slot unchanged, which makes replacement, skipping and duplicate selection directly countable.
/// </summary>
internal readonly record struct TimedFrame(byte[] Pixels, int Width, int Height, double CapturedQpcMs,
                                           long SourceId = 0);

/// <summary>
/// Bounded evidence about WHICH source frames the sender actually selected.
///
/// This answers a question the W8 telemetry could not: 16.285 fps of ACKed transport says
/// nothing about how many distinct scene samples reached the panel. Gaps here are frames the
/// freshest-frame policy deliberately dropped; a duplicate is the same acquisition selected
/// twice, which is a scheduler defect rather than a transport one. Kept deliberately small --
/// identities only, no pixels -- so it stays honest evidence and not a frame recorder.
/// </summary>
internal sealed class SourceIdentityLedger
{
    // A 10 s trial is capped at 201 frames by the manifest, so this ring never wraps in a real
    // run. It is a ring anyway, because unbounded growth in a long soak is how telemetry turns
    // into the leak it was meant to measure.
    private const int Capacity = 512;
    private readonly long[] selected = new long[Capacity];
    private long count;

    internal long First { get; private set; }
    internal long Last { get; private set; }
    /// <summary>Acquisitions that existed but were never selected, summed across gaps.</summary>
    internal long Skipped { get; private set; }
    /// <summary>The same acquisition selected more than once. Should always be zero.</summary>
    internal long DuplicateSelections { get; private set; }
    /// <summary>An identity that went backwards: a monotonicity violation, never expected.</summary>
    internal long OutOfOrderSelections { get; private set; }

    internal void Select(long sourceId)
    {
        if (count == 0) First = sourceId;
        else if (sourceId == Last) DuplicateSelections++;
        else if (sourceId < Last) OutOfOrderSelections++;
        else Skipped += sourceId - Last - 1;
        Last = sourceId;
        selected[count++ % Capacity] = sourceId;
    }

    internal object Snapshot(long lastAcquiredId) => new
    {
        selectedCount = count,
        firstSelectedSourceId = count == 0 ? 0 : First,
        lastSelectedSourceId = count == 0 ? 0 : Last,
        lastAcquiredSourceId = lastAcquiredId,
        // Acquired-but-unselected between the first and last selection. Distinct from
        // acquisitions that arrived after the final send, which are not skips.
        skippedBetweenSelections = Skipped,
        duplicateSelections = DuplicateSelections,
        outOfOrderSelections = OutOfOrderSelections,
        selectedSourceIds = selected.Take((int)Math.Min(count, Capacity)).ToArray(),
        selectedSourceIdWindow = Math.Min(count, Capacity),
    };
}
