using System.Diagnostics;

/// <summary>
/// Bounded in-memory diagnostics for the single typed image operation.
/// Volatile by design: a Host restart erases prior observations instead of
/// replaying a historical success as current device truth.
/// </summary>
sealed class ImageOperation
{
    private readonly object gate = new();
    private readonly Stopwatch elapsed = Stopwatch.StartNew();

    internal string OperationId { get; } = Guid.NewGuid().ToString("N")[..12];
    internal DateTimeOffset StartedAtUtc { get; } = DateTimeOffset.UtcNow;
    internal DateTimeOffset? EndedAtUtc { get; private set; }
    internal string? ImagePacketSha256 { get; private set; }
    internal int PaletteColors { get; private set; } = -1;
    internal string LastCompletedStage { get; private set; } = "received";
    internal string Result { get; private set; } = "in_progress";
    internal int PacketsPlanned { get; private set; }
    internal int TxBytesPlanned { get; private set; }
    internal int PacketsSentComplete { get; private set; }
    internal int TxBytesSentComplete { get; private set; }
    internal bool InFlightPacketBytesUnknown { get; private set; }
    internal bool SocketClosed { get; private set; }
    internal string? AckPayloadHex { get; private set; }
    internal string? ErrorCode { get; private set; }
    private readonly List<object> frameTimings = [];

    /// <summary>Per-frame measurement for the M8 rate study.</summary>
    internal void FrameCompleted(int frameNumber, long ackLatencyMs, long sinceFirstFrameMs, byte ack)
    {
        lock (gate) frameTimings.Add(new
        {
            frame = frameNumber,
            ackLatencyMs,
            sinceFirstFrameMs,
            ackPayloadHex = $"0x{ack:X2}",
        });
    }

    internal object[] FrameTimings
    {
        get { lock (gate) return frameTimings.ToArray(); }
    }

    internal void Encoded(string packetSha256, int paletteColors)
    {
        lock (gate)
        {
            ImagePacketSha256 = packetSha256;
            PaletteColors = paletteColors;
            LastCompletedStage = "validation";
        }
    }

    internal void Planned(byte[][] packets)
    {
        lock (gate)
        {
            PacketsPlanned = packets.Length;
            TxBytesPlanned = packets.Sum(packet => packet.Length);
        }
    }

    internal void StageCompleted(string stage)
    {
        lock (gate) LastCompletedStage = stage;
    }

    internal void PacketSent(int bytes)
    {
        lock (gate)
        {
            PacketsSentComplete++;
            TxBytesSentComplete += bytes;
            LastCompletedStage = $"packet_{PacketsSentComplete}_sent";
        }
    }

    /// A send that did not complete leaves an unknown number of bytes on the wire.
    internal void SendOutcomeUnknown()
    {
        lock (gate) InFlightPacketBytesUnknown = true;
    }

    internal void SocketWasClosed()
    {
        lock (gate) SocketClosed = true;
    }

    internal void Finish(string result, string? ackPayloadHex, string? errorCode)
    {
        lock (gate)
        {
            Result = result;
            AckPayloadHex = ackPayloadHex;
            ErrorCode = errorCode;
            EndedAtUtc = DateTimeOffset.UtcNow;
        }
    }

    internal object Snapshot()
    {
        lock (gate) return new
        {
            operationId = OperationId,
            startedAtUtc = StartedAtUtc.ToString("O"),
            endedAtUtc = EndedAtUtc?.ToString("O"),
            durationMs = EndedAtUtc is null ? (long?)null : elapsed.ElapsedMilliseconds,
            imagePacketSha256 = ImagePacketSha256,
            paletteColors = PaletteColors < 0 ? (int?)null : PaletteColors,
            lastCompletedStage = LastCompletedStage,
            result = Result,
            packetsPlanned = PacketsPlanned,
            txBytesPlanned = TxBytesPlanned,
            packetsSentComplete = PacketsSentComplete,
            txBytesSentComplete = TxBytesSentComplete,
            inFlightPacketBytesUnknown = InFlightPacketBytesUnknown,
            socketClosed = SocketClosed,
            ackPayloadHex = AckPayloadHex,
            errorCode = ErrorCode,
            frameTimings = FrameTimings,
            retry = false,
        };
    }
}

static class ImageOperationLog
{
    private const int RecentLimit = 5;
    private static readonly object Gate = new();
    private static readonly Queue<object> Recent = new();
    private static ImageOperation? current;
    private static object? last;
    private static int completed;

    internal static DateTimeOffset HostStartedAtUtc { get; } = DateTimeOffset.UtcNow;

    internal static ImageOperation Begin()
    {
        var operation = new ImageOperation();
        lock (Gate) current = operation;
        return operation;
    }

    internal static void End(ImageOperation operation)
    {
        var snapshot = operation.Snapshot();
        lock (Gate)
        {
            if (ReferenceEquals(current, operation)) current = null;
            last = snapshot;
            completed++;
            Recent.Enqueue(snapshot);
            while (Recent.Count > RecentLimit) Recent.Dequeue();
        }
    }

    internal static object Snapshot()
    {
        lock (Gate) return new
        {
            operationInProgress = current is not null,
            inProgressOperation = current?.Snapshot(),
            operationsCompletedSinceHostStart = completed,
            lastOperation = last,
            recentOperations = Recent.ToArray(),
        };
    }
}
