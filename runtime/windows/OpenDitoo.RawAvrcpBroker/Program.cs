using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace OpenDitoo.RawAvrcpBroker;

internal static class Program
{
    private const int DefaultPort = 24353;

    public static int Main(string[] args)
    {
        if (args.Contains("--selftest")) return Selftest.Run();
        try
        {
            var options = Options.Parse(args);
            using var runner = new Runner(options);
            return runner.Run();
        }
        catch (Exception exc)
        {
            Console.Error.WriteLine($"RAW_AVRCP_BROKER_ERROR={exc.GetType().Name}:{exc.Message}");
            return 2;
        }
    }

    internal sealed record InputEvent(byte Operation, string RawButton, string Candidate);

    internal static InputEvent? DecodePayload(string? field)
    {
        if (string.IsNullOrWhiteSpace(field)) return null;
        var hex = new string(field.Where(Uri.IsHexDigit).ToArray());
        if ((hex.Length & 1) != 0) return null;
        byte[] bytes;
        try { bytes = Convert.FromHexString(hex); }
        catch (FormatException) { return null; }
        // Exact AVCTP single-packet AVRCP CONTROL / panel PASS THROUGH command:
        // header, profile 0x110E, ctype 0x00, panel 0x48, opcode 0x7C, operation, len=0.
        for (var i = 0; i + 7 < bytes.Length; i++)
        {
            var header = bytes[i];
            if (((header >> 2) & 0x03) != 0 || (header & 0x03) != 0) continue; // single command, IPID clear
            if (bytes[i + 1] != 0x11 || bytes[i + 2] != 0x0E || bytes[i + 3] != 0x00 ||
                bytes[i + 4] != 0x48 || bytes[i + 5] != 0x7C || bytes[i + 7] != 0x00) continue;
            return bytes[i + 6] switch
            {
                0x4C => new(0x4C, "Backward", "nav_left"),
                0x4B => new(0x4B, "Forward", "nav_right"),
                0x44 => new(0x44, "Play", "lever_candidate"),
                0x46 => new(0x46, "Pause", "lever_candidate"),
                _ => null,
            };
        }
        return null;
    }

    // tshark columns: epoch, ACL handle, ACL pb_flag, disconnected handle (HCI event 0x05), raw L2CAP payload.
    internal sealed record Observation(InputEvent? Input, string? Change, string? Handle);

    /// <summary>
    /// Learns the exact Ditoo ACL handle from OpenDitoo's own outbound image transaction (Pixel Coloring
    /// preamble A immediately followed by preamble B on the same handle), because BTVS attached mid-connection
    /// has no address mapping. Nothing is persisted: a disconnect of the bound handle unbinds, and the next
    /// OpenDitoo frame rebinds. Only inbound AVRCP presses on the bound handle become input.
    /// </summary>
    internal sealed class HandleBinder
    {
        private const string PreambleA = "0103009fa20002";
        private const string PreambleB = "010400bd31f20002";
        private string? pendingA;
        internal string? Bound { get; private set; }

        internal Observation Observe(string[] c)
        {
            string Col(int i) => i < c.Length ? c[i].Trim() : string.Empty;
            string handle = Col(1), pb = Col(2), disconnected = Col(3);
            if (handle.Length == 0)
            {
                if (disconnected.Length == 0) return new(null, null, null);
                if (disconnected == pendingA) pendingA = null;
                if (disconnected != Bound) return new(null, null, disconnected);
                Bound = null;
                return new(null, "handle_unbound", disconnected);
            }
            var hex = new string(Col(4).Where(Uri.IsHexDigit).ToArray()).ToLowerInvariant();
            if (pb == "0") // host -> controller (spec: controller never sends pb 00 on BR/EDR)
            {
                if (hex.Contains(PreambleA, StringComparison.Ordinal)) { pendingA = handle; return new(null, null, handle); }
                if (!hex.Contains(PreambleB, StringComparison.Ordinal) || pendingA != handle) return new(null, null, handle);
                pendingA = null;
                if (Bound == handle) return new(null, null, handle);
                Bound = handle;
                return new(null, "handle_bound", handle);
            }
            if (pb != "2") return new(null, null, handle); // AVRCP presses arrive controller -> host, first fragment
            // The display filter only admits pass-through CONTROL commands, so any row on another handle is
            // another device's button (press or release): record the exclusion as negative-control evidence.
            if (Bound is not null && handle != Bound) return new(null, "ignored_foreign_handle", handle);
            var input = DecodePayload(hex);
            if (input is null) return new(null, null, handle);
            return Bound is null ? new(null, "ignored_unbound", handle) : new(input, null, handle);
        }
    }

    private sealed record Options(string Target, string Events, string SinkLog, string SinkExe,
                                  string BtvsExe, string TsharkExe, int Port, int Seconds, string? Lease)
    {
        internal static Options Parse(string[] args)
        {
            string Need(string name)
            {
                var i = Array.IndexOf(args, name);
                if (i < 0 || i + 1 >= args.Length || string.IsNullOrWhiteSpace(args[i + 1]))
                    throw new ArgumentException($"missing {name}");
                return args[i + 1];
            }
            int OptionalInt(string name, int fallback)
            {
                var i = Array.IndexOf(args, name);
                return i >= 0 && i + 1 < args.Length ? int.Parse(args[i + 1], CultureInfo.InvariantCulture) : fallback;
            }
            var port = OptionalInt("--port", DefaultPort);
            var seconds = OptionalInt("--seconds", 0);
            if (port is < 1024 or > 65535) throw new ArgumentOutOfRangeException("--port");
            if (seconds < 0) throw new ArgumentOutOfRangeException("--seconds");
            var lease = Array.IndexOf(args, "--lease") is var li and >= 0 && li + 1 < args.Length ? args[li + 1] : null;
            return new(Need("--target"), Need("--events"), Need("--sink-log"), Need("--sink-exe"),
                       Need("--btvs"), Need("--tshark"), port, seconds, lease);
        }
    }

    private sealed class Runner : IDisposable
    {
        private readonly Options options;
        private readonly string epoch = Guid.NewGuid().ToString("N")[..12];
        private readonly List<Process> children = [];
        private readonly Job job = new();
        private long seq;
        private bool disposed;

        internal Runner(Options options) => this.options = options;

        internal int Run()
        {
            foreach (var path in new[] { options.SinkExe, options.BtvsExe, options.TsharkExe })
                if (!File.Exists(path)) throw new FileNotFoundException("required executable missing", path);
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(options.Events))!);
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(options.SinkLog))!);
            // Truncate: under the scheduled task only this (elevated) process can safely reset its own log;
            // the WSL cursor resets on a shrink and treats the new epoch as a fresh baseline.
            using var writer = new StreamWriter(options.Events, append: false) { AutoFlush = true };
            Write(writer, "broker_started", new Dictionary<string, object?>
            {
                ["source"] = "avrcp_raw", ["ownership_sink"] = "playing_after_first_bind",
                ["device_attribution"] = "learned_acl_handle_openditoo_preamble",
                ["target"] = options.Target,
                ["btvs_port"] = options.Port, ["lease"] = options.Lease is not null,
            });

            // BTVS's ETW session keeps buffering HCI while no consumer is attached and replays that backlog on
            // connect (observed: presses 20 minutes old). Nothing captured before this broker started is live.
            var startEpoch = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
            long stale = 0;
            Process? sink = null; // SMTC ownership sink starts once the Ditoo link is attributable (first bind)
            // BTVS is a GUI app: closing its window killed the capture and restarted the sidecar (Runtime 017 live).
            var btvs = Start(options.BtvsExe, ["-Mode", "Wireshark", "-Remote", "on", "-Port", options.Port.ToString(CultureInfo.InvariantCulture)],
                             hidden: true);
            var btvsHiddenLogged = false;
            // ETW real-time buffers otherwise reach BTVS only when full/timer-flushed: ~1.1-2.1 s input lag.
            int flushCode = -1, flushOk = 0;
            using var flusher = new Timer(_ =>
            {
                var code = EtwFlush.Flush();
                if (code == 0) Interlocked.Increment(ref flushOk); else Volatile.Write(ref flushCode, code);
            }, null, 200, 50);
            bool flushOkLogged = false, flushErrLogged = false;
            Thread.Sleep(800);

            // RFCOMM/AVCTP dissection is disabled so every channel stays raw btl2cap.payload whether BTVS saw
            // the L2CAP connect (fresh link/reconnect) or attached mid-connection (no PSM/address state).
            const string filter = "bthci_evt.code == 0x05 || " +
                "(bthci_acl.pb_flag == 0 && (btl2cap.payload contains 01:03:00:9f:a2:00:02 || " +
                "btl2cap.payload contains 01:04:00:bd:31:f2:00:02)) || " +
                "(bthci_acl.pb_flag == 2 && btl2cap.payload contains 11:0e:00:48:7c)";
            var tshark = Start(options.TsharkExe,
            [
                "-i", $"TCP@127.0.0.1:{options.Port}", "-l",
                "--disable-protocol", "btrfcomm", "--disable-protocol", "btavctp", "-Y", filter,
                "-T", "fields", "-E", "separator=/t", "-e", "frame.time_epoch", "-e", "bthci_acl.chandle",
                "-e", "bthci_acl.pb_flag", "-e", "bthci_evt.connection_handle", "-e", "btl2cap.payload"
            ], redirect: true);
            var binder = new HandleBinder();

            var deadline = options.Seconds == 0 ? DateTimeOffset.MaxValue : DateTimeOffset.UtcNow.AddSeconds(options.Seconds);
            // tshark announces "Capturing on ..." on stderr once connected to BTVS: the product waits for this
            // before its first session so that session's first frame (preamble A->B) binds the Ditoo handle.
            var stderrText = new System.Text.StringBuilder();
            var captureReady = 0;
            var readyLogged = false;
            tshark.ErrorDataReceived += (_, e) =>
            {
                if (e.Data is null) return;
                lock (stderrText) { if (stderrText.Length < 8192) stderrText.AppendLine(e.Data); }
                if (e.Data.StartsWith("Capturing on", StringComparison.Ordinal)) Volatile.Write(ref captureReady, 1);
            };
            tshark.BeginErrorReadLine();
            string Stderr() { lock (stderrText) return stderrText.ToString(); }
            var pendingLine = tshark.StandardOutput.ReadLineAsync();
            // Lease: the unelevated WSL supervisor rewrites this file with a changing counter every second. Content
            // (not mtime, WSL/Windows clocks can drift) unchanged for LeaseTimeout means the product is gone, so the
            // elevated sidecar must not linger holding media keys and BTVS.
            string? leaseSeen = ReadLease();
            var leaseChanged = DateTimeOffset.UtcNow;
            var leaseChecked = DateTimeOffset.UtcNow;
            while (DateTimeOffset.UtcNow < deadline)
            {
                if (DateTimeOffset.UtcNow - leaseChecked >= TimeSpan.FromSeconds(1))
                {
                    leaseChecked = DateTimeOffset.UtcNow;
                    // Belt and braces: BTVS may show its window despite SW_HIDE in STARTUPINFO; re-hide it.
                    btvs.Refresh();
                    var window = btvs.MainWindowHandle;
                    if (window != IntPtr.Zero && Win32.IsWindowVisible(window))
                    {
                        Win32.ShowWindow(window, 0); // SW_HIDE
                        if (!btvsHiddenLogged)
                        {
                            btvsHiddenLogged = true;
                            Write(writer, "btvs_window_hidden", new Dictionary<string, object?>());
                        }
                    }
                    if (options.Lease is not null)
                    {
                        var now = ReadLease();
                        if (now is not null && now != leaseSeen) { leaseSeen = now; leaseChanged = leaseChecked; }
                        else if (leaseChecked - leaseChanged > LeaseTimeout)
                        {
                            Write(writer, "broker_stopped", new Dictionary<string, object?> { ["reason"] = "lease_expired" });
                            return 0;
                        }
                    }
                }
                if (sink is { HasExited: true }) throw new IOException($"SMTC sink exited {sink.ExitCode}");
                if (!flushOkLogged && Volatile.Read(ref flushOk) > 0)
                {
                    flushOkLogged = true;
                    Write(writer, "etw_flush_ok", new Dictionary<string, object?> { ["session"] = EtwFlush.Session });
                }
                if (!flushErrLogged && Volatile.Read(ref flushOk) == 0 && Volatile.Read(ref flushCode) is > 0 and not 4201)
                {
                    flushErrLogged = true; // 4201 = session not created yet by BTVS
                    Write(writer, "etw_flush_error", new Dictionary<string, object?> { ["win32"] = flushCode });
                }
                if (!readyLogged && Volatile.Read(ref captureReady) == 1)
                {
                    readyLogged = true;
                    Write(writer, "capture_ready", new Dictionary<string, object?> { ["port"] = options.Port });
                }
                if (btvs.HasExited) throw new IOException($"BTVS exited {btvs.ExitCode}");
                if (tshark.HasExited)
                    throw new IOException($"tshark exited {tshark.ExitCode}: {Stderr()}");

                // Stay responsive even when no buttons are pressed. A blocking ReadLine would hide a
                // dead sink/BTVS indefinitely on an idle Ditoo and leave product telemetry falsely healthy.
                if (!pendingLine.Wait(250)) continue;
                var line = pendingLine.Result;
                if (line is null)
                    throw new IOException($"tshark stream ended: {Stderr()}");
                pendingLine = tshark.StandardOutput.ReadLineAsync();

                var columns = line.Split('\t');
                if (!double.TryParse(columns[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var captured))
                    continue;
                var seen = binder.Observe(columns);
                // ETW backlog (captured before this broker started): history may still teach or revoke the current
                // Ditoo handle (so a restarted broker re-binds without waiting for a frame), but never yields input.
                var backlog = captured < startEpoch;
                if (backlog)
                {
                    stale++;
                    if (seen.Change is not ("handle_bound" or "handle_unbound")) continue;
                }
                else if (stale > 0)
                {
                    Write(writer, "stale_backlog_dropped", new Dictionary<string, object?> { ["rows"] = stale });
                    stale = 0;
                }
                if (seen.Change == "handle_bound" && sink is null)
                    sink = Start(options.SinkExe, ["--seconds", "0", "--status", "playing", "--log", options.SinkLog]);
                if (seen.Change is not null)
                    // Runtime-only diagnostic in the private event log; never persisted into policy or code.
                    Write(writer, seen.Change, new Dictionary<string, object?>
                    {
                        ["source"] = "avrcp_raw_attribution", ["acl_handle"] = seen.Handle,
                        ["capture_time_epoch"] = columns[0], ["from_backlog"] = backlog,
                    });
                var decoded = seen.Input;
                if (decoded is null) continue;
                Write(writer, "event", new Dictionary<string, object?>
                {
                    ["source"] = "avrcp_raw", ["raw_button"] = decoded.RawButton,
                    ["operation"] = $"0x{decoded.Operation:X2}", ["normalized_candidate"] = decoded.Candidate,
                    ["capture_time_epoch"] = columns[0],
                });
            }
            Write(writer, "broker_stopped", new Dictionary<string, object?> { ["reason"] = "lifetime_complete" });
            return 0;
        }

        private static readonly TimeSpan LeaseTimeout = TimeSpan.FromSeconds(15);

        private string? ReadLease()
        {
            if (options.Lease is null) return null;
            try { return File.ReadAllText(options.Lease); }
            catch (IOException) { return null; }
            catch (UnauthorizedAccessException) { return null; }
        }

        private Process Start(string file, IReadOnlyList<string> args, bool redirect = false, bool hidden = false)
        {
            var psi = new ProcessStartInfo(file) { UseShellExecute = false, CreateNoWindow = true };
            if (hidden) psi.WindowStyle = ProcessWindowStyle.Hidden; // STARTF_USESHOWWINDOW + SW_HIDE for GUI apps
            foreach (var arg in args) psi.ArgumentList.Add(arg);
            if (redirect)
            {
                psi.RedirectStandardOutput = true;
                psi.RedirectStandardError = true;
            }
            var process = Process.Start(psi) ?? throw new IOException($"failed to start {Path.GetFileName(file)}");
            job.Add(process);
            children.Add(process);
            return process;
        }

        private void Write(StreamWriter writer, string type, Dictionary<string, object?> fields)
        {
            var row = new Dictionary<string, object?>
            {
                ["epoch"] = epoch, ["seq"] = ++seq, ["at_utc"] = DateTimeOffset.UtcNow.ToString("O"), ["type"] = type,
            };
            foreach (var item in fields) row[item.Key] = item.Value;
            writer.WriteLine(JsonSerializer.Serialize(row));
        }

        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            foreach (var child in children.AsEnumerable().Reverse())
            {
                try { if (!child.HasExited) child.Kill(entireProcessTree: true); } catch { }
                child.Dispose();
            }
            job.Dispose();
        }
    }

    internal static class Win32
    {
        [DllImport("user32.dll")] internal static extern bool ShowWindow(IntPtr window, int command);
        [DllImport("user32.dll")] internal static extern bool IsWindowVisible(IntPtr window);
    }

    /// <summary>Flush-only control of BTVS's real-time ETW session (name from btvs.exe); no start/stop/enable.</summary>
    internal static class EtwFlush
    {
        internal const string Session = "BTETWRTSession";
        private const int PropertiesSize = 120; // EVENT_TRACE_PROPERTIES, 64-bit layout

        internal static int Flush(string session = Session)
        {
            var size = PropertiesSize + 2048;
            var buffer = Marshal.AllocHGlobal(size);
            try
            {
                Marshal.Copy(new byte[size], 0, buffer, size);
                Marshal.WriteInt32(buffer, 0, size);          // Wnode.BufferSize
                Marshal.WriteInt32(buffer, 44, 0x00020000);   // Wnode.Flags = WNODE_FLAG_TRACED_GUID
                Marshal.WriteInt32(buffer, 116, PropertiesSize); // LoggerNameOffset
                return ControlTraceW(0, session, buffer, 3);  // EVENT_TRACE_CONTROL_FLUSH
            }
            finally { Marshal.FreeHGlobal(buffer); }
        }

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode)]
        private static extern int ControlTraceW(ulong traceHandle, string sessionName, IntPtr properties, uint controlCode);
    }

    private sealed class Job : IDisposable
    {
        private IntPtr handle;
        internal Job()
        {
            handle = CreateJobObject(IntPtr.Zero, null);
            if (handle == IntPtr.Zero) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            info.BasicLimitInformation.LimitFlags = 0x00002000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            var size = Marshal.SizeOf<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>();
            var ptr = Marshal.AllocHGlobal(size);
            try
            {
                Marshal.StructureToPtr(info, ptr, false);
                if (!SetInformationJobObject(handle, 9, ptr, (uint)size))
                    throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }
            finally { Marshal.FreeHGlobal(ptr); }
        }
        internal void Add(Process process)
        {
            if (!AssignProcessToJobObject(handle, process.Handle))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        }
        public void Dispose() { if (handle != IntPtr.Zero) { CloseHandle(handle); handle = IntPtr.Zero; } }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateJobObject(IntPtr attributes, string? name);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint length);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
        [DllImport("kernel32.dll")] private static extern bool CloseHandle(IntPtr handle);

        [StructLayout(LayoutKind.Sequential)] private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint PriorityClass, SchedulingClass;
        }
        [StructLayout(LayoutKind.Sequential)] private struct IO_COUNTERS
        {
            public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
            public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
        }
        [StructLayout(LayoutKind.Sequential)] private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
        }
    }
}

internal static class Selftest
{
    internal static int Run()
    {
        static void Need(bool ok, string name) { if (!ok) throw new Exception(name); }
        var cases = new (string Hex, byte Op, string Candidate)[]
        {
            ("90110e00487c4c00", 0x4C, "nav_left"),
            ("b0110e00487c4b00", 0x4B, "nav_right"),
            ("d0110e00487c4400", 0x44, "lever_candidate"),
            ("10110e00487c4600", 0x46, "lever_candidate"),
        };
        foreach (var item in cases)
        {
            var decoded = Program.DecodePayload(item.Hex);
            Need(decoded is not null && decoded.Operation == item.Op && decoded.Candidate == item.Candidate, $"decode_{item.Op:X2}");
        }
        Need(Program.DecodePayload("90110e00487ccc00") is null, "release_rejected");
        Need(Program.DecodePayload("92110e09487c4600") is null, "response_rejected");
        Need(Program.DecodePayload("90110100487c4600") is null, "foreign_profile_rejected");
        Need(Program.DecodePayload("garbage") is null, "garbage_rejected");

        // Handle binding over real tshark rows (RFCOMM UIH-wrapped preambles, raw AVCTP presses).
        var b = new Program.HandleBinder();
        Program.Observation See(string row) => b.Observe(row.Split('\t'));
        const string left = "90110e00487c4c00", a = "0bff0f010103009fa2000286", bb = "0bff1100010400bd31f2000286";
        Need(See($"1\t0x0100\t2\t\t{left}").Change == "ignored_unbound", "unbound_press_ignored");
        Need(See($"2\t0x0100\t0\t\t{bb}").Change is null && b.Bound is null, "b_without_a_not_bound");
        Need(See($"3\t0x0100\t2\t\t{a}").Change is null, "inbound_a_ignored");
        Need(See($"4\t0x0100\t0\t\t{bb}").Change is null && b.Bound is null, "inbound_a_does_not_arm");
        See($"5\t0x0200\t0\t\t{a}");
        Need(See($"6\t0x0100\t0\t\t{bb}").Change is null && b.Bound is null, "cross_handle_ab_rejected");
        See($"7\t0x0100\t0\t\t{a}");
        Need(See($"8\t0x0100\t0\t\t{bb}").Change == "handle_bound" && b.Bound == "0x0100", "bound");
        See($"9\t0x0100\t0\t\t{a}");
        Need(See($"10\t0x0100\t0\t\t{bb}").Change is null, "rebind_same_handle_silent");
        Need(See($"11\t0x0100\t2\t\t{left}").Input?.Candidate == "nav_left", "bound_press_accepted");
        Need(See($"12\t0x0100\t0\t\t{left}").Input is null, "outbound_press_rejected");
        Need(See($"13\t0x0100\t2\t\t90110e00487ccc00").Input is null, "bound_release_rejected");
        Need(See($"14\t0x0200\t2\t\td0110e00487c4400").Change == "ignored_foreign_handle", "foreign_press_ignored");
        Need(See($"14\t0x0200\t2\t\td0110e00487cc100").Change == "ignored_foreign_handle", "foreign_other_op_ignored");
        Need(See("15\t\t\t0x0200\t").Change is null && b.Bound == "0x0100", "foreign_disconnect_ignored");
        Need(See("16\t\t\t0x0100\t").Change == "handle_unbound" && b.Bound is null, "disconnect_unbinds");
        Need(See($"17\t0x0100\t2\t\t{left}").Input is null, "stale_handle_after_disconnect_rejected");
        See($"18\t0x0300\t0\t\t{a}");
        Need(See($"19\t0x0300\t0\t\t{bb}").Change == "handle_bound" && b.Bound == "0x0300", "rebind_after_reconnect");
        // ETW validates the properties layout before the name lookup: 4201 = accepted, missing session
        // (a broken layout returns 24/ERROR_BAD_LENGTH), independent of elevation.
        var etw = Program.EtwFlush.Flush("OpenDitooSelftestNoSuchSession");
        Need(etw == 4201, $"etw_flush_layout_{etw}");
        Console.WriteLine("RAW_AVRCP_BROKER_SELFTEST=PASS");
        return 0;
    }
}
