using System.Runtime.InteropServices;
using OpenDitoo.Day1.Host.Internal;

if (args.Length != 0)
{
    Console.Error.WriteLine("M4_RUNNER_REJECTED: no arguments are accepted");
    return 2;
}

try
{
    DitooM4FileVersionProtocol.VerifyFrozenConstants();
    PairedTargetGuard.RequireAuthenticatedExactTarget();
    Console.WriteLine("M4_PRECHECK=PASS_EXACT_TARGET_PAIRED");
    Console.WriteLine($"M4_TARGET={DitooM4FileVersionProtocol.TargetMac}");
    Console.WriteLine($"M4_RFCOMM_CHANNEL={DitooM4FileVersionProtocol.TargetRfcommChannel}");
    Console.WriteLine($"M4_TX={Convert.ToHexString(DitooM4FileVersionProtocol.Request)}");
    Console.WriteLine("M4_RETRY=false");

    var version = WindowsRfcommBoundedM4Transport.ExchangeFrozenFileVersionOnce();
    Console.WriteLine("M4_RESULT=PASS");
    Console.WriteLine($"M4_VERSION={version}");
    Console.WriteLine("M4_REQUESTS_SENT=1");
    Console.WriteLine("M4_CONNECTIONS_ATTEMPTED=1");
    Console.WriteLine("M4_SOCKET_CLOSED=true");
    return 0;
}
catch (PairingRequiredException ex)
{
    Console.Error.WriteLine(ex.Message);
    Console.Error.WriteLine("M4_CONNECTIONS_ATTEMPTED=0");
    Console.Error.WriteLine("M4_REQUESTS_SENT=0");
    return 20;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"M4_RESULT=FAIL_CLOSED {ex.GetType().Name}: {ex.Message}");
    Console.Error.WriteLine("M4_RETRY=false");
    return 30;
}

internal sealed class PairingRequiredException : Exception
{
    internal PairingRequiredException(string message) : base(message) { }
}

internal static class PairedTargetGuard
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
        public ushort Year;
        public ushort Month;
        public ushort DayOfWeek;
        public ushort Day;
        public ushort Hour;
        public ushort Minute;
        public ushort Second;
        public ushort Milliseconds;
    }

    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern IntPtr BluetoothFindFirstDevice(
        ref BluetoothDeviceSearchParams searchParams,
        ref BluetoothDeviceInfo deviceInfo);

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
            throw new PairingRequiredException("M4_PAIRING_REQUIRED_NO_CONNECT: exact Ditoo is not currently available as a paired/remembered Windows Bluetooth device");

        try
        {
            while (true)
            {
                if (info.Address == DitooM4FileVersionProtocol.TargetBluetoothAddress)
                {
                    if (!info.fAuthenticated)
                        throw new PairingRequiredException("M4_PAIRING_REQUIRED_NO_CONNECT: exact Ditoo is known to Windows but is not authenticated/paired");
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

        throw new PairingRequiredException("M4_PAIRING_REQUIRED_NO_CONNECT: exact Ditoo MAC is not paired in Windows");
    }

    private static BluetoothDeviceInfo NewDeviceInfo() => new()
    {
        dwSize = (uint)Marshal.SizeOf<BluetoothDeviceInfo>(),
        szName = string.Empty,
    };
}
