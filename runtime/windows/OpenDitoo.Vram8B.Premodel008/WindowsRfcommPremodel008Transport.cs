using System.Diagnostics;
using System.Runtime.InteropServices;

internal static class WindowsRfcommPremodel008Transport
{
    private const int AfBth = 32;
    private const int SockStream = 1;
    private const int BthProtoRfcomm = 3;
    private const int SocketError = -1;
    private static readonly IntPtr InvalidSocket = new(-1);
    private static readonly IntPtr InvalidEvent = IntPtr.Zero;
    private const int WsaWouldBlock = 10035;
    private const uint WsaWaitTimeout = 258;
    private const uint WsaWaitEvent0 = 0;
    private const uint WsaWaitFailed = 0xFFFFFFFF;
    private const int FdRead = 1 << 0;
    private const int FdWrite = 1 << 1;
    private const int FdConnect = 1 << 4;
    private const int FdClose = 1 << 5;
    private const int FdReadBit = 0;
    private const int FdWriteBit = 1;
    private const int FdConnectBit = 4;
    private const int FdCloseBit = 5;
    private const int FdMaxEvents = 10;

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    private struct SockAddrBth
    {
        public ushort AddressFamily;
        public ulong BluetoothAddress;
        public Guid ServiceClassId;
        public uint Port;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct WsaNetworkEvents
    {
        public int NetworkEvents;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = FdMaxEvents)] public int[] ErrorCodes;
        public static WsaNetworkEvents Create() => new() { ErrorCodes = new int[FdMaxEvents] };
    }

    [DllImport("Ws2_32.dll")] private static extern int WSAStartup(ushort versionRequested, IntPtr wsaData);
    [DllImport("Ws2_32.dll")] private static extern int WSACleanup();
    [DllImport("Ws2_32.dll")] private static extern IntPtr socket(int addressFamily, int socketType, int protocol);
    [DllImport("Ws2_32.dll")] private static extern int closesocket(IntPtr socketHandle);
    [DllImport("Ws2_32.dll")] private static extern int connect(IntPtr socketHandle, ref SockAddrBth name, int nameLength);
    [DllImport("Ws2_32.dll")] private static extern int send(IntPtr socketHandle, byte[] buffer, int length, int flags);
    [DllImport("Ws2_32.dll")] private static extern int recv(IntPtr socketHandle, byte[] buffer, int length, int flags);
    [DllImport("Ws2_32.dll")] private static extern int WSAGetLastError();
    [DllImport("Ws2_32.dll")] private static extern IntPtr WSACreateEvent();
    [DllImport("Ws2_32.dll")] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool WSACloseEvent(IntPtr eventHandle);
    [DllImport("Ws2_32.dll")] private static extern int WSAEventSelect(IntPtr socketHandle, IntPtr eventHandle, int networkEvents);
    [DllImport("Ws2_32.dll")] private static extern int WSAEnumNetworkEvents(IntPtr socketHandle, IntPtr eventHandle, ref WsaNetworkEvents networkEvents);
    [DllImport("Ws2_32.dll")] private static extern uint WSAWaitForMultipleEvents(uint eventCount, [In] IntPtr[] eventHandles, [MarshalAs(UnmanagedType.Bool)] bool waitAll, uint timeoutMilliseconds, [MarshalAs(UnmanagedType.Bool)] bool alertable);

    internal sealed record Report(long ElapsedMs, string Phase, string WireHex, int WireLength, byte OuterCommand, byte InnerCommand, byte Tag, string PayloadHex, ushort ChecksumLe16);
    internal sealed record Result(int ConnectionsAttempted, int SendsCompleted, int CustomOverwriteSends, long OverwriteElapsedMs, long ObservationMilliseconds, bool ConnectionSurvivedObservation, IReadOnlyList<Report> Reports);

    internal sealed class TransportStopException : Exception
    {
        internal int ConnectionsAttempted { get; }
        internal int SendsCompleted { get; }
        internal int CustomOverwriteSends { get; }
        internal IReadOnlyList<Report> Reports { get; }
        internal TransportStopException(string message, int connectionsAttempted, int sendsCompleted, int customOverwriteSends, IReadOnlyList<Report> reports, Exception inner)
            : base(message, inner)
        {
            ConnectionsAttempted = connectionsAttempted;
            SendsCompleted = sendsCompleted;
            CustomOverwriteSends = customOverwriteSends;
            Reports = reports;
        }
    }

    internal static Result RunExactlyOnce(byte[][] fixtures)
    {
        var total = Stopwatch.StartNew();
        var wsaData = Marshal.AllocHGlobal(512);
        var socketHandle = InvalidSocket;
        var eventHandle = InvalidEvent;
        var started = false;
        var connectionsAttempted = 0;
        var sends = 0;
        var customOverwriteSends = 0;
        var overwriteElapsedMs = -1L;
        var reports = new List<Report>();
        try
        {
            for (var i = 0; i < 512; i++) Marshal.WriteByte(wsaData, i, 0);
            var startup = WSAStartup(0x0202, wsaData);
            if (startup != 0) throw new InvalidOperationException($"PREMODEL008_WSASTARTUP_FAILED WSA={startup}; NO_RETRY");
            started = true;
            var layoutSize = Marshal.SizeOf<SockAddrBth>();
            if (layoutSize != 30) throw new InvalidOperationException($"PREMODEL008_SOCKADDR_BTH_LAYOUT_REJECTED SIZE={layoutSize}");
            socketHandle = socket(AfBth, SockStream, BthProtoRfcomm);
            if (socketHandle == InvalidSocket) throw new InvalidOperationException($"PREMODEL008_SOCKET_CREATE_FAILED WSA={WSAGetLastError()}; NO_RETRY");
            eventHandle = WSACreateEvent();
            if (eventHandle == InvalidEvent) throw new InvalidOperationException($"PREMODEL008_EVENT_CREATE_FAILED WSA={WSAGetLastError()}; NO_RETRY");

            SelectEvents(socketHandle, eventHandle, FdConnect, "CONNECT");
            var remote = new SockAddrBth { AddressFamily = (ushort)AfBth, BluetoothAddress = FrozenPremodel008Protocol.TargetBluetoothAddress, ServiceClassId = Guid.Empty, Port = FrozenPremodel008Protocol.TargetRfcommChannel };
            var connectDeadline = new Deadline(FrozenPremodel008Protocol.ConnectBudgetMs);
            connectionsAttempted = 1;
            var cr = connect(socketHandle, ref remote, layoutSize);
            if (cr == SocketError)
            {
                var error = WSAGetLastError();
                if (error != WsaWouldBlock) throw new InvalidOperationException($"PREMODEL008_CONNECT_FAILED WSA={error}; NO_RETRY");
                WaitForExactEvent(socketHandle, eventHandle, FdConnect, FdConnectBit, connectDeadline, "CONNECT");
            }

            SelectEvents(socketHandle, eventHandle, FdWrite | FdClose, "INITIAL_WRITE_WINDOW");
            WaitForInitialWritable(socketHandle, eventHandle, new Deadline(5_000));
            SelectEvents(socketHandle, eventHandle, FdClose, "PRIME_PRE_SEND");
            SendSingleCall(socketHandle, eventHandle, fixtures[0], "PRIME_0X6E");
            sends++;
            Thread.Sleep(FrozenPremodel008Protocol.InterPacketDelayMs);
            SelectEvents(socketHandle, eventHandle, FdClose, "VOICETIP_PRE_SEND");
            SendSingleCall(socketHandle, eventHandle, fixtures[1], "VOICETIP_0XA5");
            sends++;

            var observation = Stopwatch.StartNew();
            overwriteElapsedMs = CaptureWithScheduledOverwrite(socketHandle, eventHandle, observation, reports, fixtures[2], ref sends, ref customOverwriteSends);
            if (sends != FrozenPremodel008Protocol.ExactApplicationSends) throw new InvalidOperationException($"PREMODEL008_SEND_COUNT_DRIFT sends={sends}; NO_RETRY");
            if (customOverwriteSends != 1) throw new InvalidOperationException($"PREMODEL008_CUSTOM_SEND_COUNT_DRIFT count={customOverwriteSends}; NO_RETRY");
            if (total.ElapsedMilliseconds > FrozenPremodel008Protocol.TotalBudgetMs) throw new TimeoutException("PREMODEL008_TOTAL_BUDGET_EXCEEDED; NO_RETRY");
            return new Result(connectionsAttempted, sends, customOverwriteSends, overwriteElapsedMs, observation.ElapsedMilliseconds, true, reports);
        }
        catch (Exception ex) when (ex is not TransportStopException)
        {
            throw new TransportStopException(ex.Message, connectionsAttempted, sends, customOverwriteSends, reports.ToArray(), ex);
        }
        finally
        {
            if (socketHandle != InvalidSocket) closesocket(socketHandle);
            if (eventHandle != InvalidEvent) WSACloseEvent(eventHandle);
            if (started) WSACleanup();
            Marshal.FreeHGlobal(wsaData);
        }
    }

    private static long CaptureWithScheduledOverwrite(IntPtr socketHandle, IntPtr eventHandle, Stopwatch observation, List<Report> reports, byte[] overwriteFixture, ref int sends, ref int customOverwriteSends)
    {
        SelectEvents(socketHandle, eventHandle, FdRead | FdClose, "CAPTURE");
        var pending = new List<byte>();
        var chunk = new byte[1024];
        var overwriteSent = false;
        var overwriteElapsedMs = -1L;
        while (true)
        {
            DrainCurrentlyAvailable(socketHandle, chunk, pending);
            ParseAvailableFrames(pending, observation, reports, overwriteSent ? "post_overwrite" : "pre_overwrite");

            var elapsed = observation.ElapsedMilliseconds;
            if (!overwriteSent && elapsed >= FrozenPremodel008Protocol.OverwriteTargetElapsedMs)
            {
                SendSingleCall(socketHandle, eventHandle, overwriteFixture, "PREMODEL_0X6C");
                sends++;
                customOverwriteSends++;
                overwriteSent = true;
                overwriteElapsedMs = observation.ElapsedMilliseconds;
                Console.WriteLine($"PREMODEL008_OVERWRITE_SENT elapsed_ms={overwriteElapsedMs} source_length=0x{FrozenPremodel008Protocol.CustomSourceLength:X}");
                continue;
            }

            if (elapsed >= FrozenPremodel008Protocol.CaptureWindowMs)
            {
                if (!overwriteSent) throw new InvalidOperationException("PREMODEL008_CAPTURE_ENDED_BEFORE_OVERWRITE; NO_RETRY");
                if (pending.Count != 0) throw new InvalidOperationException($"PREMODEL008_CAPTURE_ENDED_WITH_PARTIAL_FRAME bytes={pending.Count}; NO_RETRY");
                return overwriteElapsedMs;
            }

            var nextDeadlineMs = overwriteSent ? FrozenPremodel008Protocol.CaptureWindowMs : Math.Min(FrozenPremodel008Protocol.OverwriteTargetElapsedMs, FrozenPremodel008Protocol.CaptureWindowMs);
            var remaining = nextDeadlineMs - elapsed;
            if (remaining <= 0) continue;
            var wait = WSAWaitForMultipleEvents(1, [eventHandle], false, (uint)Math.Max(1, remaining), false);
            if (wait == WsaWaitTimeout) continue;
            if (wait == WsaWaitFailed) throw new InvalidOperationException($"PREMODEL008_CAPTURE_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
            if (wait != WsaWaitEvent0) throw new InvalidOperationException($"PREMODEL008_CAPTURE_WAIT_UNEXPECTED RESULT={wait}; NO_RETRY");
            var events = WsaNetworkEvents.Create();
            if (WSAEnumNetworkEvents(socketHandle, eventHandle, ref events) == SocketError) throw new InvalidOperationException($"PREMODEL008_CAPTURE_ENUM_FAILED WSA={WSAGetLastError()}; NO_RETRY");
            if ((events.NetworkEvents & FdClose) != 0) throw new InvalidOperationException($"PREMODEL008_DISCONNECTED_DURING_CAPTURE WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
            if ((events.NetworkEvents & FdRead) == 0) continue;
            if (events.ErrorCodes[FdReadBit] != 0) throw new InvalidOperationException($"PREMODEL008_CAPTURE_READ_EVENT_FAILED WSA={events.ErrorCodes[FdReadBit]}; NO_RETRY");
            while (true)
            {
                var got = recv(socketHandle, chunk, chunk.Length, 0);
                if (got == 0) throw new InvalidOperationException("PREMODEL008_CAPTURE_RECV_DISCONNECTED; NO_RETRY");
                if (got < 0)
                {
                    var error = WSAGetLastError();
                    if (error == WsaWouldBlock) break;
                    throw new InvalidOperationException($"PREMODEL008_CAPTURE_RECV_FAILED WSA={error}; NO_RETRY");
                }
                for (var i = 0; i < got; i++) pending.Add(chunk[i]);
                if (pending.Count > FrozenPremodel008Protocol.MaxBufferedBytes) throw new InvalidOperationException($"PREMODEL008_CAPTURE_BUFFER_EXCEEDED bytes={pending.Count}; NO_RETRY");
                ParseAvailableFrames(pending, observation, reports, overwriteSent ? "post_overwrite" : "pre_overwrite");
            }
        }
    }

    private static void DrainCurrentlyAvailable(IntPtr socketHandle, byte[] chunk, List<byte> pending)
    {
        while (true)
        {
            var got = recv(socketHandle, chunk, chunk.Length, 0);
            if (got == 0) throw new InvalidOperationException("PREMODEL008_CAPTURE_RECV_DISCONNECTED; NO_RETRY");
            if (got < 0)
            {
                var error = WSAGetLastError();
                if (error == WsaWouldBlock) return;
                throw new InvalidOperationException($"PREMODEL008_CAPTURE_RECV_FAILED WSA={error}; NO_RETRY");
            }
            for (var i = 0; i < got; i++) pending.Add(chunk[i]);
            if (pending.Count > FrozenPremodel008Protocol.MaxBufferedBytes) throw new InvalidOperationException($"PREMODEL008_CAPTURE_BUFFER_EXCEEDED bytes={pending.Count}; NO_RETRY");
        }
    }

    private static void ParseAvailableFrames(List<byte> pending, Stopwatch observation, List<Report> reports, string phase)
    {
        while (true)
        {
            if (pending.Count == 0) return;
            if (pending[0] != 0x01) throw new InvalidOperationException($"PREMODEL008_FRAME_START_REJECTED value=0x{pending[0]:X2}; NO_RETRY");
            if (pending.Count < 3) return;
            var innerLength = pending[1] | (pending[2] << 8);
            var expectedTotal = innerLength + 4;
            if (expectedTotal < 9 || expectedTotal > FrozenPremodel008Protocol.MaxWireBytes) throw new InvalidOperationException($"PREMODEL008_FRAME_LENGTH_REJECTED inner={innerLength} total={expectedTotal}; NO_RETRY");
            if (pending.Count < expectedTotal) return;
            var wire = pending.GetRange(0, expectedTotal).ToArray();
            pending.RemoveRange(0, expectedTotal);
            var report = ValidateAndDecode(wire, observation.ElapsedMilliseconds, phase);
            reports.Add(report);
            if (reports.Count > FrozenPremodel008Protocol.MaxReports) throw new InvalidOperationException($"PREMODEL008_REPORT_BUDGET_EXHAUSTED count={reports.Count}; NO_RETRY");
            Console.WriteLine($"PREMODEL008_REPORT elapsed_ms={report.ElapsedMs} phase={report.Phase} inner=0x{report.InnerCommand:X2} payload={report.PayloadHex} wire={report.WireHex}");
        }
    }

    private static Report ValidateAndDecode(byte[] wire, long elapsedMs, string phase)
    {
        if (wire[0] != 0x01 || wire[^1] != 0x02) throw new InvalidOperationException("PREMODEL008_RESPONSE_BOUNDARY_REJECTED; NO_RETRY");
        var innerLength = wire[1] | (wire[2] << 8);
        if (wire.Length != innerLength + 4 || innerLength < 5) throw new InvalidOperationException($"PREMODEL008_RESPONSE_INNER_LENGTH_REJECTED value={innerLength}; NO_RETRY");
        var checksumIndex = 3 + innerLength - 2;
        ushort sum = 0;
        for (var i = 1; i < checksumIndex; i++) sum = unchecked((ushort)(sum + wire[i]));
        var observedChecksum = (ushort)(wire[checksumIndex] | (wire[checksumIndex + 1] << 8));
        if (sum != observedChecksum) throw new InvalidOperationException($"PREMODEL008_RESPONSE_CHECKSUM_REJECTED observed=0x{observedChecksum:X4} expected=0x{sum:X4}; NO_RETRY");
        if (wire[3] != 0x04 || wire[5] != 0x55) throw new InvalidOperationException($"PREMODEL008_RESPONSE_WRAPPER_REJECTED outer=0x{wire[3]:X2} tag=0x{wire[5]:X2}; NO_RETRY");
        var payloadLength = checksumIndex - 6;
        var payload = payloadLength == 0 ? Array.Empty<byte>() : wire.AsSpan(6, payloadLength).ToArray();
        return new Report(elapsedMs, phase, Convert.ToHexString(wire).ToLowerInvariant(), wire.Length, wire[3], wire[4], wire[5], Convert.ToHexString(payload).ToLowerInvariant(), observedChecksum);
    }

    private static void WaitForInitialWritable(IntPtr socketHandle, IntPtr eventHandle, Deadline deadline)
    {
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, deadline, "INITIAL_WRITE_WINDOW");
            if ((events.NetworkEvents & FdClose) != 0) throw new InvalidOperationException($"PREMODEL008_INITIAL_WRITE_WINDOW_CLOSED WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
            if ((events.NetworkEvents & FdWrite) == 0) continue;
            if (events.ErrorCodes[FdWriteBit] != 0) throw new InvalidOperationException($"PREMODEL008_INITIAL_WRITE_WINDOW_FAILED WSA={events.ErrorCodes[FdWriteBit]}; NO_RETRY");
            return;
        }
    }

    private static void SendSingleCall(IntPtr socketHandle, IntPtr eventHandle, byte[] bytes, string stage)
    {
        CheckNoCloseEvent(socketHandle, eventHandle, stage);
        var sent = send(socketHandle, bytes, bytes.Length, 0);
        if (sent != bytes.Length)
        {
            var error = sent < 0 ? WSAGetLastError() : 0;
            var suffix = error == WsaWouldBlock ? "WOULD_BLOCK" : "AMBIGUOUS";
            throw new InvalidOperationException($"PREMODEL008_{stage}_SEND_{suffix} bytes={sent}/{bytes.Length} WSA={error}; NO_RETRY");
        }
    }

    private static void CheckNoCloseEvent(IntPtr socketHandle, IntPtr eventHandle, string stage)
    {
        var wait = WSAWaitForMultipleEvents(1, [eventHandle], false, 0, false);
        if (wait == WsaWaitTimeout) return;
        if (wait == WsaWaitFailed) throw new InvalidOperationException($"PREMODEL008_{stage}_PRE_SEND_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if (wait != WsaWaitEvent0) throw new InvalidOperationException($"PREMODEL008_{stage}_PRE_SEND_WAIT_UNEXPECTED result={wait}; NO_RETRY");
        var events = WsaNetworkEvents.Create();
        if (WSAEnumNetworkEvents(socketHandle, eventHandle, ref events) == SocketError) throw new InvalidOperationException($"PREMODEL008_{stage}_PRE_SEND_ENUM_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if ((events.NetworkEvents & FdClose) != 0) throw new InvalidOperationException($"PREMODEL008_{stage}_CLOSED WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
    }

    private static void SelectEvents(IntPtr socketHandle, IntPtr eventHandle, int mask, string stage)
    {
        if (WSAEventSelect(socketHandle, eventHandle, mask) == SocketError) throw new InvalidOperationException($"PREMODEL008_{stage}_EVENT_SELECT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
    }

    private static void WaitForExactEvent(IntPtr socketHandle, IntPtr eventHandle, int eventMask, int errorIndex, Deadline deadline, string stage)
    {
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, deadline, stage);
            if ((events.NetworkEvents & eventMask) == 0) continue;
            var error = events.ErrorCodes[errorIndex];
            if (error != 0) throw new InvalidOperationException($"PREMODEL008_{stage}_FAILED WSA={error}; NO_RETRY");
            return;
        }
    }

    private static WsaNetworkEvents WaitForEvents(IntPtr socketHandle, IntPtr eventHandle, Deadline deadline, string stage)
    {
        var wait = WSAWaitForMultipleEvents(1, [eventHandle], false, (uint)deadline.RemainingMilliseconds(stage), false);
        if (wait == WsaWaitTimeout) throw new TimeoutException($"PREMODEL008_{stage}_TIMEOUT; NO_RETRY");
        if (wait == WsaWaitFailed) throw new InvalidOperationException($"PREMODEL008_{stage}_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if (wait != WsaWaitEvent0) throw new InvalidOperationException($"PREMODEL008_{stage}_WAIT_UNEXPECTED result={wait}; NO_RETRY");
        var events = WsaNetworkEvents.Create();
        if (WSAEnumNetworkEvents(socketHandle, eventHandle, ref events) == SocketError) throw new InvalidOperationException($"PREMODEL008_{stage}_ENUM_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        return events;
    }

    private sealed class Deadline(int budgetMs)
    {
        private readonly long _started = Stopwatch.GetTimestamp();
        private readonly double _ticksPerMillisecond = Stopwatch.Frequency / 1000.0;
        internal int RemainingMilliseconds(string stage)
        {
            var elapsed = (Stopwatch.GetTimestamp() - _started) / _ticksPerMillisecond;
            var remaining = budgetMs - (int)Math.Ceiling(elapsed);
            if (remaining <= 0) throw new TimeoutException($"PREMODEL008_{stage}_TIMEOUT budget_ms={budgetMs}; NO_RETRY");
            return remaining;
        }
    }
}
