using System.Diagnostics;
using System.Runtime.InteropServices;

internal static class WindowsRfcommVram8BTransport
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

    internal sealed record Result(int ConnectionsAttempted, int SendsCompleted, int CustomOverwriteSends, int BaselineValue, int PostValue, int RestoredValue, long ObservationMilliseconds, bool ConnectionSurvivedObservation);

    internal sealed class TransportStopException : Exception
    {
        internal int ConnectionsAttempted { get; }
        internal int SendsCompleted { get; }
        internal int CustomOverwriteSends { get; }
        internal TransportStopException(string message, int connectionsAttempted, int sendsCompleted, int customOverwriteSends, Exception inner)
            : base(message, inner)
        {
            ConnectionsAttempted = connectionsAttempted;
            SendsCompleted = sendsCompleted;
            CustomOverwriteSends = customOverwriteSends;
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
        var baseline = -1;
        var post = -1;
        var restored = -1;
        try
        {
            for (var i = 0; i < 512; i++) Marshal.WriteByte(wsaData, i, 0);
            var startup = WSAStartup(0x0202, wsaData);
            if (startup != 0) throw new InvalidOperationException($"VRAM8B_WSASTARTUP_FAILED WSA={startup}; NO_RETRY");
            started = true;
            var layoutSize = Marshal.SizeOf<SockAddrBth>();
            if (layoutSize != 30) throw new InvalidOperationException($"VRAM8B_SOCKADDR_BTH_LAYOUT_REJECTED SIZE={layoutSize}");
            socketHandle = socket(AfBth, SockStream, BthProtoRfcomm);
            if (socketHandle == InvalidSocket) throw new InvalidOperationException($"VRAM8B_SOCKET_CREATE_FAILED WSA={WSAGetLastError()}; NO_RETRY");
            eventHandle = WSACreateEvent();
            if (eventHandle == InvalidEvent) throw new InvalidOperationException($"VRAM8B_EVENT_CREATE_FAILED WSA={WSAGetLastError()}; NO_RETRY");

            SelectEvents(socketHandle, eventHandle, FdConnect, "CONNECT");
            var remote = new SockAddrBth
            {
                AddressFamily = (ushort)AfBth,
                BluetoothAddress = FrozenVram8BProtocol.TargetBluetoothAddress,
                ServiceClassId = Guid.Empty,
                Port = FrozenVram8BProtocol.TargetRfcommChannel,
            };
            var connectDeadline = new Deadline(FrozenVram8BProtocol.ConnectBudgetMs);
            connectionsAttempted = 1;
            var cr = connect(socketHandle, ref remote, layoutSize);
            if (cr == SocketError)
            {
                var error = WSAGetLastError();
                if (error != WsaWouldBlock) throw new InvalidOperationException($"VRAM8B_CONNECT_FAILED WSA={error}; NO_RETRY");
                WaitForExactEvent(socketHandle, eventHandle, FdConnect, FdConnectBit, connectDeadline, "CONNECT");
            }
            if (total.ElapsedMilliseconds > FrozenVram8BProtocol.ConnectBudgetMs)
                throw new TimeoutException("VRAM8B_CONNECT_BUDGET_EXCEEDED; NO_RETRY");

            SelectEvents(socketHandle, eventHandle, FdWrite | FdClose, "INITIAL_WRITE_WINDOW");
            WaitForInitialWritable(socketHandle, eventHandle, new Deadline(5_000));

            for (var i = 0; i < FrozenVram8BProtocol.Fixtures.Length; i++)
            {
                var f = FrozenVram8BProtocol.Fixtures[i];
                if (f.Key == "post_get")
                    ObserveCloseOnly(socketHandle, eventHandle, FrozenVram8BProtocol.ObservationHoldMs);

                SelectEvents(socketHandle, eventHandle, FdClose, $"{f.Key}_PRE_SEND");
                SendSingleCall(socketHandle, eventHandle, fixtures[i], f.Key.ToUpperInvariant());
                sends++;
                if (f.IsCustomOverwrite) customOverwriteSends++;

                switch (f.Key)
                {
                    case "baseline_set":
                    case "restore_set":
                    {
                        var response = ReceiveOneWrapped(socketHandle, eventHandle, new Deadline(FrozenVram8BProtocol.ResponseBudgetMs), f.Key.ToUpperInvariant());
                        FrozenVram8BProtocol.ValidateWrappedResponse(response, 0xB2, 0);
                        break;
                    }
                    case "baseline_get":
                    case "post_get":
                    case "restore_get":
                    {
                        var response = ReceiveOneWrapped(socketHandle, eventHandle, new Deadline(FrozenVram8BProtocol.ResponseBudgetMs), f.Key.ToUpperInvariant());
                        var payload = FrozenVram8BProtocol.ValidateWrappedResponse(response, 0xB3, (byte)f.ExpectedB3Value!.Value);
                        var value = payload[0];
                        if (f.Key == "baseline_get") baseline = value;
                        else if (f.Key == "post_get") post = value;
                        else restored = value;
                        break;
                    }
                    case "prime":
                    {
                        var response = ReceiveOneWrapped(socketHandle, eventHandle, new Deadline(FrozenVram8BProtocol.ResponseBudgetMs), "PRIME_0X6E");
                        FrozenVram8BProtocol.ValidateWrappedResponse(response, 0x6E, null);
                        break;
                    }
                    case "voicetip":
                        TryDrainOptionalMatching(socketHandle, eventHandle, 0xA5, "VOICETIP_0XA5");
                        break;
                    case "overwrite":
                        TryDrainOptionalMatching(socketHandle, eventHandle, 0x6C, "OVERWRITE_0X6C");
                        break;
                    default:
                        throw new InvalidOperationException($"VRAM8B_UNEXPECTED_FIXTURE_KEY {f.Key}; NO_RETRY");
                }

                if (i + 1 < FrozenVram8BProtocol.Fixtures.Length && f.Key != "overwrite")
                    Thread.Sleep(FrozenVram8BProtocol.InterPacketDelayMs);
                if (total.ElapsedMilliseconds > FrozenVram8BProtocol.TotalBudgetMs)
                    throw new TimeoutException("VRAM8B_TOTAL_BUDGET_EXCEEDED; NO_RETRY");
            }

            if (sends != FrozenVram8BProtocol.ExactApplicationSends || customOverwriteSends != FrozenVram8BProtocol.MaxCustomOverwriteSends)
                throw new InvalidOperationException($"VRAM8B_SEND_COUNT_DRIFT sends={sends} custom={customOverwriteSends}; NO_RETRY");
            if (baseline != 0 || post != 1 || restored != 0)
                throw new InvalidOperationException($"VRAM8B_TYPED_DISCRIMINATOR_REJECTED {baseline}->{post}->{restored}; NO_RETRY");

            return new Result(connectionsAttempted, sends, customOverwriteSends, baseline, post, restored, FrozenVram8BProtocol.ObservationHoldMs, true);
        }
        catch (Exception ex) when (ex is not TransportStopException)
        {
            throw new TransportStopException(ex.Message, connectionsAttempted, sends, customOverwriteSends, ex);
        }
        finally
        {
            if (socketHandle != InvalidSocket) closesocket(socketHandle);
            if (eventHandle != InvalidEvent) WSACloseEvent(eventHandle);
            if (started) WSACleanup();
            Marshal.FreeHGlobal(wsaData);
        }
    }

    private static byte[] ReceiveOneWrapped(IntPtr socketHandle, IntPtr eventHandle, Deadline deadline, string stage)
    {
        const int maxWire = 64;
        SelectEvents(socketHandle, eventHandle, FdRead | FdClose, stage + "_RECV");
        var received = new List<byte>(maxWire);
        var expectedTotal = -1;
        var chunk = new byte[maxWire];
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, deadline, stage + "_RECV");
            if ((events.NetworkEvents & FdClose) != 0)
                throw new InvalidOperationException($"VRAM8B_{stage}_RECV_CLOSED WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
            if ((events.NetworkEvents & FdRead) == 0) continue;
            if (events.ErrorCodes[FdReadBit] != 0)
                throw new InvalidOperationException($"VRAM8B_{stage}_RECV_EVENT_FAILED WSA={events.ErrorCodes[FdReadBit]}; NO_RETRY");
            var remaining = maxWire - received.Count;
            if (remaining <= 0) throw new InvalidOperationException($"VRAM8B_{stage}_RECV_OVERSIZE; NO_RETRY");
            var got = recv(socketHandle, chunk, remaining, 0);
            if (got == 0) throw new InvalidOperationException($"VRAM8B_{stage}_RECV_DISCONNECTED; NO_RETRY");
            if (got < 0)
            {
                var error = WSAGetLastError();
                if (error == WsaWouldBlock) continue;
                throw new InvalidOperationException($"VRAM8B_{stage}_RECV_FAILED WSA={error}; NO_RETRY");
            }
            for (var i = 0; i < got; i++) received.Add(chunk[i]);
            if (received.Count >= 1 && received[0] != 0x01)
                throw new InvalidOperationException($"VRAM8B_{stage}_FRAME_START_REJECTED; NO_RETRY");
            if (received.Count >= 3 && expectedTotal < 0)
            {
                var inner = received[1] | (received[2] << 8);
                expectedTotal = inner + 4;
                if (expectedTotal < 9 || expectedTotal > maxWire)
                    throw new InvalidOperationException($"VRAM8B_{stage}_FRAME_LENGTH_REJECTED INNER={inner}; NO_RETRY");
            }
            if (expectedTotal > 0 && received.Count == expectedTotal) return received.ToArray();
            if (expectedTotal > 0 && received.Count > expectedTotal)
                throw new InvalidOperationException($"VRAM8B_{stage}_FRAME_TRAILING_BYTES; NO_RETRY");
        }
    }

    private static bool TryDrainOptionalMatching(IntPtr socketHandle, IntPtr eventHandle, byte expectedCommand, string stage)
    {
        try
        {
            var response = ReceiveOneWrapped(socketHandle, eventHandle, new Deadline(150), stage + "_OPTIONAL");
            FrozenVram8BProtocol.ValidateWrappedResponse(response, expectedCommand, null);
            return true;
        }
        catch (TimeoutException)
        {
            return false;
        }
    }

    private static void ObserveCloseOnly(IntPtr socketHandle, IntPtr eventHandle, int holdMs)
    {
        SelectEvents(socketHandle, eventHandle, FdClose, "OBSERVE_CLOSE_ONLY");
        var wait = WSAWaitForMultipleEvents(1, [eventHandle], false, (uint)holdMs, false);
        if (wait == WsaWaitFailed) throw new InvalidOperationException($"VRAM8B_OBSERVE_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if (wait == WsaWaitTimeout) return;
        if (wait != WsaWaitEvent0) throw new InvalidOperationException($"VRAM8B_OBSERVE_WAIT_UNEXPECTED RESULT={wait}; NO_RETRY");
        var events = WsaNetworkEvents.Create();
        if (WSAEnumNetworkEvents(socketHandle, eventHandle, ref events) == SocketError)
            throw new InvalidOperationException($"VRAM8B_OBSERVE_ENUM_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if ((events.NetworkEvents & FdClose) != 0)
            throw new InvalidOperationException($"VRAM8B_DISCONNECTED_DURING_OBSERVATION WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
        throw new InvalidOperationException($"VRAM8B_UNEXPECTED_OBSERVATION_EVENT MASK={events.NetworkEvents}; NO_RETRY");
    }

    private static void WaitForInitialWritable(IntPtr socketHandle, IntPtr eventHandle, Deadline deadline)
    {
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, deadline, "INITIAL_WRITE_WINDOW");
            if ((events.NetworkEvents & FdClose) != 0)
                throw new InvalidOperationException($"VRAM8B_INITIAL_WRITE_WINDOW_CLOSED WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
            if ((events.NetworkEvents & FdWrite) == 0) continue;
            if (events.ErrorCodes[FdWriteBit] != 0)
                throw new InvalidOperationException($"VRAM8B_INITIAL_WRITE_WINDOW_FAILED WSA={events.ErrorCodes[FdWriteBit]}; NO_RETRY");
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
            throw new InvalidOperationException($"VRAM8B_{stage}_SEND_{suffix} BYTES={sent}/{bytes.Length} WSA={error}; NO_RETRY");
        }
    }

    private static void CheckNoCloseEvent(IntPtr socketHandle, IntPtr eventHandle, string stage)
    {
        var wait = WSAWaitForMultipleEvents(1, [eventHandle], false, 0, false);
        if (wait == WsaWaitTimeout) return;
        if (wait == WsaWaitFailed) throw new InvalidOperationException($"VRAM8B_{stage}_PRE_SEND_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if (wait != WsaWaitEvent0) throw new InvalidOperationException($"VRAM8B_{stage}_PRE_SEND_WAIT_UNEXPECTED RESULT={wait}; NO_RETRY");
        var events = WsaNetworkEvents.Create();
        if (WSAEnumNetworkEvents(socketHandle, eventHandle, ref events) == SocketError)
            throw new InvalidOperationException($"VRAM8B_{stage}_PRE_SEND_ENUM_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if ((events.NetworkEvents & FdClose) != 0)
            throw new InvalidOperationException($"VRAM8B_{stage}_CLOSED WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
    }

    private static void SelectEvents(IntPtr socketHandle, IntPtr eventHandle, int mask, string stage)
    {
        if (WSAEventSelect(socketHandle, eventHandle, mask) == SocketError)
            throw new InvalidOperationException($"VRAM8B_{stage}_EVENT_SELECT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
    }

    private static void WaitForExactEvent(IntPtr socketHandle, IntPtr eventHandle, int eventMask, int errorIndex, Deadline deadline, string stage)
    {
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, deadline, stage);
            if ((events.NetworkEvents & eventMask) == 0) continue;
            var error = events.ErrorCodes[errorIndex];
            if (error != 0) throw new InvalidOperationException($"VRAM8B_{stage}_FAILED WSA={error}; NO_RETRY");
            return;
        }
    }

    private static WsaNetworkEvents WaitForEvents(IntPtr socketHandle, IntPtr eventHandle, Deadline deadline, string stage)
    {
        var wait = WSAWaitForMultipleEvents(1, [eventHandle], false, (uint)deadline.RemainingMilliseconds(stage), false);
        if (wait == WsaWaitTimeout) throw new TimeoutException($"VRAM8B_{stage}_TIMEOUT; NO_RETRY");
        if (wait == WsaWaitFailed) throw new InvalidOperationException($"VRAM8B_{stage}_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if (wait != WsaWaitEvent0) throw new InvalidOperationException($"VRAM8B_{stage}_WAIT_UNEXPECTED RESULT={wait}; NO_RETRY");
        var events = WsaNetworkEvents.Create();
        if (WSAEnumNetworkEvents(socketHandle, eventHandle, ref events) == SocketError)
            throw new InvalidOperationException($"VRAM8B_{stage}_ENUM_FAILED WSA={WSAGetLastError()}; NO_RETRY");
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
            if (remaining <= 0) throw new TimeoutException($"VRAM8B_{stage}_TIMEOUT BUDGET_MS={budgetMs}; NO_RETRY");
            return remaining;
        }
    }
}
