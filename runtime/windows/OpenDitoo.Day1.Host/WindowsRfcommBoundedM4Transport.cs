using System.Diagnostics;
using System.Runtime.InteropServices;

namespace OpenDitoo.Day1.Host.Internal;

// Offline-prepared transport for exactly one frozen M4 file-version exchange.
// IMPORTANT: Program.cs does not reference this type. Merely compiling the Host
// therefore does not create a Bluetooth/API/transmission surface.
internal static class WindowsRfcommBoundedM4Transport
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

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = FdMaxEvents)]
        public int[] ErrorCodes;

        public static WsaNetworkEvents Create() => new()
        {
            ErrorCodes = new int[FdMaxEvents],
        };
    }

    [DllImport("Ws2_32.dll")]
    private static extern int WSAStartup(ushort versionRequested, IntPtr wsaData);

    [DllImport("Ws2_32.dll")]
    private static extern int WSACleanup();

    [DllImport("Ws2_32.dll")]
    private static extern IntPtr socket(int addressFamily, int socketType, int protocol);

    [DllImport("Ws2_32.dll")]
    private static extern int closesocket(IntPtr socketHandle);

    [DllImport("Ws2_32.dll")]
    private static extern int connect(IntPtr socketHandle, ref SockAddrBth name, int nameLength);

    [DllImport("Ws2_32.dll")]
    private static extern int send(IntPtr socketHandle, byte[] buffer, int length, int flags);

    [DllImport("Ws2_32.dll")]
    private static extern int recv(IntPtr socketHandle, byte[] buffer, int length, int flags);

    [DllImport("Ws2_32.dll")]
    private static extern int WSAGetLastError();

    [DllImport("Ws2_32.dll")]
    private static extern IntPtr WSACreateEvent();

    [DllImport("Ws2_32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool WSACloseEvent(IntPtr eventHandle);

    [DllImport("Ws2_32.dll")]
    private static extern int WSAEventSelect(IntPtr socketHandle, IntPtr eventHandle, int networkEvents);

    [DllImport("Ws2_32.dll")]
    private static extern int WSAEnumNetworkEvents(
        IntPtr socketHandle,
        IntPtr eventHandle,
        ref WsaNetworkEvents networkEvents);

    [DllImport("Ws2_32.dll")]
    private static extern uint WSAWaitForMultipleEvents(
        uint eventCount,
        [In] IntPtr[] eventHandles,
        [MarshalAs(UnmanagedType.Bool)] bool waitAll,
        uint timeoutMilliseconds,
        [MarshalAs(UnmanagedType.Bool)] bool alertable);

    internal static int ExchangeFrozenFileVersionOnce()
    {
        DitooM4FileVersionProtocol.VerifyFrozenConstants();

        var total = Stopwatch.StartNew();
        var wsaData = Marshal.AllocHGlobal(512);
        var socketHandle = InvalidSocket;
        var eventHandle = InvalidEvent;
        var started = false;

        try
        {
            for (var i = 0; i < 512; i++)
                Marshal.WriteByte(wsaData, i, 0);

            var startup = WSAStartup(0x0202, wsaData);
            if (startup != 0)
                throw new InvalidOperationException($"M4_WSASTARTUP_FAILED WSA={startup}");
            started = true;

            var layoutSize = Marshal.SizeOf<SockAddrBth>();
            if (layoutSize != 30)
                throw new InvalidOperationException($"M4_SOCKADDR_BTH_LAYOUT_REJECTED SIZE={layoutSize}");

            socketHandle = socket(AfBth, SockStream, BthProtoRfcomm);
            if (socketHandle == InvalidSocket)
                throw new InvalidOperationException($"M4_SOCKET_CREATE_FAILED WSA={WSAGetLastError()}");

            eventHandle = WSACreateEvent();
            if (eventHandle == InvalidEvent)
                throw new InvalidOperationException($"M4_WSA_EVENT_CREATE_FAILED WSA={WSAGetLastError()}");

            SelectEvents(socketHandle, eventHandle, FdConnect, "M4_CONNECT");
            var remote = new SockAddrBth
            {
                AddressFamily = (ushort)AfBth,
                BluetoothAddress = DitooM4FileVersionProtocol.TargetBluetoothAddress,
                ServiceClassId = Guid.Empty,
                Port = DitooM4FileVersionProtocol.TargetRfcommChannel,
            };

            var connectDeadline = new Deadline(DitooM4FileVersionProtocol.ConnectBudgetMs);
            var connectResult = connect(socketHandle, ref remote, layoutSize); // exactly one connect call
            if (connectResult == SocketError)
            {
                var error = WSAGetLastError();
                if (error != WsaWouldBlock)
                    throw new InvalidOperationException($"M4_RFCOMM_CONNECT_FAILED WSA={error}");
                WaitForExactEvent(socketHandle, eventHandle, FdConnect, FdConnectBit, connectDeadline, "M4_RFCOMM_CONNECT");
            }

            if (total.ElapsedMilliseconds > DitooM4FileVersionProtocol.ConnectBudgetMs)
                throw new TimeoutException("M4_CONNECT_TOTAL_BUDGET_EXCEEDED");

            // WSAEventSelect keeps the socket nonblocking. Await write readiness,
            // then make exactly one application send. A WOULD_BLOCK result after
            // readiness is ambiguous and fails closed; there is no second send.
            var responseDeadline = new Deadline(DitooM4FileVersionProtocol.ResponseBudgetMs);
            SelectEvents(socketHandle, eventHandle, FdWrite | FdClose, "M4_SEND_READY");
            WaitForWriteOrClose(socketHandle, eventHandle, responseDeadline);

            var request = (byte[])DitooM4FileVersionProtocol.Request.Clone();
            var sent = send(socketHandle, request, request.Length, 0); // exactly one application send call
            if (sent != request.Length)
            {
                var error = sent < 0 ? WSAGetLastError() : 0;
                throw new InvalidOperationException($"M4_APPLICATION_SEND_AMBIGUOUS BYTES={sent} WSA={error}; NO_RETRY");
            }

            SelectEvents(socketHandle, eventHandle, FdRead | FdClose, "M4_RECEIVE");
            var received = new List<byte>(DitooM4FileVersionProtocol.MaxResponseWireBytes);
            var expectedTotal = -1;
            var chunk = new byte[DitooM4FileVersionProtocol.MaxResponseWireBytes];

            while (true)
            {
                var events = WaitForEvents(socketHandle, eventHandle, responseDeadline, "M4_APPLICATION_RECV");
                if ((events.NetworkEvents & FdClose) != 0)
                {
                    var closeError = events.ErrorCodes[FdCloseBit];
                    throw new InvalidOperationException($"M4_APPLICATION_RECV_CLOSED WSA={closeError}; NO_RETRY");
                }
                if ((events.NetworkEvents & FdRead) == 0)
                    continue;

                var readError = events.ErrorCodes[FdReadBit];
                if (readError != 0)
                    throw new InvalidOperationException($"M4_APPLICATION_RECV_EVENT_FAILED WSA={readError}; NO_RETRY");

                var remainingCapacity = DitooM4FileVersionProtocol.MaxResponseWireBytes - received.Count;
                if (remainingCapacity <= 0)
                    throw new InvalidOperationException("M4_APPLICATION_RECV_OVERSIZE; NO_RETRY");
                var got = recv(socketHandle, chunk, remainingCapacity, 0);
                if (got == 0)
                    throw new InvalidOperationException("M4_APPLICATION_RECV_DISCONNECTED_BEFORE_COMPLETE_FRAME; NO_RETRY");
                if (got < 0)
                {
                    var error = WSAGetLastError();
                    if (error == WsaWouldBlock)
                        continue;
                    throw new InvalidOperationException($"M4_APPLICATION_RECV_FAILED WSA={error}; NO_RETRY");
                }

                for (var i = 0; i < got; i++)
                    received.Add(chunk[i]);

                if (received.Count >= 1 && received[0] != 0x01)
                    throw new InvalidOperationException("M4_APPLICATION_FRAME_MALFORMED_START; NO_RETRY");
                if (received.Count >= 3 && expectedTotal < 0)
                {
                    var inner = received[1] | (received[2] << 8);
                    if (inner != 9)
                        throw new InvalidOperationException($"M4_APPLICATION_FRAME_INNER_LENGTH_REJECTED={inner}; NO_RETRY");
                    expectedTotal = inner + 4;
                    if (expectedTotal != DitooM4FileVersionProtocol.MaxResponseWireBytes)
                        throw new InvalidOperationException($"M4_APPLICATION_FRAME_TOTAL_LENGTH_REJECTED={expectedTotal}; NO_RETRY");
                }
                if (expectedTotal > 0 && received.Count == expectedTotal)
                    break;
                if (expectedTotal > 0 && received.Count > expectedTotal)
                    throw new InvalidOperationException("M4_APPLICATION_FRAME_TRAILING_BYTES; NO_RETRY");
            }

            if (total.ElapsedMilliseconds > DitooM4FileVersionProtocol.TotalBudgetMs)
                throw new TimeoutException("M4_TOTAL_BUDGET_EXCEEDED; NO_RETRY");

            return DitooM4FileVersionProtocol.ValidateAndDecodeVersion(received.ToArray());
        }
        finally
        {
            if (socketHandle != InvalidSocket)
                closesocket(socketHandle);
            if (eventHandle != InvalidEvent)
                WSACloseEvent(eventHandle);
            if (started)
                WSACleanup();
            Marshal.FreeHGlobal(wsaData);
        }
    }

    private static void SelectEvents(IntPtr socketHandle, IntPtr eventHandle, int mask, string stage)
    {
        if (WSAEventSelect(socketHandle, eventHandle, mask) == SocketError)
            throw new InvalidOperationException($"{stage}_EVENT_SELECT_FAILED WSA={WSAGetLastError()}");
    }

    private static void WaitForWriteOrClose(IntPtr socketHandle, IntPtr eventHandle, Deadline deadline)
    {
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, deadline, "M4_APPLICATION_SEND_READY");
            if ((events.NetworkEvents & FdClose) != 0)
            {
                var closeError = events.ErrorCodes[FdCloseBit];
                throw new InvalidOperationException($"M4_APPLICATION_SEND_CLOSED WSA={closeError}; NO_RETRY");
            }
            if ((events.NetworkEvents & FdWrite) == 0)
                continue;
            var writeError = events.ErrorCodes[FdWriteBit];
            if (writeError != 0)
                throw new InvalidOperationException($"M4_APPLICATION_SEND_READY_FAILED WSA={writeError}; NO_RETRY");
            return;
        }
    }

    private static void WaitForExactEvent(
        IntPtr socketHandle,
        IntPtr eventHandle,
        int eventMask,
        int errorIndex,
        Deadline deadline,
        string stage)
    {
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, deadline, stage);
            if ((events.NetworkEvents & eventMask) == 0)
                continue;
            var error = events.ErrorCodes[errorIndex];
            if (error != 0)
                throw new InvalidOperationException($"{stage}_FAILED WSA={error}");
            return;
        }
    }

    private static WsaNetworkEvents WaitForEvents(
        IntPtr socketHandle,
        IntPtr eventHandle,
        Deadline deadline,
        string stage)
    {
        var wait = WSAWaitForMultipleEvents(
            1,
            new[] { eventHandle },
            waitAll: false,
            timeoutMilliseconds: (uint)deadline.RemainingMilliseconds(stage),
            alertable: false);
        if (wait == WsaWaitTimeout)
            throw new TimeoutException($"{stage}_TIMEOUT; NO_RETRY");
        if (wait == WsaWaitFailed)
            throw new InvalidOperationException($"{stage}_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if (wait != WsaWaitEvent0)
            throw new InvalidOperationException($"{stage}_WAIT_UNEXPECTED RESULT={wait}; NO_RETRY");

        var events = WsaNetworkEvents.Create();
        if (WSAEnumNetworkEvents(socketHandle, eventHandle, ref events) == SocketError)
            throw new InvalidOperationException($"{stage}_ENUM_EVENTS_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        return events;
    }

    private sealed class Deadline
    {
        private readonly long _started = Stopwatch.GetTimestamp();
        private readonly double _ticksPerMillisecond = Stopwatch.Frequency / 1000.0;

        internal Deadline(int budgetMs)
        {
            BudgetMs = budgetMs;
        }

        internal int BudgetMs { get; }

        internal int RemainingMilliseconds(string stage)
        {
            var elapsedMs = (Stopwatch.GetTimestamp() - _started) / _ticksPerMillisecond;
            var remaining = BudgetMs - (int)Math.Ceiling(elapsedMs);
            if (remaining <= 0)
                throw new TimeoutException($"{stage}_TIMEOUT BUDGET_MS={BudgetMs}; NO_RETRY");
            return remaining;
        }
    }
}
