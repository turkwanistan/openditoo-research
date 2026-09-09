using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

const bool TransmissionAuthorized = false;

byte[][] packets =
[
    Convert.FromHexString("0103009FA20002"),
    Convert.FromHexString("010400BD31F20002"),
    Convert.FromHexString("01800044000A0A04AA7900F4010006000000FF000000FF000000FFFFFFFF5A5A5A0900000000400000000000400000000000400000000000000000000000000000000000000000000000000000A00000000000000000000000000000000000000000000000000000000000000000000000000000001B00000000001B0000000080210C02"),
];
string[] expectedHashes =
[
    "c8026e7a39d55bbd0db852705c16bdfe1c0c1f4341c1a17130965f870e3037e6",
    "d9ef630e33d736dd859855cde6c3429df09fddae21bb18ccb0cd07927a10637a",
    "db336e89123dc472d5e4d2815fb6df6115a4feb436b8678de4b33bd18ba3cb9b",
];

if (args.Length != 0)
{
    Console.Error.WriteLine("M5_RUNNER_REJECTED: no arguments are accepted");
    return 2;
}

for (var i = 0; i < packets.Length; i++)
{
    var hash = Convert.ToHexString(SHA256.HashData(packets[i])).ToLowerInvariant();
    if (!hash.Equals(expectedHashes[i], StringComparison.Ordinal))
    {
        Console.Error.WriteLine($"M5_PACKET_HASH_DRIFT INDEX={i + 1}");
        return 3;
    }
}
if (packets.Sum(x => x.Length) != 147 || packets[2].Length != 132)
{
    Console.Error.WriteLine("M5_PACKET_BUDGET_DRIFT");
    return 3;
}

Console.WriteLine($"M5_EXECUTION_ID={M5Config.ExecutionId}");
Console.WriteLine($"M5_TARGET={M5Config.TargetMac}");
Console.WriteLine($"M5_RFCOMM_CHANNEL={M5Config.TargetRfcommChannel}");
Console.WriteLine("M5_PACKET_COUNT=3");
Console.WriteLine("M5_TX_BYTES_TOTAL=147");
Console.WriteLine("M5_RETRY=false");

if (!TransmissionAuthorized)
{
    Console.Error.WriteLine("M5_NOT_AUTHORIZED: runner is compile-time disarmed in this revision");
    Console.Error.WriteLine("M5_CONNECTIONS_ATTEMPTED=0");
    Console.Error.WriteLine("M5_REQUESTS_SENT=0");
    return 31;
}

try
{
    PairedTargetGuard.RequireAuthenticatedExactTarget();
    Console.WriteLine("M5_PRECHECK=PASS_EXACT_TARGET_PAIRED");
    var ackPayload = WindowsRfcommM5Transport.ExchangeOnce(packets);
    Console.WriteLine("M5_RESULT=TRANSPORT_PASS");
    Console.WriteLine($"M5_ACK_PAYLOAD=0x{ackPayload:X2}");
    Console.WriteLine("M5_PACKETS_SENT=3");
    Console.WriteLine("M5_CONNECTIONS_ATTEMPTED=1");
    Console.WriteLine("M5_SOCKET_CLOSED=true");
    Console.WriteLine("M5_VISUAL_RESULT=OPERATOR_OBSERVATION_REQUIRED");
    return 0;
}
catch (PairingRequiredException ex)
{
    Console.Error.WriteLine(ex.Message);
    Console.Error.WriteLine("M5_CONNECTIONS_ATTEMPTED=0");
    Console.Error.WriteLine("M5_REQUESTS_SENT=0");
    return 20;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"M5_RESULT=FAIL_CLOSED {ex.GetType().Name}: {ex.Message}");
    Console.Error.WriteLine("M5_RETRY=false");
    return 30;
}


static class M5Config
{
    internal const string ExecutionId = "OPENDITOO-DAY1-M5-STATIC-DIAGNOSTIC-001";
    internal const string TargetMac = "11:75:58:CE:DE:C7";
    internal const ulong TargetBluetoothAddress = 0x117558CEDEC7;
    internal const uint TargetRfcommChannel = 1;
    internal const int ConnectBudgetMs = 15_000;
    internal const int AckBudgetMs = 5_000;
    internal const int TotalBudgetMs = 20_000;
    internal const int SendSpacingMs = 40;
}

sealed class PairingRequiredException(string message) : Exception(message);

static class PairedTargetGuard
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
            dwSize = (uint)Marshal.SizeOf<BluetoothDeviceSearchParams>(),
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
            throw new PairingRequiredException("M5_PAIRING_REQUIRED_NO_CONNECT: exact Ditoo is not available as a paired/remembered Windows Bluetooth device");
        try
        {
            while (true)
            {
                if (info.Address == M5Config.TargetBluetoothAddress)
                {
                    if (!info.fAuthenticated)
                        throw new PairingRequiredException("M5_PAIRING_REQUIRED_NO_CONNECT: exact Ditoo is known but not authenticated/paired");
                    return;
                }
                info = NewDeviceInfo();
                if (!BluetoothFindNextDevice(handle, ref info)) break;
            }
        }
        finally { BluetoothFindDeviceClose(handle); }
        throw new PairingRequiredException("M5_PAIRING_REQUIRED_NO_CONNECT: exact Ditoo MAC is not paired in Windows");
    }

    private static BluetoothDeviceInfo NewDeviceInfo() => new()
    {
        dwSize = (uint)Marshal.SizeOf<BluetoothDeviceInfo>(),
        szName = string.Empty,
    };
}

static class WindowsRfcommM5Transport
{
    private const int AfBth = 32, SockStream = 1, BthProtoRfcomm = 3, SocketError = -1;
    private static readonly IntPtr InvalidSocket = new(-1), InvalidEvent = IntPtr.Zero;
    private const int WsaWouldBlock = 10035;
    private const uint WsaWaitTimeout = 258, WsaWaitEvent0 = 0, WsaWaitFailed = 0xFFFFFFFF;
    private const int FdRead = 1 << 0, FdWrite = 1 << 1, FdConnect = 1 << 4, FdClose = 1 << 5;
    private const int FdReadBit = 0, FdWriteBit = 1, FdConnectBit = 4, FdCloseBit = 5, FdMaxEvents = 10;

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    private struct SockAddrBth { public ushort AddressFamily; public ulong BluetoothAddress; public Guid ServiceClassId; public uint Port; }
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

    internal static byte ExchangeOnce(byte[][] packets)
    {
        var total = Stopwatch.StartNew();
        var wsaData = Marshal.AllocHGlobal(512);
        var socketHandle = InvalidSocket;
        var eventHandle = InvalidEvent;
        var started = false;
        try
        {
            for (var i = 0; i < 512; i++) Marshal.WriteByte(wsaData, i, 0);
            var startup = WSAStartup(0x0202, wsaData);
            if (startup != 0) throw new InvalidOperationException($"M5_WSASTARTUP_FAILED WSA={startup}");
            started = true;
            var layoutSize = Marshal.SizeOf<SockAddrBth>();
            if (layoutSize != 30) throw new InvalidOperationException($"M5_SOCKADDR_BTH_LAYOUT_REJECTED SIZE={layoutSize}");
            socketHandle = socket(AfBth, SockStream, BthProtoRfcomm);
            if (socketHandle == InvalidSocket) throw new InvalidOperationException($"M5_SOCKET_CREATE_FAILED WSA={WSAGetLastError()}");
            eventHandle = WSACreateEvent();
            if (eventHandle == InvalidEvent) throw new InvalidOperationException($"M5_WSA_EVENT_CREATE_FAILED WSA={WSAGetLastError()}");

            SelectEvents(socketHandle, eventHandle, FdConnect, "M5_CONNECT");
            var remote = new SockAddrBth { AddressFamily = AfBth, BluetoothAddress = M5Config.TargetBluetoothAddress, ServiceClassId = Guid.Empty, Port = M5Config.TargetRfcommChannel };
            var connectDeadline = new Deadline(M5Config.ConnectBudgetMs);
            var result = connect(socketHandle, ref remote, layoutSize); // exactly one connect call
            if (result == SocketError)
            {
                var error = WSAGetLastError();
                if (error != WsaWouldBlock) throw new InvalidOperationException($"M5_RFCOMM_CONNECT_FAILED WSA={error}");
                WaitForExactEvent(socketHandle, eventHandle, FdConnect, FdConnectBit, connectDeadline, "M5_RFCOMM_CONNECT");
            }
            if (total.ElapsedMilliseconds > M5Config.ConnectBudgetMs) throw new TimeoutException("M5_CONNECT_TOTAL_BUDGET_EXCEEDED");

            for (var index = 0; index < packets.Length; index++)
            {
                var sendDeadline = new Deadline(M5Config.AckBudgetMs);
                SelectEvents(socketHandle, eventHandle, FdWrite | FdClose, $"M5_SEND_{index + 1}");
                WaitForWriteOrClose(socketHandle, eventHandle, sendDeadline, index + 1);
                var sent = send(socketHandle, packets[index], packets[index].Length, 0); // exactly one send per frozen packet
                if (sent != packets[index].Length)
                {
                    var error = sent < 0 ? WSAGetLastError() : 0;
                    throw new InvalidOperationException($"M5_APPLICATION_SEND_AMBIGUOUS INDEX={index + 1} BYTES={sent} WSA={error}; NO_RETRY");
                }
                if (index < packets.Length - 1) Thread.Sleep(M5Config.SendSpacingMs);
            }

            SelectEvents(socketHandle, eventHandle, FdRead | FdClose, "M5_ACK");
            var ackDeadline = new Deadline(M5Config.AckBudgetMs);
            var received = new List<byte>(32);
            var expectedTotal = -1;
            var chunk = new byte[32];
            while (true)
            {
                var events = WaitForEvents(socketHandle, eventHandle, ackDeadline, "M5_ACK_RECV");
                if ((events.NetworkEvents & FdClose) != 0)
                    throw new InvalidOperationException($"M5_ACK_CLOSED WSA={events.ErrorCodes[FdCloseBit]}; NO_RETRY");
                if ((events.NetworkEvents & FdRead) == 0) continue;
                if (events.ErrorCodes[FdReadBit] != 0)
                    throw new InvalidOperationException($"M5_ACK_EVENT_FAILED WSA={events.ErrorCodes[FdReadBit]}; NO_RETRY");
                var got = recv(socketHandle, chunk, chunk.Length, 0);
                if (got <= 0)
                {
                    var error = got < 0 ? WSAGetLastError() : 0;
                    throw new InvalidOperationException($"M5_ACK_RECV_FAILED BYTES={got} WSA={error}; NO_RETRY");
                }
                for (var i = 0; i < got; i++) received.Add(chunk[i]);
                if (received.Count >= 3 && expectedTotal < 0)
                {
                    if (received[0] != 0x01) throw new InvalidOperationException("M5_ACK_BAD_START; NO_RETRY");
                    expectedTotal = (received[1] | (received[2] << 8)) + 4;
                    if (expectedTotal != 10) throw new InvalidOperationException($"M5_ACK_LENGTH_REJECTED TOTAL={expectedTotal}; NO_RETRY");
                }
                if (expectedTotal > 0 && received.Count == expectedTotal) break;
                if (received.Count > 32 || (expectedTotal > 0 && received.Count > expectedTotal))
                    throw new InvalidOperationException("M5_ACK_TRAILING_OR_OVERSIZE; NO_RETRY");
            }
            if (total.ElapsedMilliseconds > M5Config.TotalBudgetMs) throw new TimeoutException("M5_TOTAL_BUDGET_EXCEEDED; NO_RETRY");
            return ValidateAck(received.ToArray());
        }
        finally
        {
            if (socketHandle != InvalidSocket) closesocket(socketHandle);
            if (eventHandle != InvalidEvent) WSACloseEvent(eventHandle);
            if (started) WSACleanup();
            Marshal.FreeHGlobal(wsaData);
        }
    }

    private static byte ValidateAck(byte[] wire)
    {
        if (wire.Length != 10 || wire[0] != 0x01 || wire[^1] != 0x02) throw new InvalidOperationException("M5_ACK_BOUNDARY_REJECTED");
        ushort sum = 0;
        for (var i = 1; i < 7; i++) sum = unchecked((ushort)(sum + wire[i]));
        var observed = (ushort)(wire[7] | (wire[8] << 8));
        if (sum != observed) throw new InvalidOperationException($"M5_ACK_CHECKSUM_REJECTED OBSERVED=0x{observed:X4} EXPECTED=0x{sum:X4}");
        if (wire[3] != 0x04 || wire[4] != 0x44 || wire[5] != 0x55) throw new InvalidOperationException("M5_ACK_WRAPPER_REJECTED");
        return wire[6];
    }

    private static void SelectEvents(IntPtr s, IntPtr e, int mask, string stage)
    {
        if (WSAEventSelect(s, e, mask) == SocketError) throw new InvalidOperationException($"{stage}_EVENT_SELECT_FAILED WSA={WSAGetLastError()}");
    }
    private static void WaitForWriteOrClose(IntPtr s, IntPtr e, Deadline d, int index)
    {
        while (true)
        {
            var events = WaitForEvents(s, e, d, $"M5_SEND_READY_{index}");
            if ((events.NetworkEvents & FdClose) != 0) throw new InvalidOperationException($"M5_SEND_CLOSED INDEX={index}; NO_RETRY");
            if ((events.NetworkEvents & FdWrite) == 0) continue;
            if (events.ErrorCodes[FdWriteBit] != 0) throw new InvalidOperationException($"M5_SEND_READY_FAILED INDEX={index} WSA={events.ErrorCodes[FdWriteBit]}; NO_RETRY");
            return;
        }
    }
    private static void WaitForExactEvent(IntPtr s, IntPtr e, int mask, int errorIndex, Deadline d, string stage)
    {
        while (true)
        {
            var events = WaitForEvents(s, e, d, stage);
            if ((events.NetworkEvents & mask) == 0) continue;
            if (events.ErrorCodes[errorIndex] != 0) throw new InvalidOperationException($"{stage}_FAILED WSA={events.ErrorCodes[errorIndex]}");
            return;
        }
    }
    private static WsaNetworkEvents WaitForEvents(IntPtr s, IntPtr e, Deadline d, string stage)
    {
        var wait = WSAWaitForMultipleEvents(1, [e], false, (uint)d.RemainingMilliseconds(stage), false);
        if (wait == WsaWaitTimeout) throw new TimeoutException($"{stage}_TIMEOUT; NO_RETRY");
        if (wait == WsaWaitFailed) throw new InvalidOperationException($"{stage}_WAIT_FAILED WSA={WSAGetLastError()}; NO_RETRY");
        if (wait != WsaWaitEvent0) throw new InvalidOperationException($"{stage}_WAIT_UNEXPECTED RESULT={wait}; NO_RETRY");
        var events = WsaNetworkEvents.Create();
        if (WSAEnumNetworkEvents(s, e, ref events) == SocketError) throw new InvalidOperationException($"{stage}_ENUM_EVENTS_FAILED WSA={WSAGetLastError()}; NO_RETRY");
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
