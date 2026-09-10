using System.Text.Json;

namespace OpenDitoo.ButtonProbe;

public static class Selftest
{
    public static int Run()
    {
        var failures = new List<string>();
        void Check(bool ok, string name) { if (!ok) failures.Add(name); }

        Check(Normalize.Smtc("Previous") == "nav_left", "smtc previous");
        Check(Normalize.Smtc("Next") == "nav_right", "smtc next");
        Check(Normalize.Smtc("Play") == "lever_candidate" && Normalize.Smtc("Pause") == "lever_candidate", "smtc play/pause");
        Check(Normalize.Smtc("Stop") == null && Normalize.Smtc("FastForward") == null, "smtc unknown stays unknown");
        Check(Normalize.AppCommand(12) == "nav_left" && Normalize.AppCommand(11) == "nav_right", "appcommand arrows");
        Check(Normalize.AppCommand(14) == "lever_candidate" && Normalize.AppCommand(46) == "lever_candidate"
              && Normalize.AppCommand(47) == "lever_candidate", "appcommand lever");
        Check(Normalize.AppCommand(8) == null, "appcommand volume stays unknown");
        Check(Normalize.MediaVk(0xB1) == "nav_left" && Normalize.MediaVk(0xB0) == "nav_right"
              && Normalize.MediaVk(0xB3) == "lever_candidate" && Normalize.MediaVk(0xB2) == null, "media vk");
        for (int vk = 0; vk < 256; vk++)
            if (Normalize.IsMediaVk(vk) != (vk is >= 0xB0 and <= 0xB3)) Check(false, $"keyboard privacy filter vk {vk:X2}");

        // Sequence: strictly increasing, gapless, and unique under concurrent callbacks.
        var sink = new StringWriter();
        var log = new NdjsonLog(sink);
        Parallel.For(0, 500, i => log.Event("smtc", "Next", "nav_right"));
        var seqs = sink.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Select(line => JsonDocument.Parse(line).RootElement.GetProperty("seq").GetInt64()).ToList();
        Check(seqs.SequenceEqual(Enumerable.Range(1, 500).Select(i => (long)i)), "seq monotonic and gapless in file order");

        // Epoch changes on every process/logger start.
        Check(new NdjsonLog().Epoch != new NdjsonLog().Epoch, "epoch changes on restart");

        // Two sources reporting the same logical button stay two records: nothing is merged.
        var both = new StringWriter();
        var twin = new NdjsonLog(both);
        twin.Event("smtc", "Next", Normalize.Smtc("Next"));
        twin.Event("wm_appcommand", "APPCOMMAND_11", Normalize.AppCommand(11));
        var records = both.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Select(line => JsonDocument.Parse(line).RootElement).ToList();
        Check(records.Count == 2 && records[0].GetProperty("source").GetString() == "smtc"
              && records[1].GetProperty("source").GetString() == "wm_appcommand", "sources stay separate");
        Check(records.All(r => r.TryGetProperty("at_utc", out _) && r.TryGetProperty("at_monotonic_ms", out _)
                               && r.TryGetProperty("epoch", out _)), "record fields");

        foreach (var failure in failures) Console.WriteLine($"FAIL {failure}");
        Console.WriteLine(failures.Count == 0 ? "BUTTONPROBE_SELFTEST=PASS" : $"BUTTONPROBE_SELFTEST=FAIL {failures.Count}");
        return failures.Count == 0 ? 0 : 1;
    }
}
