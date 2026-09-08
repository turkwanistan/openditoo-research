using System.Security.Cryptography;

namespace OpenDitoo.Day1.Host.Internal;

// Exact, stock-observed Day-1 M4 application contract.
// This type performs no I/O and is intentionally not referenced by Program.cs.
internal static class DitooM4FileVersionProtocol
{
    internal const string TargetMac = "11:75:58:CE:DE:C7";
    internal const ulong TargetBluetoothAddress = 0x117558CEDEC7;
    internal const uint TargetRfcommChannel = 1;

    internal const int ConnectBudgetMs = 15_000;
    internal const int ResponseBudgetMs = 5_000;
    internal const int TotalBudgetMs = 20_000;
    internal const int MaxResponseWireBytes = 13;
    internal const int ExpectedInstalledVersion = 42012;

    internal static readonly byte[] Request = Convert.FromHexString("01040097009B0002");
    internal static readonly byte[] StockObservedResponse = Convert.FromHexString("010900049755001CA400B90102");
    internal const string RequestSha256 = "6260dc0995cdaa13dadd614eb7f25b5b9ecf4c8a555f6da96bc84c62b5c31780";
    internal const string StockObservedResponseSha256 = "d312a0a59165ca6c65aaa156465b3d3ad84acc4af7ef70bfc75a7338de800cc0";

    internal static void VerifyFrozenConstants()
    {
        if (Request.Length != 8 || !Convert.ToHexString(Request).Equals("01040097009B0002", StringComparison.Ordinal))
            throw new InvalidOperationException("M4_REQUEST_DRIFT");
        if (Convert.ToHexString(SHA256.HashData(Request)).ToLowerInvariant() != RequestSha256)
            throw new InvalidOperationException("M4_REQUEST_HASH_DRIFT");
        if (StockObservedResponse.Length != MaxResponseWireBytes)
            throw new InvalidOperationException("M4_STOCK_RESPONSE_LENGTH_DRIFT");
        if (Convert.ToHexString(SHA256.HashData(StockObservedResponse)).ToLowerInvariant() != StockObservedResponseSha256)
            throw new InvalidOperationException("M4_STOCK_RESPONSE_HASH_DRIFT");
        if (ConnectBudgetMs + ResponseBudgetMs != TotalBudgetMs)
            throw new InvalidOperationException("M4_BUDGET_DRIFT");
    }

    internal static int ValidateAndDecodeVersion(ReadOnlySpan<byte> wire)
    {
        VerifyFrozenConstants();
        if (wire.Length != MaxResponseWireBytes)
            throw new InvalidOperationException($"M4_RESPONSE_LENGTH_REJECTED COUNT={wire.Length} EXPECTED={MaxResponseWireBytes}");
        if (wire[0] != 0x01 || wire[^1] != 0x02)
            throw new InvalidOperationException("M4_RESPONSE_BOUNDARY_REJECTED");

        var innerLength = wire[1] | (wire[2] << 8);
        if (innerLength != 9 || wire.Length != innerLength + 4)
            throw new InvalidOperationException($"M4_RESPONSE_INNER_LENGTH_REJECTED VALUE={innerLength}");

        var checksumIndex = 3 + innerLength - 2;
        ushort sum = 0;
        for (var i = 1; i < checksumIndex; i++)
            sum = unchecked((ushort)(sum + wire[i]));
        var observedChecksum = (ushort)(wire[checksumIndex] | (wire[checksumIndex + 1] << 8));
        if (sum != observedChecksum)
            throw new InvalidOperationException($"M4_RESPONSE_CHECKSUM_REJECTED OBSERVED=0x{observedChecksum:X4} EXPECTED=0x{sum:X4}");

        if (wire[3] != 0x04 || wire[4] != 0x97 || wire[5] != 0x55)
            throw new InvalidOperationException("M4_RESPONSE_WRAPPER_REJECTED");
        if (wire[6] != 0x00)
            throw new InvalidOperationException($"M4_RESPONSE_SELECTOR_REJECTED VALUE=0x{wire[6]:X2}");

        var version = wire[7] | (wire[8] << 8);
        if (version != ExpectedInstalledVersion)
            throw new InvalidOperationException($"M4_RESPONSE_VERSION_MISMATCH VALUE={version} EXPECTED={ExpectedInstalledVersion}");

        // wire[9] is preserved as observed but deliberately has no promoted semantic.
        return version;
    }
}
