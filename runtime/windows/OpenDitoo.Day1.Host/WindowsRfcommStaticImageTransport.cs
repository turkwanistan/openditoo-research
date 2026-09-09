using System.Diagnostics;
using System.Runtime.InteropServices;

sealed class PairingRequiredException(string message) : Exception(message);

static class PairedDitooTargetGuard
{
    [StructLayout(LayoutKind.Sequential)]
    private struct BluetoothDeviceSearchParams
    {
        public uint dwSize;
        [MarshalAs(UnmanagedType.Bool)] public bool fReturnAuthenticated;
        [MarshalAs(UnmanagedType.Bool)] public bool fReturnRemembered;
        [MarshalAs(UnmanagedType.Bool)] public bool fReturnUnknown;
        [MarshalAs(UnmanagedType.Bool)] public bool fReturnConnected;
        [MarshalAs(UnmanagedType.Bool)] public bool fIssueInquiry;
        public byte cTimeoutMultiplier;
        public IntPtr hRadio;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct BluetoothDeviceInfo
    {
        public uint dwSize;
        public ulong Address;
        public uint ulClassofDevice;
        [MarshalAs(UnmanagedType.Bool)] public bool fConnected;
        [MarshalAs(UnmanagedType.Bool)] public bool fRemembered;
        [MarshalAs(UnmanagedType.Bool)] public bool fAuthenticated;
        public SystemTime stLastSeen;
        public SystemTime stLastUsed;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 248)] public string szName;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SystemTime
    {
        public ushort Year, Month, DayOfWeek, Day, Hour, Minute, Second, Milliseconds;
    }

    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern IntPtr BluetoothFindFirstDevice(ref BluetoothDeviceSearchParams searchParams, ref BluetoothDeviceInfo deviceInfo);
    [DllImport("bthprops.cpl", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool BluetoothFindNextDevice(IntPtr findHandle, ref BluetoothDeviceInfo deviceInfo);
    [DllImport("bthprops.cpl")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool BluetoothFindDeviceClose(IntPtr findHandle);

    internal static void RequireAuthenticatedExactTarget()
    {
        var search = new BluetoothDeviceSearchParams
        {
            dwSize = checked((uint)Marshal.SizeOf<BluetoothDeviceSearchParams>()),
            fReturnAuthenticated = true,
            fReturnRemembered = true,
            fReturnUnknown = false,
            fReturnConnected = true,
            fIssueInquiry = false,
            cTimeoutMultiplier = 0,
            hRadio = IntPtr.Zero,
        };
        var info = NewDeviceInfo();
        var handle = BluetoothFindFirstDevice(ref search, ref info);
        if (handle == IntPtr.Zero)
            throw new PairingRequiredException("IMAGE_PAIRING_REQUIRED: exact Ditoo is not available as a paired/remembered Windows Bluetooth device");
        try
        {
            while (true)
            {
                if (info.Address == DitooStaticImageProtocol.TargetBluetoothAddress)
                {
                    if (!info.fAuthenticated)
                        throw new PairingRequiredException("IMAGE_PAIRING_REQUIRED: exact Ditoo is known but not authenticated/paired");
                    return;
                }
                info = NewDeviceInfo();
                if (!BluetoothFindNextDevice(handle, ref info))
                    break;
            }
        }
        finally
        {
            BluetoothFindDeviceClose(handle);
        }
        throw new PairingRequiredException("IMAGE_PAIRING_REQUIRED: exact Ditoo MAC is not paired in Windows");
    }

    private static BluetoothDeviceInfo NewDeviceInfo() => new()
    {
        dwSize = checked((uint)Marshal.SizeOf<BluetoothDeviceInfo>()),
        szName = string.Empty,
    };
}

static class WindowsRfcommStaticImageTransport
{
    private const int AfBth = 32, SockStream = 1, BthProtoRfcomm = 3, SocketError = -1;
    private static readonly IntPtr InvalidSocket = new(-1), InvalidEvent = IntPtr.Zero;
    private const int WsaWouldBlock = 10035;
    private const uint WsaWaitTimeout = 258, WsaWaitEvent0 = 0, WsaWaitFailed = 0xFFFFFFFF;
    private const int FdRead = 1 << 0, FdWrite = 1 << 1, FdConnect = 1 << 4, FdClose = 1 << 5;
    private const int FdReadBit = 0, FdWriteBit = 1, FdConnectBit = 4, FdCloseBit = 5, FdMaxEvents = 10;

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
    [DllImport("Ws2_32.dll")][return: MarshalAs(UnmanagedType.Bool)] private static extern bool WSACloseEvent(IntPtr eventHandle);
    [DllImport("Ws2_32.dll")] private static extern int WSAEventSelect(IntPtr socketHandle, IntPtr eventHandle, int networkEvents);
    [DllImport("Ws2_32.dll")] private static extern int WSAEnumNetworkEvents(IntPtr socketHandle, IntPtr eventHandle, ref WsaNetworkEvents networkEvents);
    [DllImport("Ws2_32.dll")] private static extern uint WSAWaitForMultipleEvents(uint eventCount, [In] IntPtr[] eventHandles, [MarshalAs(UnmanagedType.Bool)] bool waitAll, uint timeoutMilliseconds, [MarshalAs(UnmanagedType.Bool)] bool alertable);

    internal static byte ExchangeOnce(byte[][] packets, ImageOperation? operation = null)
        => ExchangeSequenceOnce([packets], 0, operation)[0];

    /// <summary>
    /// One connection, one or more ordered frame groups, one ACK each, then close.
    /// The stock app repeats frames inside a single open session, so a sequence does
    /// not reconnect between frames. There is still no retry and no reconnect.
    /// </summary>
    internal static byte[] ExchangeSequenceOnce(byte[][][] groups, int interFrameDelayMs, ImageOperation? operation = null, int totalBudgetMsOverride = 0)
    {
        if (groups.Length < 1 || groups.Length > DitooStaticImageProtocol.MaxSequenceFrames)
            throw new ArgumentException("IMAGE_SEQUENCE_FRAME_COUNT_REJECTED");
        foreach (var group in groups)
        {
            if (group.Length != 3)
                throw new ArgumentException("IMAGE_TRANSACTION_PACKET_COUNT_REJECTED");
        }
        if (interFrameDelayMs < 0 || interFrameDelayMs > DitooStaticImageProtocol.MaxInterFrameDelayMs)
            throw new ArgumentException("IMAGE_SEQUENCE_DELAY_REJECTED");

        var budgetMs = DitooStaticImageProtocol.TotalBudgetMs
            + (groups.Length - 1) * (DitooStaticImageProtocol.AckBudgetMs + interFrameDelayMs);
        // A reviewed manifest may impose a TIGHTER ceiling than the computed one; it may
        // never loosen it.
        if (totalBudgetMsOverride > 0)
        {
            if (totalBudgetMsOverride > budgetMs)
                throw new ArgumentException("IMAGE_SEQUENCE_BUDGET_EXCEEDS_CEILING");
            budgetMs = totalBudgetMsOverride;
        }
        var total = Stopwatch.StartNew();
        var wsaData = Marshal.AllocHGlobal(512);
        var socketHandle = InvalidSocket;
        var eventHandle = InvalidEvent;
        var started = false;
        var acks = new byte[groups.Length];
        try
        {
            for (var i = 0; i < 512; i++) Marshal.WriteByte(wsaData, i, 0);
            var startup = WSAStartup(0x0202, wsaData);
            if (startup != 0) throw new InvalidOperationException($"IMAGE_WSASTARTUP_FAILED WSA={startup}");
            started = true;
            var layoutSize = Marshal.SizeOf<SockAddrBth>();
            if (layoutSize != 30) throw new InvalidOperationException($"IMAGE_SOCKADDR_BTH_LAYOUT_REJECTED SIZE={layoutSize}");
            socketHandle = socket(AfBth, SockStream, BthProtoRfcomm);
            if (socketHandle == InvalidSocket) throw new InvalidOperationException($"IMAGE_SOCKET_CREATE_FAILED WSA={WSAGetLastError()}");
            eventHandle = WSACreateEvent();
            if (eventHandle == InvalidEvent) throw new InvalidOperationException($"IMAGE_WSA_EVENT_CREATE_FAILED WSA={WSAGetLastError()}");

            SelectEvents(socketHandle, eventHandle, FdConnect, "IMAGE_CONNECT");
            var remote = new SockAddrBth
            {
                AddressFamily = AfBth,
                BluetoothAddress = DitooStaticImageProtocol.TargetBluetoothAddress,
                ServiceClassId = Guid.Empty,
                Port = DitooStaticImageProtocol.TargetRfcommChannel,
            };
            var connectDeadline = new Deadline(DitooStaticImageProtocol.ConnectBudgetMs);
            var result = connect(socketHandle, ref remote, layoutSize);
            if (result == SocketError)
            {
                var error = WSAGetLastError();
                if (error != WsaWouldBlock) throw new InvalidOperationException($"IMAGE_RFCOMM_CONNECT_FAILED WSA={error}");
                WaitForExactEvent(socketHandle, eventHandle, FdConnect, FdConnectBit, connectDeadline, "IMAGE_RFCOMM_CONNECT");
            }
            if (total.ElapsedMilliseconds > DitooStaticImageProtocol.ConnectBudgetMs)
                throw new TimeoutException("IMAGE_CONNECT_TOTAL_BUDGET_EXCEEDED");
            operation?.StageCompleted("connect");

            var initialSendDeadline = new Deadline(DitooStaticImageProtocol.AckBudgetMs);
            SelectEvents(socketHandle, eventHandle, FdWrite | FdClose, "IMAGE_INITIAL_SEND_READY");
            WaitForWriteOrClose(socketHandle, eventHandle, initialSendDeadline);
            operation?.StageCompleted("send_ready");

            var firstFrameAt = total.ElapsedMilliseconds;
            for (var frame = 0; frame < groups.Length; frame++)
            {
                var packets = groups[frame];
                var frameStartedAt = total.ElapsedMilliseconds;
                if (frame == 0) firstFrameAt = frameStartedAt;
                for (var index = 0; index < packets.Length; index++)
                {
                    var sent = send(socketHandle, packets[index], packets[index].Length, 0);
                    if (sent != packets[index].Length)
                    {
                        operation?.SendOutcomeUnknown();
                        var error = sent < 0 ? WSAGetLastError() : 0;
                        var reason = error == WsaWouldBlock ? "WOULD_BLOCK" : "PARTIAL_OR_ERROR";
                        throw new InvalidOperationException($"IMAGE_SEND_FAILED FRAME={frame + 1} INDEX={index + 1} REASON={reason} BYTES={sent} WSA={error}; NO_RETRY");
                    }
                    operation?.PacketSent(sent);
                    if (index < packets.Length - 1)
                        Thread.Sleep(DitooStaticImageProtocol.SendSpacingMs);
                }

                acks[frame] = ReadOneAck(socketHandle, eventHandle);
                var ackAt = total.ElapsedMilliseconds;
                operation?.FrameCompleted(frame + 1, ackAt - frameStartedAt, frameStartedAt - firstFrameAt, acks[frame]);
                operation?.StageCompleted($"frame_{frame + 1}_ack");
                if (total.ElapsedMilliseconds > budgetMs)
                    throw new TimeoutException("IMAGE_TOTAL_BUDGET_EXCEEDED; NO_RETRY");
                if (frame < groups.Length - 1 && interFrameDelayMs > 0)
                    Thread.Sleep(interFrameDelayMs);
            }
            operation?.StageCompleted("ack");
            return acks;
        }
        finally
        {
            if (socketHandle != InvalidSocket)
            {
                closesocket(socketHandle);
                operation?.SocketWasClosed();
            }
            if (eventHandle != InvalidEvent) WSACloseEvent(eventHandle);
            if (started) WSACleanup();
            Marshal.FreeHGlobal(wsaData);
        }
    }

    private static byte ReadOneAck(IntPtr socketHandle, IntPtr eventHandle)
    {
        SelectEvents(socketHandle, eventHandle, FdRead | FdClose, "IMAGE_ACK");
        var ackDeadline = new Deadline(DitooStaticImageProtocol.AckBudgetMs);
        var received = new List<byte>(32);
        var expectedTotal = -1;
        var chunk = new byte[32];
        while (true)
        {
            var events = WaitForEvents(socketHandle, eventHandle, ackDeadline, "IMAGE_ACK_RECV");
            if ((events.NetworkEvents & FdClose) != 0)
                throw new InvalidOperationException($"IMAGE_ACK_CLOSED WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
            if ((events.NetworkEvents & FdRead) == 0) continue;
            if (events.ErrorCodes[FdReadBit] != 0)
                throw new InvalidOperationException($"IMAGE_ACK_EVENT_FAILED WSA={events.ErrorCodes[FdReadBit]}; NO_RETRY");
            var got = recv(socketHandle, chunk, chunk.Length, 0);
            if (got <= 0)
            {
                var error = got < 0 ? WSAGetLastError() : 0;
                throw new InvalidOperationException($"IMAGE_ACK_RECV_FAILED BYTES={got} WSA={error}; NO_RETRY");
            }
            for (var i = 0; i < got; i++) received.Add(chunk[i]);
            if (received.Count >= 3 && expectedTotal < 0)
            {
                if (received[0] != 0x01) throw new InvalidOperationException("IMAGE_ACK_BAD_START; NO_RETRY");
                expectedTotal = (received[1] | (received[2] << 8)) + 4;
                if (expectedTotal != 10) throw new InvalidOperationException($"IMAGE_ACK_LENGTH_REJECTED TOTAL={expectedTotal}; NO_RETRY");
            }
            if (expectedTotal > 0 && received.Count == expectedTotal) break;
            if (received.Count > 32 || (expectedTotal > 0 && received.Count > expectedTotal))
                throw new InvalidOperationException("IMAGE_ACK_TRAILING_OR_OVERSIZE; NO_RETRY");
        }
        return ValidateAck(received.ToArray());
    }

    private static byte ValidateAck(byte[] wire)
    {
        if (wire.Length != 10 || wire[0] != 0x01 || wire[^1] != 0x02)
            throw new InvalidOperationException("IMAGE_ACK_BOUNDARY_REJECTED");
        ushort sum = 0;
        for (var i = 1; i < 7; i++) sum = unchecked((ushort)(sum + wire[i]));
        var observed = (ushort)(wire[7] | (wire[8] << 8));
        if (sum != observed)
            throw new InvalidOperationException($"IMAGE_ACK_CHECKSUM_REJECTED OBSERVED=0x{observed:X4} EXPECTED=0x{sum:X4}");
        if (wire[3] != 0x04 || wire[4] != 0x44 || wire[5] != 0x55)
            throw new InvalidOperationException("IMAGE_ACK_WRAPPER_REJECTED");
        return wire[6];
    }

    private static void SelectEvents(IntPtr s, IntPtr e, int mask, string stage)
    {
        if (WSAEventSelect(s, e, mask) == SocketError)
            throw new InvalidOperationException($"{stage}_EVENT_SELECT_FAILED WSA={WSAGetLastError()}");
    }

    private static void WaitForWriteOrClose(IntPtr s, IntPtr e, Deadline d)
    {
        while (true)
        {
            var events = WaitForEvents(s, e, d, "IMAGE_SEND_READY");
            if ((events.NetworkEvents & FdClose) != 0)
                throw new InvalidOperationException("IMAGE_SEND_CLOSED; NO_RETRY");
            if ((events.NetworkEvents & FdWrite) == 0) continue;
            if (events.ErrorCodes[FdWriteBit] != 0)
                throw new InvalidOperationException($"IMAGE_SEND_READY_FAILED WSA={events.ErrorCodes[FdWriteBit]}; NO_RETRY");
            return;
        }
    }

    private static void WaitForExactEvent(IntPtr s, IntPtr e, int mask, int errorIndex, Deadline d, string stage)
    {
        while (true)
        {
            var events = WaitForEvents(s, e, d, stage);
            if ((events.NetworkEvents & mask) == 0) continue;
            if (events.ErrorCodes[errorIndex] != 0)
                throw new InvalidOperationException($"{stage}_FAILED WSA={events.ErrorCodes[errorIndex]}");
            return;
        }
    }

    private static WsaNetworkEvents WaitForEvents(IntPtr s, IntPtr e, Deadline d, string stage)
    {
        var wait = WSAWaitForMultipleEvents(1, [e], false, checked((uint)d.RemainingMilliseconds(stage)), false);
        if (wait == WsaWaitTimeout) throw new TimeoutException($"{stage}_TIMEOUT; NO_RETRY");
        if (wait == WsaWaitFailed) throw new InvalidOperationException($"{stage}_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if (wait != WsaWaitEvent0) throw new InvalidOperationException($"{stage}_WAIT_UNEXPECTED RESULT={wait}; NO_RETRY");
        var events = WsaNetworkEvents.Create();
        if (WSAEnumNetworkEvents(s, e, ref events) == SocketError)
            throw new InvalidOperationException($"{stage}_ENUM_EVENTS_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        return events;
    }

    private sealed class Deadline(int budgetMs)
    {
        private readonly long started = Stopwatch.GetTimestamp();
        private readonly double ticksPerMs = Stopwatch.Frequency / 1000.0;

        internal int RemainingMilliseconds(string stage)
        {
            var elapsed = (Stopwatch.GetTimestamp() - started) / ticksPerMs;
            var remaining = budgetMs - (int)Math.Ceiling(elapsed);
            if (remaining <= 0) throw new TimeoutException($"{stage}_TIMEOUT BUDGET_MS={budgetMs}; NO_RETRY");
            return remaining;
        }
    }
}
