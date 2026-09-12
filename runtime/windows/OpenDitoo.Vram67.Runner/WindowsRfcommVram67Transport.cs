using System.Diagnostics;
using System.Runtime.InteropServices;

internal static class WindowsRfcommVram67Transport
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
    private const int FdWrite = 1 << 1;
    private const int FdConnect = 1 << 4;
    private const int FdClose = 1 << 5;
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
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = FdMaxEvents)]
        public int[] ErrorCodes;
        public static WsaNetworkEvents Create() => new() { ErrorCodes = new int[FdMaxEvents] };
    }

    [DllImport("Ws2_32.dll")] private static extern int WSAStartup(ushort versionRequested, IntPtr wsaData);
    [DllImport("Ws2_32.dll")] private static extern int WSACleanup();
    [DllImport("Ws2_32.dll")] private static extern IntPtr socket(int addressFamily, int socketType, int protocol);
    [DllImport("Ws2_32.dll")] private static extern int closesocket(IntPtr socketHandle);
    [DllImport("Ws2_32.dll")] private static extern int connect(IntPtr socketHandle, ref SockAddrBth name, int nameLength);
    [DllImport("Ws2_32.dll")] private static extern int send(IntPtr socketHandle, byte[] buffer, int length, int flags);
    [DllImport("Ws2_32.dll")] private static extern int WSAGetLastError();
    [DllImport("Ws2_32.dll")] private static extern IntPtr WSACreateEvent();
    [DllImport("Ws2_32.dll")] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool WSACloseEvent(IntPtr eventHandle);
    [DllImport("Ws2_32.dll")] private static extern int WSAEventSelect(IntPtr socketHandle, IntPtr eventHandle, int networkEvents);
    [DllImport("Ws2_32.dll")] private static extern int WSAEnumNetworkEvents(IntPtr socketHandle, IntPtr eventHandle, ref WsaNetworkEvents networkEvents);
    [DllImport("Ws2_32.dll")] private static extern uint WSAWaitForMultipleEvents(uint eventCount, [In] IntPtr[] eventHandles, [MarshalAs(UnmanagedType.Bool)] bool waitAll, uint timeoutMilliseconds, [MarshalAs(UnmanagedType.Bool)] bool alertable);

    internal sealed record Result(int ConnectionsAttempted, int SendsCompleted, long ObservationMilliseconds, bool ConnectionSurvivedObservation);

    internal static Result RunExactlyOnce()
    {
        FrozenVram67Protocol.VerifyFrozenConstants();
        var total = Stopwatch.StartNew();
        var wsaData = Marshal.AllocHGlobal(512);
        var socketHandle = InvalidSocket;
        var eventHandle = InvalidEvent;
        var started = false;
        var sends = 0;
        try
        {
            for (var i = 0; i < 512; i++) Marshal.WriteByte(wsaData, i, 0);
            var startup = WSAStartup(0x0202, wsaData);
            if (startup != 0) throw new InvalidOperationException($"VRAM67_WSASTARTUP_FAILED WSA={startup}; NO_RETRY");
            started = true;
            var layoutSize = Marshal.SizeOf<SockAddrBth>();
            if (layoutSize != 30) throw new InvalidOperationException($"VRAM67_SOCKADDR_BTH_LAYOUT_REJECTED SIZE={layoutSize}");
            socketHandle = socket(AfBth, SockStream, BthProtoRfcomm);
            if (socketHandle == InvalidSocket) throw new InvalidOperationException($"VRAM67_SOCKET_CREATE_FAILED WSA={WSAGetLastError()}; NO_RETRY");
            eventHandle = WSACreateEvent();
            if (eventHandle == InvalidEvent) throw new InvalidOperationException($"VRAM67_EVENT_CREATE_FAILED WSA={WSAGetLastError()}; NO_RETRY");

            SelectEvents(socketHandle, eventHandle, FdConnect, "CONNECT");
            var remote = new SockAddrBth
            {
                AddressFamily = (ushort)AfBth,
                BluetoothAddress = FrozenVram67Protocol.TargetBluetoothAddress,
                ServiceClassId = Guid.Empty,
                Port = FrozenVram67Protocol.TargetRfcommChannel,
            };
            var connectDeadline = new Deadline(FrozenVram67Protocol.ConnectBudgetMs);
            var cr = connect(socketHandle, ref remote, layoutSize); // exactly one connect call
            if (cr == SocketError)
            {
                var error = WSAGetLastError();
                if (error != WsaWouldBlock) throw new InvalidOperationException($"VRAM67_CONNECT_FAILED WSA={error}; NO_RETRY");
                WaitForExactEvent(socketHandle, eventHandle, FdConnect, FdConnectBit, connectDeadline, "CONNECT");
            }
            if (total.ElapsedMilliseconds > FrozenVram67Protocol.ConnectBudgetMs)
                throw new TimeoutException("VRAM67_CONNECT_BUDGET_EXCEEDED; NO_RETRY");

            SendExactlyOnce(socketHandle, eventHandle, FrozenVram67Protocol.BuildPrime(), "PRIME_0X6E"); sends++;
            Thread.Sleep(FrozenVram67Protocol.InterPacketDelayMs);
            SendExactlyOnce(socketHandle, eventHandle, FrozenVram67Protocol.BuildVoiceTip(), "VOICETIP_0XA5"); sends++;
            Thread.Sleep(FrozenVram67Protocol.InterPacketDelayMs);
            SendExactlyOnce(socketHandle, eventHandle, FrozenVram67Protocol.BuildOverwrite(), "OVERWRITE_0X6C"); sends++;

            var observed = Stopwatch.StartNew();
            SelectEvents(socketHandle, eventHandle, FdClose, "OBSERVE_CLOSE_ONLY");
            var wait = WSAWaitForMultipleEvents(1, [eventHandle], false, FrozenVram67Protocol.ObservationHoldMs, false);
            if (wait == WsaWaitFailed)
                throw new InvalidOperationException($"VRAM67_OBSERVE_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
            if (wait != WsaWaitTimeout)
            {
                if (wait != WsaWaitEvent0) throw new InvalidOperationException($"VRAM67_OBSERVE_WAIT_UNEXPECTED RESULT={wait}; NO_RETRY");
                var events = WsaNetworkEvents.Create();
                if (WSAEnumNetworkEvents(socketHandle, eventHandle, ref events) == SocketError)
                    throw new InvalidOperationException($"VRAM67_OBSERVE_ENUM_FAILED WSA={WSAGetLastError()}; NO_RETRY");
                if ((events.NetworkEvents & FdClose) != 0)
                    throw new InvalidOperationException($"VRAM67_DISCONNECTED_DURING_OBSERVATION WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
                throw new InvalidOperationException($"VRAM67_UNEXPECTED_OBSERVATION_EVENT MASK={events.NetworkEvents}; NO_RETRY");
            }
            if (total.ElapsedMilliseconds > FrozenVram67Protocol.TotalBudgetMs)
                throw new TimeoutException("VRAM67_TOTAL_BUDGET_EXCEEDED; NO_RETRY");
            return new Result(1, sends, observed.ElapsedMilliseconds, true);
        }
        finally
        {
            if (socketHandle != InvalidSocket) closesocket(socketHandle);
            if (eventHandle != InvalidEvent) WSACloseEvent(eventHandle);
            if (started) WSACleanup();
            Marshal.FreeHGlobal(wsaData);
        }
    }

    private static void SendExactlyOnce(IntPtr socketHandle, IntPtr eventHandle, byte[] bytes, string stage)
    {
        SelectEvents(socketHandle, eventHandle, FdWrite | FdClose, stage);
        var deadline = new Deadline(5_000);
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, deadline, stage);
            if ((events.NetworkEvents & FdClose) != 0)
                throw new InvalidOperationException($"VRAM67_{stage}_CLOSED WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
            if ((events.NetworkEvents & FdWrite) == 0) continue;
            if (events.ErrorCodes[FdWriteBit] != 0)
                throw new InvalidOperationException($"VRAM67_{stage}_WRITE_READY_FAILED WSA={events.ErrorCodes[FdWriteBit]}; NO_RETRY");
            break;
        }
        var sent = send(socketHandle, bytes, bytes.Length, 0); // exactly one send call for this application frame
        if (sent != bytes.Length)
        {
            var error = sent < 0 ? WSAGetLastError() : 0;
            throw new InvalidOperationException($"VRAM67_{stage}_SEND_AMBIGUOUS BYTES={sent}/{bytes.Length} WSA={error}; NO_RETRY");
        }
    }

    private static void SelectEvents(IntPtr socketHandle, IntPtr eventHandle, int mask, string stage)
    {
        if (WSAEventSelect(socketHandle, eventHandle, mask) == SocketError)
            throw new InvalidOperationException($"VRAM67_{stage}_EVENT_SELECT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
    }

    private static void WaitForExactEvent(IntPtr socketHandle, IntPtr eventHandle, int eventMask, int errorIndex, Deadline deadline, string stage)
    {
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, deadline, stage);
            if ((events.NetworkEvents & eventMask) == 0) continue;
            var error = events.ErrorCodes[errorIndex];
            if (error != 0) throw new InvalidOperationException($"VRAM67_{stage}_FAILED WSA={error}; NO_RETRY");
            return;
        }
    }

    private static WsaNetworkEvents WaitForEvents(IntPtr socketHandle, IntPtr eventHandle, Deadline deadline, string stage)
    {
        var wait = WSAWaitForMultipleEvents(1, [eventHandle], false, (uint)deadline.RemainingMilliseconds(stage), false);
        if (wait == WsaWaitTimeout) throw new TimeoutException($"VRAM67_{stage}_TIMEOUT; NO_RETRY");
        if (wait == WsaWaitFailed) throw new InvalidOperationException($"VRAM67_{stage}_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if (wait != WsaWaitEvent0) throw new InvalidOperationException($"VRAM67_{stage}_WAIT_UNEXPECTED RESULT={wait}; NO_RETRY");
        var events = WsaNetworkEvents.Create();
        if (WSAEnumNetworkEvents(socketHandle, eventHandle, ref events) == SocketError)
            throw new InvalidOperationException($"VRAM67_{stage}_ENUM_FAILED WSA={WSAGetLastError()}; NO_RETRY");
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
            if (remaining <= 0) throw new TimeoutException($"VRAM67_{stage}_TIMEOUT BUDGET_MS={budgetMs}; NO_RETRY");
            return remaining;
        }
    }
}
