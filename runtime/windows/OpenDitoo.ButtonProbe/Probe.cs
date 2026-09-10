// OpenDitoo.ButtonProbe (BTN-1): receive-only proof that Windows surfaces the Ditoo's
// AVRCP pass-through keys to an application. It registers with Windows media controls
// and input only. It holds no Ditoo transport, no Host endpoint or credential, no target,
// and no send path of any kind.
//
// Sources are logged separately and never merged or de-duplicated:
//   smtc                   SystemMediaTransportControls for this process's own HWND (primary)
//   wm_appcommand          WM_APPCOMMAND delivered to the hidden window (diagnostic)
//   rawinput_keyboard      raw keyboard input, FILTERED to the four media VKs only
//   rawinput_consumer      raw HID consumer-control reports (diagnostic, hex only)
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Windows.Media;

namespace OpenDitoo.ButtonProbe;

public static class Normalize
{
    public static string? Smtc(string button) => button switch
    {
        "Previous" => "nav_left",
        "Next" => "nav_right",
        "Play" or "Pause" => "lever_candidate",
        _ => null,
    };

    // APPCOMMAND_MEDIA_* ids from winuser.h.
    public static string? AppCommand(int command) => command switch
    {
        12 => "nav_left",                 // MEDIA_PREVIOUSTRACK
        11 => "nav_right",                // MEDIA_NEXTTRACK
        14 or 46 or 47 => "lever_candidate", // MEDIA_PLAY_PAUSE / PLAY / PAUSE
        _ => null,
    };

    public const int VkNext = 0xB0, VkPrev = 0xB1, VkStop = 0xB2, VkPlayPause = 0xB3;

    // The only keyboard keys the probe may ever record. Anything else is dropped unread.
    public static bool IsMediaVk(int vk) => vk is VkNext or VkPrev or VkStop or VkPlayPause;

    public static string? MediaVk(int vk) => vk switch
    {
        VkPrev => "nav_left",
        VkNext => "nav_right",
        VkPlayPause => "lever_candidate",
        _ => null,
    };

    public static string VkName(int vk) => vk switch
    {
        VkNext => "VK_MEDIA_NEXT_TRACK",
        VkPrev => "VK_MEDIA_PREV_TRACK",
        VkStop => "VK_MEDIA_STOP",
        VkPlayPause => "VK_MEDIA_PLAY_PAUSE",
        _ => "other",
    };
}

public sealed class NdjsonLog
{
    private readonly object gate = new();
    private readonly TextWriter[] sinks;
    private long seq;

    public string Epoch { get; } = Guid.NewGuid().ToString("N")[..12];
    public long Count => Interlocked.Read(ref seq);

    public NdjsonLog(params TextWriter[] sinks) => this.sinks = sinks;

    public long Write(string type, Dictionary<string, object?> fields)
    {
        lock (gate)
        {
            var record = new Dictionary<string, object?>
            {
                ["epoch"] = Epoch,
                ["seq"] = ++seq,
                ["at_monotonic_ms"] = Math.Round(Stopwatch.GetTimestamp() * 1000.0 / Stopwatch.Frequency, 3),
                ["at_utc"] = DateTime.UtcNow.ToString("O"),
                ["type"] = type,
            };
            foreach (var pair in fields) record[pair.Key] = pair.Value;
            var line = JsonSerializer.Serialize(record);
            foreach (var sink in sinks) { sink.WriteLine(line); sink.Flush(); }
            return seq;
        }
    }

    public long Event(string source, string rawButton, string? candidate, Dictionary<string, object?>? extra = null)
    {
        var fields = new Dictionary<string, object?>
        {
            ["source"] = source, ["raw_button"] = rawButton, ["normalized_candidate"] = candidate,
        };
        if (extra != null) foreach (var pair in extra) fields[pair.Key] = pair.Value;
        return Write("event", fields);
    }
}

internal sealed class ProbeWindow : NativeWindow
{
    private const int WM_INPUT = 0x00FF, WM_APPCOMMAND = 0x0319, WM_KEYDOWN = 0x0100, WM_KEYUP = 0x0101;
    private const uint RID_INPUT = 0x10000003, RIDI_DEVICENAME = 0x20000007;
    private const uint RIM_TYPEKEYBOARD = 1, RIM_TYPEHID = 2, RIDEV_INPUTSINK = 0x100;

    private readonly NdjsonLog log;
    private readonly Dictionary<IntPtr, string> deviceNames = new();

    public ProbeWindow(NdjsonLog log)
    {
        this.log = log;
        CreateHandle(new CreateParams { Caption = "OpenDitoo ButtonProbe" }); // top-level, never shown
    }

    public bool RegisterRawInput()
    {
        var devices = new[]
        {
            new RAWINPUTDEVICE { UsagePage = 0x01, Usage = 0x06, Flags = RIDEV_INPUTSINK, Target = Handle }, // keyboard
            new RAWINPUTDEVICE { UsagePage = 0x0C, Usage = 0x01, Flags = RIDEV_INPUTSINK, Target = Handle }, // consumer control
        };
        return RegisterRawInputDevices(devices, (uint)devices.Length, (uint)Marshal.SizeOf<RAWINPUTDEVICE>());
    }

    protected override void WndProc(ref Message m)
    {
        if (m.Msg == WM_APPCOMMAND)
        {
            int command = (short)(((long)m.LParam >> 16) & 0xFFFF) & ~0xF000;
            log.Event("wm_appcommand", $"APPCOMMAND_{command}", Normalize.AppCommand(command));
        }
        else if (m.Msg == WM_INPUT)
        {
            OnRawInput(m.LParam);
        }
        base.WndProc(ref m);
    }

    private void OnRawInput(IntPtr handle)
    {
        uint headerSize = (uint)Marshal.SizeOf<RAWINPUTHEADER>();
        uint size = 0;
        if (GetRawInputData(handle, RID_INPUT, IntPtr.Zero, ref size, headerSize) != 0 || size == 0) return;
        IntPtr buffer = Marshal.AllocHGlobal((int)size);
        try
        {
            if (GetRawInputData(handle, RID_INPUT, buffer, ref size, headerSize) != size) return;
            var header = Marshal.PtrToStructure<RAWINPUTHEADER>(buffer);
            IntPtr body = buffer + (int)headerSize;
            if (header.Type == RIM_TYPEKEYBOARD)
            {
                var key = Marshal.PtrToStructure<RAWKEYBOARD>(body);
                if (!Normalize.IsMediaVk(key.VKey)) return; // privacy boundary: never record other keys
                bool down = key.Message == WM_KEYDOWN;
                if (!down && key.Message != WM_KEYUP) return;
                log.Event("rawinput_keyboard", $"{Normalize.VkName(key.VKey)} {(down ? "down" : "up")}",
                          down ? Normalize.MediaVk(key.VKey) : null, Device(header.Device));
            }
            else if (header.Type == RIM_TYPEHID)
            {
                int sizeHid = Marshal.ReadInt32(body), count = Marshal.ReadInt32(body, 4);
                int total = Math.Min(sizeHid * count, (int)size - (int)headerSize - 8);
                var bytes = new byte[Math.Max(total, 0)];
                Marshal.Copy(body + 8, bytes, 0, bytes.Length);
                log.Event("rawinput_consumer", Convert.ToHexString(bytes), null, Device(header.Device));
            }
        }
        finally { Marshal.FreeHGlobal(buffer); }
    }

    private Dictionary<string, object?> Device(IntPtr device)
    {
        if (!deviceNames.TryGetValue(device, out var name))
        {
            name = "none(injected)";
            uint chars = 0;
            if (device != IntPtr.Zero && GetRawInputDeviceInfo(device, RIDI_DEVICENAME, IntPtr.Zero, ref chars) == 0 && chars > 0)
            {
                IntPtr text = Marshal.AllocHGlobal((int)chars * 2);
                try
                {
                    if ((int)GetRawInputDeviceInfo(device, RIDI_DEVICENAME, text, ref chars) > 0)
                        name = Marshal.PtrToStringUni(text) ?? name;
                }
                finally { Marshal.FreeHGlobal(text); }
            }
            deviceNames[device] = name;
        }
        return new Dictionary<string, object?> { ["device"] = name };
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct RAWINPUTDEVICE { public ushort UsagePage; public ushort Usage; public uint Flags; public IntPtr Target; }

    [StructLayout(LayoutKind.Sequential)]
    private struct RAWINPUTHEADER { public uint Type; public uint Size; public IntPtr Device; public IntPtr WParam; }

    [StructLayout(LayoutKind.Sequential)]
    private struct RAWKEYBOARD
    {
        public ushort MakeCode; public ushort Flags; public ushort Reserved; public ushort VKey;
        public uint Message; public uint ExtraInformation;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterRawInputDevices(RAWINPUTDEVICE[] devices, uint count, uint size);

    [DllImport("user32.dll")]
    private static extern uint GetRawInputData(IntPtr rawInput, uint command, IntPtr data, ref uint size, uint headerSize);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern uint GetRawInputDeviceInfo(IntPtr device, uint command, IntPtr data, ref uint size);
}

public static class Program
{
    [STAThread]
    public static int Main(string[] args)
    {
        if (args.Contains("--selftest")) return Selftest.Run();

        int seconds = 900;
        string? logPath = null;
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--seconds") seconds = Math.Clamp(int.Parse(args[i + 1]), 5, 3600);
            if (args[i] == "--log") logPath = args[i + 1];
        }

        using var file = logPath == null ? null : new StreamWriter(logPath, append: true);
        var log = file == null ? new NdjsonLog(Console.Out) : new NdjsonLog(Console.Out, file);
        var window = new ProbeWindow(log);
        bool rawInput = window.RegisterRawInput();

        var smtcState = new Dictionary<string, object?>();
        SystemMediaTransportControls? smtc = null;
        try
        {
            smtc = SystemMediaTransportControlsInterop.GetForWindow(window.Handle);
            smtc.IsEnabled = true;
            smtc.IsPlayEnabled = smtc.IsPauseEnabled = smtc.IsNextEnabled = smtc.IsPreviousEnabled = true;
            // Deliberately constant: the probe never toggles state, so raw Play vs Pause is the device's choice.
            smtc.PlaybackStatus = MediaPlaybackStatus.Playing;
            smtc.DisplayUpdater.Type = MediaPlaybackType.Music;
            smtc.DisplayUpdater.MusicProperties.Title = "OpenDitoo ButtonProbe";
            smtc.DisplayUpdater.Update();
            smtc.ButtonPressed += (_, e) => log.Event("smtc", e.Button.ToString(), Normalize.Smtc(e.Button.ToString()));
            smtcState["acquired"] = true;
            smtcState["playback_status"] = smtc.PlaybackStatus.ToString();
        }
        catch (Exception exc)
        {
            smtcState["acquired"] = false;
            smtcState["error"] = $"{exc.GetType().Name}: {exc.Message}";
        }

        log.Write("probe_started", new()
        {
            ["pid"] = Environment.ProcessId, ["seconds"] = seconds, ["smtc"] = smtcState,
            ["rawinput_registered"] = rawInput, ["merging"] = "none; every source logged separately",
        });

        var timer = new System.Windows.Forms.Timer { Interval = seconds * 1000 };
        timer.Tick += (_, _) => Application.ExitThread();
        timer.Start();
        Console.CancelKeyPress += (_, e) => { e.Cancel = true; Application.ExitThread(); };
        Application.Run();

        if (smtc != null) smtc.IsEnabled = false;
        log.Write("probe_stopped", new() { ["records_before_stop"] = log.Count });
        window.DestroyHandle();
        return 0;
    }
}
