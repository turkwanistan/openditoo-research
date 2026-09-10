using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using OpenDitoo.Webcam.Probe;

namespace OpenDitoo.Webcam.Runner;

internal static class OfflineTests
{
    internal sealed class FakeHandler(string fault = "none") : HttpMessageHandler
    {
        internal int Opens, Attempts, Frames, Closes, Bytes;
        internal double LastStart = double.NegativeInfinity;
        private string id = "";
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token)
        {
            Trial.Require(request.RequestUri!.GetLeftPart(UriPartial.Authority) == TypedSession.Origin, "WRONG_ENDPOINT");
            var body = request.Content is null ? new JsonObject()
                : JsonNode.Parse(await request.Content.ReadAsStringAsync(token))!;
            object response;
            switch (request.RequestUri.AbsolutePath)
            {
                case "/v1/status":
                    // Match the real Host contract: /v1/status is a successful identity document
                    // but does not carry the POST command-result `ok` field.
                    response = new { target = Trial.Target, bind = "127.0.0.1", port = 8796,
                        activitySession = new { active = fault == "busy" }, diagnostics = new { operationInProgress = false } };
                    break;
                case "/v1/session/open":
                    Opens++;
                    Trial.Require(body["sessionProfile"]!.GetValue<string>() == Trial.Profile &&
                        body["minFrameIntervalMs"]!.GetValue<int>() == 40, "WRONG_OPEN_ENVELOPE");
                    id = body["experimentId"]!.GetValue<string>();
                    response = new { ok = true, sessionId = "offline", target = Trial.Target,
                        sessionProfile = fault == "profile" ? "activity" : Trial.Profile,
                        minFrameIntervalMs = 40, sendSpacingMs = 0 };
                    break;
                case "/v1/session/frame":
                    Attempts++;
                    Trial.Require(body["sessionId"]!.GetValue<string>() == "offline", "WRONG_SESSION");
                    Trial.Require(WebcamFrames.NowMs - LastStart >= Trial.HostFloor, "PACING_VIOLATION");
                    LastStart = WebcamFrames.NowMs;
                    var pixels = Convert.FromHexString(body["pixelsRgb888Hex"]!.GetValue<string>());
                    var encoded = DitooEncoder.EncodeRgb888(pixels);
                    var sha = DitooEncoder.Sha256Hex(encoded.Packet);
                    Trial.Require(body["expectedImagePacketSha256"]!.GetValue<string>() == sha, "ENCODER_HASH_DRIFT");
                    if (fault == "frame" && Attempts == 2) throw new IOException("SIMULATED_LOST_FRAME_RESPONSE");
                    var simulatedHostMs = fault == "fast_ack" ? 5 : 54;
                    await Task.Delay(fault == "fast_ack" ? 5 : 65, token);
                    Frames++; Bytes += encoded.Packet.Length + 15;
                    response = new { ok = true, imagePacketSha256 = fault == "hash" ? "wrong" : sha,
                        frame = Frames, packetCount = 3, packetsSentTotal = Frames * 3, txBytesSentTotal = Bytes,
                        ackPayloadHex = "0x44", hostFrameElapsedMs = simulatedHostMs };
                    break;
                case "/v1/session/close":
                    Closes++;
                    if (fault == "close") throw new IOException("SIMULATED_LOST_CLOSE_RESPONSE");
                    response = new { ok = true, socketClosed = true,
                        session = new { experimentId = id, sessionId = "offline", active = false,
                            terminalOutcome = "stopped_clean", terminalReason = "operator_stop" } };
                    break;
                default: throw new IOException("UNEXPECTED_TYPED_ROUTE");
            }
            return new(HttpStatusCode.OK) { Content = JsonContent.Create(response) };
        }
    }

    private sealed class GeneratedFrames(FakeHandler handler, string fault) : IFrameSource
    {
        public string? Fault => fault == "camera_before" || (fault == "camera_mid" && handler.Frames == 1)
            ? "camera_disconnected" : null;
        public bool TryTake(out TimedFrame frame)
        {
            var rgb = Enumerable.Repeat((byte)(handler.Frames % 255), 768).ToArray();
            frame = new(rgb, 16, 16, WebcamFrames.NowMs - (fault == "stale" ? 1000 : 0));
            return fault != "silent";
        }
        public void Wait(CancellationToken token) => token.WaitHandle.WaitOne(20);
    }

    internal static async Task<int> Run()
    {
        var failures = 0;
        foreach (var fault in new[] { "none", "camera_before", "camera_mid", "frame", "close", "profile", "hash", "busy", "stale", "silent" })
        {
            var handler = new FakeHandler(fault);
            using var session = new TypedSession(new HttpClient(handler));
            var result = JsonSerializer.SerializeToNode(await Sender.Run(new("OFFLINE", 1, 12, 12648),
                new GeneratedFrames(handler, fault), session, CancellationToken.None))!;
            var expected = fault switch
            {
                "camera_before" or "busy" => "not_opened",
                "frame" or "close" or "profile" or "hash" => "unknown",
                _ => "stopped_clean",
            };
            var expectedAttempts = fault switch
            {
                "camera_before" or "busy" or "profile" or "stale" or "silent" => 0,
                "camera_mid" or "hash" => 1,
                "frame" => 2,
                _ => handler.Attempts,
            };
            var passed = result["outcome"]!.GetValue<string>() == expected &&
                handler.Opens == (fault is "camera_before" or "busy" ? 0 : 1) &&
                handler.Closes == handler.Opens && handler.Attempts == expectedAttempts &&
                (fault != "none" || handler.Frames >= 5);
            if (!passed) failures++;
            Console.WriteLine($"ADAPTER_CASE_{(passed ? "PASS" : "FAIL")} name={fault} opens={handler.Opens} attempts={handler.Attempts} closes={handler.Closes} outcome={result["outcome"]}");
        }
        // W8 control: ACK returns far faster than the permanent 40 ms Host backstop. The
        // manifest-driven client floor must still keep dispatch starts legal without a 90 ms timer.
        var w8Handler = new FakeHandler("fast_ack");
        using (var w8Session = new TypedSession(new HttpClient(w8Handler)))
        {
            var w8 = JsonSerializer.SerializeToNode(await Sender.Run(
                new("OFFLINE-W8", 1, 26, 26 * Trial.WorstCaseFrameTxBytes, Trial.W8ClientInterval),
                new GeneratedFrames(w8Handler, "fast_ack"), w8Session, CancellationToken.None))!;
            var w8Pass = w8["outcome"]!.GetValue<string>() == "stopped_clean" &&
                w8["clientIntervalMs"]!.GetValue<int>() == 40 &&
                w8["frames"]!.GetValue<int>() >= 20 &&
                w8["duplicateSourceFrames"]!.GetValue<int>() == 0;
            if (!w8Pass) failures++;
            Console.WriteLine($"ADAPTER_W8_ACK_FLOOR_{(w8Pass ? "PASS" : "FAIL")} frames={w8["frames"]} client_interval_ms={w8["clientIntervalMs"]} outcome={w8["outcome"]}");
        }
        Console.WriteLine($"ADAPTER_SELFTEST_{(failures == 0 ? "PASS" : "FAIL")} failures={failures} device_io=false camera_io=false");
        return failures == 0 ? 0 : 2;
    }
}
