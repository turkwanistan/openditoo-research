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

    private sealed record Options(string Target, string Events, string SinkLog, string SinkExe,
                                  string BtvsExe, string TsharkExe, int Port, int Seconds)
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
            return new(Need("--target"), Need("--events"), Need("--sink-log"), Need("--sink-exe"),
                       Need("--btvs"), Need("--tshark"), port, seconds);
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
            using var writer = new StreamWriter(options.Events, append: true) { AutoFlush = true };
            Write(writer, "broker_started", new Dictionary<string, object?>
            {
                ["source"] = "avrcp_raw", ["ownership_sink"] = "playing", ["device_attribution"] = "acl_source_address",
                ["btvs_port"] = options.Port,
            });

            var sink = Start(options.SinkExe, ["--seconds", "0", "--status", "playing", "--log", options.SinkLog]);
            var btvs = Start(options.BtvsExe, ["-Mode", "Wireshark", "-Remote", "on", "-Port", options.Port.ToString(CultureInfo.InvariantCulture)]);
            Thread.Sleep(800);

            var filter = $"bthci_acl.src.bd_addr == {options.Target} && (" +
                         "btl2cap.payload contains 11:0e:00:48:7c:4b:00 || " +
                         "btl2cap.payload contains 11:0e:00:48:7c:4c:00 || " +
                         "btl2cap.payload contains 11:0e:00:48:7c:44:00 || " +
                         "btl2cap.payload contains 11:0e:00:48:7c:46:00)";
            var tshark = Start(options.TsharkExe,
            [
                "-i", $"TCP@127.0.0.1:{options.Port}", "-l", "-Y", filter,
                "-T", "fields", "-E", "separator=\\t", "-e", "frame.time_epoch", "-e", "btl2cap.payload"
            ], redirect: true);

            var deadline = options.Seconds == 0 ? DateTimeOffset.MaxValue : DateTimeOffset.UtcNow.AddSeconds(options.Seconds);
            var stderr = tshark.StandardError.ReadToEndAsync();
            var pendingLine = tshark.StandardOutput.ReadLineAsync();
            while (DateTimeOffset.UtcNow < deadline)
            {
                if (sink.HasExited) throw new IOException($"SMTC sink exited {sink.ExitCode}");
                if (btvs.HasExited) throw new IOException($"BTVS exited {btvs.ExitCode}");
                if (tshark.HasExited)
                    throw new IOException($"tshark exited {tshark.ExitCode}: {(stderr.IsCompletedSuccessfully ? stderr.Result : string.Empty)}");

                // Stay responsive even when no buttons are pressed. A blocking ReadLine would hide a
                // dead sink/BTVS indefinitely on an idle Ditoo and leave product telemetry falsely healthy.
                if (!pendingLine.Wait(250)) continue;
                var line = pendingLine.Result;
                if (line is null)
                    throw new IOException($"tshark stream ended: {(stderr.IsCompletedSuccessfully ? stderr.Result : string.Empty)}");
                pendingLine = tshark.StandardOutput.ReadLineAsync();

                var columns = line.Split('\t');
                var decoded = DecodePayload(columns.Length > 1 ? columns[^1] : columns[0]);
                if (decoded is null) continue;
                Write(writer, "event", new Dictionary<string, object?>
                {
                    ["source"] = "avrcp_raw", ["raw_button"] = decoded.RawButton,
                    ["operation"] = $"0x{decoded.Operation:X2}", ["normalized_candidate"] = decoded.Candidate,
                    ["capture_time_epoch"] = columns.Length > 1 ? columns[0] : null,
                });
            }
            Write(writer, "broker_stopped", new Dictionary<string, object?> { ["reason"] = "lifetime_complete" });
            return 0;
        }

        private Process Start(string file, IReadOnlyList<string> args, bool redirect = false)
        {
            var psi = new ProcessStartInfo(file) { UseShellExecute = false, CreateNoWindow = true };
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
        Console.WriteLine("RAW_AVRCP_BROKER_SELFTEST=PASS");
        return 0;
    }
}
