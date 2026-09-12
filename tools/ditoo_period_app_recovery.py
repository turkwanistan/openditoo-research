#!/usr/bin/env python3
"""Offline audit of the preserved 2021-era Divoom Android updater/recovery surface.

Recognition/provenance only.  This tool never contacts a server, opens a device
transport, emits device packets, mutates firmware, or constructs an installable image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APK = ROOT / "artifacts/apps/divoom_android_3.1.58.apk"
APK_PROV = ROOT / "artifacts/provenance/divoom_android_3.1.58.json"
PERIOD_MATRIX = ROOT / "artifacts/provenance/period_apptest_v3_matrix_2026-09-12.json"
CURRENT_MATRIX = ROOT / "artifacts/provenance/getupdatefile_v2_v3_matrix_2026-09-12.json"

EXPECTED = {
    "size": 41427089,
    "md5": "d60c7560aee69bffb60ae925b7bbf6fc",
    "sha1": "ac5158aad4a88f56772c5180887697d5c5b9415c",
    "sha256": "c690ba9aad29811eb7b007d31b593999e1ba937b7d247ff09fdcc4ec57d67082",
    "signer_sha1": "eeb353cb9bc057f8abd82cfc36f483d745ff9dd0",
    "signer_sha256": "b54bda23c5c9239bb80a0581220f2d46c3f59962c3ec52e692202e65b5ac0955",
}

STRING_WITNESSES = {
    "get_update_v3": b"GetUpdateFileV3",
    "firmware_test_pref": b"com.divoom.DIVOOM.SP_TEST_VERSION",
    "server_test_pref": b"com.divoom.DIVOOM.SP_TEST_SERVER",
    "period_prod_https": b"https://app.divoom-gz.com",
    "period_test_https": b"https://apptest.divoom-gz.com",
    "firmware_cdn_https": b"https://f.divoom-gz.com",
    "hardware_json_field": b"Hardware",
    "is_test_json_field": b"IsTest",
    "language_json_field": b"Language",
    "update_flag_json_field": b"UpdateFlag",
}


def _hashes(data: bytes) -> dict[str, Any]:
    return {
        "size_bytes": len(data),
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _signer(rsa: bytes) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as td_s:
        td = Path(td_s)
        sig = td / "sig.der"
        cert = td / "cert.pem"
        sig.write_bytes(rsa)
        pem = subprocess.check_output(
            ["openssl", "pkcs7", "-inform", "DER", "-in", str(sig), "-print_certs"]
        )
        cert.write_bytes(pem)
        subject = subprocess.check_output(
            ["openssl", "x509", "-in", str(cert), "-noout", "-subject"], text=True
        ).strip()
        sha1 = subprocess.check_output(
            ["openssl", "x509", "-in", str(cert), "-noout", "-fingerprint", "-sha1"], text=True
        ).strip().split("=", 1)[1].replace(":", "").lower()
        sha256 = subprocess.check_output(
            ["openssl", "x509", "-in", str(cert), "-noout", "-fingerprint", "-sha256"], text=True
        ).strip().split("=", 1)[1].replace(":", "").lower()
    return {"subject": subject, "sha1": sha1, "sha256": sha256}


def _matrix_object_map(rows: list[dict[str, Any]]) -> dict[tuple[int, bool], tuple[Any, ...]]:
    out = {}
    for row in rows:
        req, resp = row["request"], row["response"]
        out[(int(req["Hardware"]), bool(req["IsTest"]))] = (
            resp.get("FileId"), resp.get("Version"), resp.get("Sha1"), resp.get("Explain")
        )
    return out


def build_report() -> dict[str, Any]:
    data = APK.read_bytes()
    h = _hashes(data)
    if h != {
        "size_bytes": EXPECTED["size"],
        "md5": EXPECTED["md5"],
        "sha1": EXPECTED["sha1"],
        "sha256": EXPECTED["sha256"],
    }:
        raise ValueError(f"period APK identity drift: {h}")

    with zipfile.ZipFile(APK) as z:
        bad = z.testzip()
        if bad is not None:
            raise ValueError(f"period APK ZIP corruption at {bad}")
        manifest = z.read("AndroidManifest.xml")
        rsa = z.read("META-INF/GOOGPLAY.RSA")
        dex_names = [n for n in z.namelist() if re.fullmatch(r"classes\d*\.dex", n)]
        dex = b"".join(z.read(n) for n in dex_names)

    signer = _signer(rsa)
    if signer["sha1"] != EXPECTED["signer_sha1"] or signer["sha256"] != EXPECTED["signer_sha256"]:
        raise ValueError(f"period APK signer drift: {signer}")

    prov = json.loads(APK_PROV.read_text())
    if prov["sha256"] != EXPECTED["sha256"] or not prov["acceptance"]["accepted_for_offline_archaeology"]:
        raise ValueError("period APK provenance record drift")
    if prov["acceptance"].get("historical_revoom_sha1") != EXPECTED["sha1"] or not prov["acceptance"].get("historical_revoom_sha1_matches"):
        raise ValueError("period APK historical REvoom identity witness drift")

    period = json.loads(PERIOD_MATRIX.read_text())
    current = json.loads(CURRENT_MATRIX.read_text())
    if not period.get("no_bruteforce") or len(period.get("rows", [])) != 4:
        raise ValueError("period test-server matrix scope drift")
    current_v3 = [r for r in current["rows"] if r["endpoint"] == "GetUpdateFileV3"]
    same_objects = _matrix_object_map(period["rows"]) == _matrix_object_map(current_v3)
    if not same_objects:
        raise ValueError("period test-server firmware objects no longer match captured current V3 matrix")

    witnesses = {name: needle in dex for name, needle in STRING_WITNESSES.items()}
    if not all(witnesses.values()):
        raise ValueError(f"period APK updater string witness drift: {witnesses}")

    negatives = {
        "get_update_v2_string_absent": b"GetUpdateFileV2" not in dex,
        "divoomupdate_filename_string_absent": b"divoomupdate" not in dex.lower(),
    }
    if not all(negatives.values()):
        raise ValueError(f"period APK negative string witness drift: {negatives}")

    return {
        "schema_version": 1,
        "kind": "period_divoom_android_recovery_surface",
        "ok": True,
        "safety": {
            "offline_analysis": True,
            "device_io": False,
            "packet_generation": False,
            "firmware_mutation": False,
            "installation_authorized": False,
        },
        "apk": {
            "path": str(APK.relative_to(ROOT)),
            **h,
            "zip_integrity_ok": True,
            "manifest_package_utf16_witness": "com.divoom.Divoom".encode("utf-16le") in manifest,
            "manifest_version_utf16_witness": "3.1.58".encode("utf-16le") in manifest,
            "dex_members": dex_names,
            "signer": signer,
            "signer_matches_independent_apkmirror_oracle": True,
            "sha1_matches_historical_revoom_oracle": True,
        },
        "raw_apk_witnesses": witnesses,
        "raw_apk_negative_witnesses": negatives,
        "period_test_backend": {
            "matrix_path": str(PERIOD_MATRIX.relative_to(ROOT)),
            "request_count": len(period["rows"]),
            "bounded_no_bruteforce": period["no_bruteforce"],
            "same_firmware_objects_as_current_v3_matrix": same_objects,
            "versions": {
                f"{r['request']['Hardware']}_{'test' if r['request']['IsTest'] else 'prod'}": r["response"].get("Version")
                for r in period["rows"]
            },
        },
        "decompilation_observations": {
            "method": "apktool 2.5.0-dirty in disposable OptiPlex Lab; observations below are tied to the pinned APK hash and class/method identifiers",
            "request_schema": "GetUpdateFileRequest fields Hardware, IsTest, Language, UpdateFlag; BaseRequestJson contributes DeviceId; constructor initializes UpdateFlag=2",
            "single_firmware_request_site": "com.divoom.Divoom.bluetooth.s.c.o(I): Hardware=input/1000; Language CN/EN; IsTest=GlobalApplication.A(); BaseParams.postRx('GetUpdateFileV3', request, GetUpdateFileResponse)",
            "update_flag_override_callers": 0,
            "test_version_pref": "utils.y.u()/l0(Z) read/write com.divoom.DIVOOM.SP_TEST_VERSION; AboutTestFragment toggles it through GlobalApplication.N(Z)",
            "test_server_pref": "utils.y.t()/k0(Z) read/write com.divoom.DIVOOM.SP_TEST_SERVER; GlobalApplication.q() selects app.divoom-gz.com vs apptest.divoom-gz.com",
            "hidden_test_ui": "fragment_about_test.xml exposes literal test/formal firmware-version and test/formal server switches; About-page date entry is gated by account test flag, manager flag, or a fixed developer-account allowlist",
            "response_schema": "GetUpdateFileResponse has only FileId, Version, Sha1, Explain",
            "download_path": "UpdateFileService passes FileId to BaseParams download helper; OkHttpUtils.checkDownLoadPath prefixes GlobalApplication.f(), the f.divoom-gz.com firmware CDN base, and SHA-1 is verified before update processing",
            "no_app_manual_sd_recovery_string": "No divoomupdate filename string was found in the decoded APK; the 2022 divoomupdate.bin SD package remains support-channel evidence outside this app path",
        },
        "conclusion": {
            "status": "PERIOD_APP_NO_HISTORICAL_OR_RECOVERY_SELECTOR_FOUND",
            "firmware_test_branch_selector": True,
            "separate_test_server_selector": True,
            "historical_version_selector": False,
            "caller_settable_update_flag_in_period_app": False,
            "current_legacy_test_backend_yields_older_v42012": False,
            "exact_v42012_recovered": False,
            "support_sd_package_recovered": False,
            "summary": "The verified 2021-era app exposes developer/test selection, not arbitrary or historical firmware selection. Its still-live legacy test backend currently resolves to the same latest production/test objects as the modern bounded V3 matrix.",
        },
        "scope_limit": "One provenance-strong 2021-era app (3.1.58) was decompiled. This does not formally prove every older app/support backend lacked other behavior, nor reconstruct the historical state of apptest.divoom-gz.com. Failure to recover v42012/divoomupdate.bin is not proof those bytes were never distributed.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", type=Path)
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    report = build_report()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text)
    if args.json:
        print(text, end="")
    if args.selfcheck:
        print("DITOO_PERIOD_APP_RECOVERY=PASS")
        print("PERIOD_APP_VERSION=3.1.58")
        print("PERIOD_TEST_BACKEND_OBJECTS_MATCH_CURRENT_V3=true")
        print("SFR2=PERIOD_APP_NO_HISTORICAL_OR_RECOVERY_SELECTOR_FOUND")
    if not (args.json or args.write or args.selfcheck):
        print("DITOO_PERIOD_APP_RECOVERY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
