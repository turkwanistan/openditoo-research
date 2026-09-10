using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text.Json;
using OpenDitoo.Webcam.Probe;

namespace OpenDitoo.Webcam.Studio;

/// <summary>Framing the operator chose. Persisted locally; transform parameters only.</summary>
internal sealed record Framing(double Zoom = 1, double OffsetX = 0, double OffsetY = 0, bool Mirror = true, int QuarterTurns = 0)
{
    internal static readonly string PathOnDisk = System.IO.Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OpenDitoo", "webcam-framing.json");
    internal FrameTransform.Preset ToPreset() => FrameTransform.Default with
    { Zoom = Zoom, OffsetX = OffsetX, OffsetY = OffsetY, Mirror = Mirror, QuarterTurns = QuarterTurns };
    internal static Framing Load()
    {
        try { return JsonSerializer.Deserialize<Framing>(File.ReadAllText(PathOnDisk)) ?? new(); }
        catch { return new(); }
    }
    internal void Save()
    {
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(PathOnDisk)!);
        File.WriteAllText(PathOnDisk, JsonSerializer.Serialize(this));
    }
}

/// <summary>
/// Preview window. Left: the camera as the operator sees it, with the square ROI the transform
/// crops. Right: the exact 16x16 RGB888 frame the sender would transmit, pixel for pixel.
/// `sessionControl` is null in preview mode, so this window can never reach the Host on its own.
/// </summary>
internal sealed class StudioForm : Form
{
    private sealed class Canvas : Panel
    {
        internal Action<Graphics>? Draw;
        internal Canvas() { DoubleBuffered = true; BackColor = Color.Black; }
        protected override void OnPaint(PaintEventArgs e) { base.OnPaint(e); Draw?.Invoke(e.Graphics); }
    }

    private StudioCamera? camera;
    private Framing framing = Framing.Load();
    private readonly Canvas source = new() { Dock = DockStyle.Fill };
    private readonly Canvas matrix = new() { Dock = DockStyle.Fill };
    private readonly TrackBar zoom = new() { Minimum = 5, Maximum = 100, TickFrequency = 5, Dock = DockStyle.Fill };
    private readonly TrackBar offsetX = new() { Minimum = -100, Maximum = 100, TickFrequency = 25, Dock = DockStyle.Fill };
    private readonly TrackBar offsetY = new() { Minimum = -100, Maximum = 100, TickFrequency = 25, Dock = DockStyle.Fill };
    private readonly CheckBox mirror = new() { Text = "Mirror", AutoSize = true };
    private readonly Button rotate = new() { Text = "Rotate 90°", AutoSize = true };
    private readonly Button save = new() { Text = "Save framing", AutoSize = true };
    private readonly Button reset = new() { Text = "Reset", AutoSize = true };
    private readonly Button reconnect = new() { Text = "Reconnect camera", AutoSize = true, Enabled = false };
    private readonly Button stopButton = new() { Text = "Stop", AutoSize = true, Visible = false };
    private readonly Label cameraLabel = new() { AutoSize = true };
    private readonly Label statsLabel = new() { AutoSize = true };
    private readonly Label sessionLabel = new() { AutoSize = true, Font = new Font(SystemFonts.DefaultFont, FontStyle.Bold) };
    private readonly System.Windows.Forms.Timer tick = new() { Interval = 66 };
    private Bitmap? sourceBitmap;
    private readonly Bitmap matrixBitmap = new(16, 16, PixelFormat.Format24bppRgb);
    private long lastCaptured;
    private double lastTickMs;
    private double cameraFps;
    private string matrixSha = "";
    private readonly CancellationTokenSource? sessionStop;

    internal StudioCamera? Camera => camera;

    internal StudioForm(StudioCamera? camera, string title, CancellationTokenSource? sessionStop = null)
    {
        this.camera = camera;
        this.sessionStop = sessionStop;
        Text = title;
        ClientSize = new Size(980, 720);
        MinimumSize = new Size(640, 480);

        var views = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2 };
        views.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 58));
        views.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 42));
        views.Controls.Add(source, 0, 0);
        views.Controls.Add(matrix, 1, 0);

        var sliders = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, AutoSize = true };
        sliders.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        sliders.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        foreach (var (label, bar) in new[] { ("Zoom", zoom), ("Pan X", offsetX), ("Pan Y", offsetY) })
        {
            sliders.Controls.Add(new Label { Text = label, AutoSize = true, Anchor = AnchorStyles.Left });
            sliders.Controls.Add(bar);
        }
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
        buttons.Controls.AddRange([mirror, rotate, reset, save, reconnect, stopButton]);
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1 };
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        foreach (Control row in new Control[] { views, sliders, buttons, sessionLabel, cameraLabel, statsLabel })
        {
            if (row != views) root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            root.Controls.Add(row);
        }
        views.Dock = DockStyle.Fill;
        Controls.Add(root);

        ShowFraming();
        // The preview is drawn mirrored when the transform mirrors, so Pan X is flipped to keep
        // "slider right" meaning "box right" on screen, and toggling mirror keeps the box in place.
        zoom.ValueChanged += (_, _) => Apply(framing with { Zoom = zoom.Value / 100.0 });
        offsetX.ValueChanged += (_, _) => Apply(framing with { OffsetX = ScreenSign * offsetX.Value / 100.0 });
        offsetY.ValueChanged += (_, _) => Apply(framing with { OffsetY = offsetY.Value / 100.0 });
        mirror.CheckedChanged += (_, _) => Apply(framing with { Mirror = mirror.Checked, OffsetX = -framing.OffsetX });
        rotate.Click += (_, _) => Apply(framing with { QuarterTurns = (framing.QuarterTurns + 1) % 4 });
        reset.Click += (_, _) => { Apply(new Framing()); ShowFraming(); };
        save.Click += (_, _) =>
        {
            try { framing.Save(); sessionLabel.Text = "Framing saved to " + Framing.PathOnDisk; }
            catch (Exception ex) { sessionLabel.Text = "Save failed: " + ex.Message; }
        };
        reconnect.Click += async (_, _) => await Reconnect();
        if (sessionStop is not null)
        {
            stopButton.Visible = true;
            stopButton.Click += (_, _) => sessionStop.Cancel();
            FormClosing += (_, _) => sessionStop.Cancel(); // closing the window is a stop, never an abandon
        }
        sessionLabel.Text = sessionStop is null ? "PREVIEW ONLY — nothing is sent to the Ditoo" : "Waiting for the session to open";
        source.Draw = DrawSource;
        matrix.Draw = DrawMatrix;
        tick.Tick += (_, _) => Tick();
        tick.Start();
        Apply(framing);
    }

    internal void SetSessionStatus(string text)
    {
        if (IsHandleCreated) BeginInvoke(() => sessionLabel.Text = text);
    }

    private int ScreenSign => framing.Mirror ? -1 : 1;

    private void ShowFraming()
    {
        showing = true;
        mirror.Checked = framing.Mirror;
        zoom.Value = (int)Math.Round(Math.Clamp(framing.Zoom, 0.05, 1) * 100);
        offsetX.Value = (int)Math.Round(Math.Clamp(ScreenSign * framing.OffsetX, -1, 1) * 100);
        offsetY.Value = (int)Math.Round(Math.Clamp(framing.OffsetY, -1, 1) * 100);
        showing = false;
    }

    private bool showing;

    private void Apply(Framing next)
    {
        if (showing) return; // control values are being set from `framing`, not by the operator
        framing = next;
        if (camera is not null) camera.Preset = framing.ToPreset();
    }

    internal async Task Reconnect()
    {
        reconnect.Enabled = false;
        cameraLabel.Text = "Reconnecting camera…";
        try
        {
            // The camera lives in the MTA only: a MediaCapture created on this STA thread cannot be
            // disposed from any other thread (RPC_E_WRONG_THREAD on exit).
            var old = camera;
            camera = null;
            if (old is not null) await Task.Run(() => old.DisposeAsync().AsTask());
            var preset = framing.ToPreset();
            camera = await Task.Run(() => StudioCamera.Open(preset));
        }
        catch (Exception ex) { cameraLabel.Text = "Camera unavailable: " + ex.Message; reconnect.Enabled = true; }
    }

    private void Tick()
    {
        var now = WebcamFrames.NowMs;
        if (camera is null) { source.Invalidate(); return; }
        if (camera.Fault is { } fault)
        {
            cameraLabel.Text = $"Camera FAULT: {fault}";
            // In a live session the sender owns the reaction (it stops cleanly). Reconnect is preview-only.
            reconnect.Enabled = sessionStop is null;
        }
        else if (lastTickMs > 0 && now - lastTickMs > 500)
        {
            cameraFps = (camera.Captured - lastCaptured) * 1000 / (now - lastTickMs);
            lastCaptured = camera.Captured;
            lastTickMs = now;
            cameraLabel.Text = $"{camera.Name} — {camera.Mode} — measured {cameraFps:F1} fps delivered";
        }
        else if (lastTickMs == 0) { lastTickMs = now; lastCaptured = camera.Captured; }
        var transform = System.Text.Json.JsonSerializer.SerializeToElement(camera.TransformMs.Snapshot());
        var roi = RoiText();
        statsLabel.Text = $"ROI {roi}  mirror={framing.Mirror}  rotation={framing.QuarterTurns * 90}°  " +
            $"transform p95 {transform.GetProperty("p95").GetDouble():F2} ms  packet sha256 {matrixSha}";
        source.Invalidate();
        matrix.Invalidate();
    }

    private string RoiText()
    {
        var frame = camera?.LatestSource;
        if (frame is not { } f) return "-";
        var (top, left, side) = FrameTransform.SquareRoi(f.Height, f.Width, framing.ToPreset());
        return $"{side}x{side} at ({left},{top}) of {f.Width}x{f.Height}";
    }

    private void DrawSource(Graphics g)
    {
        if (camera?.LatestSource is not { } frame) { g.DrawString("No camera frame", Font, Brushes.White, 8, 8); return; }
        if (sourceBitmap is null || sourceBitmap.Width != frame.Width || sourceBitmap.Height != frame.Height)
        {
            sourceBitmap?.Dispose();
            sourceBitmap = new Bitmap(frame.Width, frame.Height, PixelFormat.Format32bppRgb);
        }
        var data = sourceBitmap.LockBits(new Rectangle(0, 0, frame.Width, frame.Height), ImageLockMode.WriteOnly, PixelFormat.Format32bppRgb);
        for (var y = 0; y < frame.Height; y++)
            Marshal.Copy(frame.Pixels, y * frame.Width * 4, data.Scan0 + y * data.Stride, frame.Width * 4);
        sourceBitmap.UnlockBits(data);
        var scale = Math.Min((float)source.Width / frame.Width, (float)source.Height / frame.Height);
        var target = new RectangleF(0, 0, frame.Width * scale, frame.Height * scale);
        var state = g.Save();
        if (framing.Mirror) { g.TranslateTransform(target.Width, 0); g.ScaleTransform(-1, 1); }
        g.DrawImage(sourceBitmap, target);
        var (top, left, side) = FrameTransform.SquareRoi(frame.Height, frame.Width, framing.ToPreset());
        using var pen = new Pen(Color.Lime, 2);
        g.DrawRectangle(pen, left * scale, top * scale, side * scale, side * scale);
        g.Restore(state);
    }

    private void DrawMatrix(Graphics g)
    {
        if (camera?.LatestMatrix is not { } frame) return;
        var data = matrixBitmap.LockBits(new Rectangle(0, 0, 16, 16), ImageLockMode.WriteOnly, PixelFormat.Format24bppRgb);
        var row = new byte[16 * 3];
        for (var y = 0; y < 16; y++)
        {
            for (var x = 0; x < 16; x++) // RGB888 -> GDI's BGR
            {
                var i = (y * 16 + x) * 3;
                row[x * 3] = frame.Pixels[i + 2]; row[x * 3 + 1] = frame.Pixels[i + 1]; row[x * 3 + 2] = frame.Pixels[i];
            }
            Marshal.Copy(row, 0, data.Scan0 + y * data.Stride, row.Length);
        }
        matrixBitmap.UnlockBits(data);
        matrixSha = DitooEncoder.Sha256Hex(DitooEncoder.EncodeRgb888(frame.Pixels).Packet)[..12];
        var side = Math.Min(matrix.Width, matrix.Height) - 8;
        g.InterpolationMode = InterpolationMode.NearestNeighbor;
        g.PixelOffsetMode = PixelOffsetMode.Half;
        g.DrawImage(matrixBitmap, new Rectangle(4, 4, side, side));
        using var grid = new Pen(Color.FromArgb(60, 0, 0, 0));
        for (var i = 1; i < 16; i++)
        {
            var p = 4 + i * side / 16f;
            g.DrawLine(grid, p, 4, p, 4 + side);
            g.DrawLine(grid, 4, p, 4 + side, p);
        }
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        tick.Stop();
        base.OnFormClosed(e);
    }
}
