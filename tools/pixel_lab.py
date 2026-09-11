#!/usr/bin/env python3
"""Offline review workbench for literal OpenDitoo 16x16 art and ACK-driven animation."""
from __future__ import annotations

import argparse
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from host.pixel_art import (SPRITE_SCHEMA, PixelArtError, contact_sheet, geometry, load_sprite,
                            png_bytes, write_png)
from host.pixel_animation import (ANIMATION_SCHEMA, CADENCE_PROFILES, AckAnimationPlayer,
                                  animation_quality, cadence_intervals, load_animation)

DEFAULT_REVIEW_ROOT = ROOT / ".openditoo-local" / "pixel-lab" / "reviews"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_path(path: Path) -> str:
    """Project-relative provenance when possible; never bake sandbox mount paths into bundles."""
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def schema(path: Path) -> str:
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("schema") or "")
    except Exception as exc:
        raise PixelArtError(f"{path}: cannot read JSON: {exc}") from exc


def load_any(path: Path):
    kind = schema(path)
    if kind == SPRITE_SCHEMA:
        return "sprite", load_sprite(path)
    if kind == ANIMATION_SCHEMA:
        return "animation", load_animation(path)
    raise PixelArtError(f"{path}: unsupported pixel-lab schema {kind!r}")


def sprite_record(sprite) -> dict:
    return {
        "id": sprite.id, "source": stable_path(sprite.source_path) if sprite.source_path else None,
        "canonical_sha256": sprite.canonical_sha256, "rgb888_sha256": sprite.rgb_sha256,
        "palette": {k: list(v) for k, v in sprite.palette.items()}, "rows": list(sprite.rows),
        "anchor": None if sprite.anchor is None else list(sprite.anchor), "geometry": geometry(sprite),
    }


def quality_for_sprite(sprite) -> dict:
    metrics = geometry(sprite)
    warnings = []
    if metrics["edge_touches"]:
        warnings.append({"code": "EDGE_TOUCH", "edges": metrics["edge_touches"]})
    if metrics["single_pixel_islands"]:
        warnings.append({"code": "SINGLE_PIXEL_ISLANDS", "count": metrics["single_pixel_islands"]})
    return {"structural": "PASS", "geometry": metrics, "warnings": warnings}


def animation_records(animation) -> tuple[list[dict], list[dict]]:
    unique = animation.unique_frames()
    frames = [sprite_record(sprite) for sprite in unique]
    ref_to_hash = {ref: sprite.rgb_sha256 for ref, sprite in animation.sprites.items()}
    sequence = []
    for index, step in enumerate(animation.steps):
        sprite = animation.sprites[step.sprite_ref]
        sequence.append({"step": index, "sprite_ref": step.sprite_ref, "sprite_id": sprite.id,
                         "rgb888_sha256": ref_to_hash[step.sprite_ref],
                         "hold_acks": step.hold_acks, "phase": step.phase})
    return frames, sequence


def make_contact_png(frames: list[bytes], path: Path, scale: int = 12) -> None:
    rgb, width, height = contact_sheet(frames, scale=scale)
    path.write_bytes(png_bytes(rgb, width, height))


def html_document(title: str, frame_records: list[dict], sequence: list[dict], *, loop: bool) -> str:
    payload = json.dumps({"title": title, "frames": frame_records, "sequence": sequence,
                          "loop": loop, "profiles": CADENCE_PROFILES}, separators=(",", ":"))
    return f"""<!doctype html>
<meta charset='utf-8'><title>{title}</title>
<style>
body{{background:#111;color:#eee;font:14px system-ui;margin:18px}} button,select{{margin:3px;padding:6px}}
#stage{{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}} canvas{{image-rendering:pixelated;background:#000;border:1px solid #555}}
pre{{max-width:900px;white-space:pre-wrap}} .sw{{display:inline-block;width:18px;height:18px;border:1px solid #777;margin:2px}}
</style>
<h2>{title}</h2><div>
<button id='play'>Pause</button><button id='prev'>◀ Step</button><button id='next'>Step ▶</button>
<label>Cadence <select id='cadence'></select></label><label><input id='grid' type='checkbox'> grid</label>
<label><input id='mirror' type='checkbox'> mirror</label><button id='restart'>Restart</button></div>
<div id='stage'><canvas id='c' width='256' height='256'></canvas><div><pre id='info'></pre><div id='palette'></div></div></div>
<script>
const D={payload}; const c=document.querySelector('#c'),ctx=c.getContext('2d'); ctx.imageSmoothingEnabled=false;
const byHash=Object.fromEntries(D.frames.map(f=>[f.rgb888_sha256,f])); let step=0,held=0,playing=true,last=performance.now();
const sel=document.querySelector('#cadence'); Object.keys(D.profiles).forEach(x=>{{let o=document.createElement('option');o.value=x;o.text=x;sel.add(o)}});sel.value='measured16';
function current(){{return D.sequence[Math.min(step,D.sequence.length-1)]}}
function draw(){{const s=byHash[current().rgb888_sha256];ctx.fillStyle='#000';ctx.fillRect(0,0,256,256);for(let y=0;y<16;y++)for(let x=0;x<16;x++){{let xx=document.querySelector('#mirror').checked?15-x:x;let k=s.rows[y][xx],rgb=s.palette[k];ctx.fillStyle=`rgb(${{rgb[0]}},${{rgb[1]}},${{rgb[2]}})`;ctx.fillRect(x*16,y*16,16,16)}}if(document.querySelector('#grid').checked){{ctx.strokeStyle='#333';ctx.lineWidth=1;for(let i=0;i<=16;i++){{ctx.beginPath();ctx.moveTo(i*16,0);ctx.lineTo(i*16,256);ctx.stroke();ctx.beginPath();ctx.moveTo(0,i*16);ctx.lineTo(256,i*16);ctx.stroke()}}}}document.querySelector('#info').textContent=JSON.stringify({{step,held,phase:current().phase,hold_acks:current().hold_acks,sprite:s.id,sha:s.rgb888_sha256}},null,2);let p=document.querySelector('#palette');p.innerHTML='';Object.values(s.palette).forEach(rgb=>{{let q=document.createElement('span');q.className='sw';q.style.background=`rgb(${{rgb[0]}},${{rgb[1]}},${{rgb[2]}})`;p.append(q)}})}}
function advance(){{held++;if(held>=current().hold_acks){{held=0;step++;if(step>=D.sequence.length){{if(D.loop)step=0;else{{step=D.sequence.length-1;playing=false}}}}}}draw()}}
function interval(){{let p=D.profiles[sel.value];return p.interval_ms||p.base_ms||61.5}}function tick(t){{if(playing&&t-last>=interval()){{last=t;advance()}}requestAnimationFrame(tick)}}
document.querySelector('#play').onclick=()=>{{playing=!playing;document.querySelector('#play').textContent=playing?'Pause':'Play'}};document.querySelector('#next').onclick=advance;document.querySelector('#prev').onclick=()=>{{step=Math.max(0,step-1);held=0;draw()}};document.querySelector('#restart').onclick=()=>{{step=held=0;draw()}};document.querySelector('#grid').onchange=draw;document.querySelector('#mirror').onchange=draw;draw();requestAnimationFrame(tick);
</script>"""


def build_review(path: Path, out_root: Path = DEFAULT_REVIEW_ROOT, *, profile: str = "measured16",
                 seed: int = 1) -> Path:
    kind, value = load_any(path)
    review_id = value.id.replace("/", "_")
    out = out_root / review_id
    out.mkdir(parents=True, exist_ok=True)
    if kind == "sprite":
        frame_records = [sprite_record(value)]
        sequence = [{"step": 0, "sprite_ref": str(path), "sprite_id": value.id,
                     "rgb888_sha256": value.rgb_sha256, "hold_acks": 1, "phase": "still"}]
        quality = quality_for_sprite(value)
        frames = [value.rgb888]
        loop = False
        source_files = [path]
        total_acks = 1
    else:
        frame_records, sequence = animation_records(value)
        quality = {"structural": "PASS", "animation": animation_quality(value),
                   "frames": {sprite.id: quality_for_sprite(sprite) for sprite in value.unique_frames()}}
        frames = [sprite.rgb888 for sprite in value.unique_frames()]
        loop = value.loop
        source_files = [path] + sorted({sprite.source_path for sprite in value.sprites.values() if sprite.source_path})
        total_acks = value.total_acks
    manifest = {
        "schema": "openditoo.pixel-review.v1", "id": value.id, "kind": kind,
        "source": stable_path(path), "source_files": [{"path": stable_path(p), "sha256": sha(p)} for p in source_files],
        "asset_sha256": value.canonical_sha256, "cadence_profile": profile, "cadence_seed": seed,
        "cadence_intervals_ms": cadence_intervals(profile, max(total_acks, 1), seed=seed),
        "command": f"python3 tools/pixel_lab.py review-bundle {path} --profile {profile} --seed {seed}",
        "artifacts": ["manifest.json", "frames.json", "quality.json", "contact-sheet.png", "preview.html", "README.txt"],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (out / "frames.json").write_text(json.dumps({"id": value.id, "kind": kind, "frames": frame_records,
                                                   "sequence": sequence, "loop": loop}, indent=2, sort_keys=True) + "\n")
    (out / "quality.json").write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n")
    make_contact_png(frames, out / "contact-sheet.png")
    (out / "preview.html").write_text(html_document(value.id, frame_records, sequence, loop=loop), encoding="utf-8")
    (out / "README.txt").write_text(
        "OpenDitoo Pixel Lab review bundle.\nRead frames.json for exact 16x16 rows/palettes/timing; quality.json for objective checks; "
        "manifest.json for hashes/cadence. PNG/HTML are derived review artifacts.\n", encoding="utf-8")
    return out


def cmd_validate(args) -> None:
    kind, value = load_any(args.asset)
    report = quality_for_sprite(value) if kind == "sprite" else animation_quality(value)
    print(json.dumps({"ok": True, "kind": kind, "id": value.id, "sha256": value.canonical_sha256,
                      "quality": report}, indent=2, sort_keys=True))


def cmd_render(args) -> None:
    kind, value = load_any(args.asset)
    sprite = value if kind == "sprite" else value.sprites[value.steps[0].sprite_ref]
    out = args.output or Path(".openditoo-local/pixel-lab/render") / f"{value.id}.png"
    write_png(out, sprite.rgb888, scale=args.scale)
    print(out)


def cmd_compare(args) -> None:
    sprites = []
    for path in args.assets:
        kind, value = load_any(path)
        sprites.append(value if kind == "sprite" else value.sprites[value.steps[0].sprite_ref])
    out = args.output or Path(".openditoo-local/pixel-lab/compare.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    make_contact_png([s.rgb888 for s in sprites], out, args.scale)
    print(json.dumps({"output": str(out), "items": [{"id": s.id, "geometry": geometry(s), "sha256": s.rgb_sha256} for s in sprites]}, indent=2))


def cmd_review(args) -> None:
    out = build_review(args.asset, args.output_root, profile=args.profile, seed=args.seed)
    print(out)


def cmd_list(_args) -> None:
    found = []
    for path in sorted((ROOT / "assets").rglob("*.json")):
        try:
            kind = schema(path)
        except PixelArtError:
            continue
        if kind in (SPRITE_SCHEMA, ANIMATION_SCHEMA):
            found.append({"path": str(path.relative_to(ROOT)), "schema": kind})
    print(json.dumps(found, indent=2))


def cmd_serve(args) -> None:
    out = build_review(args.asset, args.output_root, profile=args.profile, seed=args.seed)
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw): super().__init__(*a, directory=str(out), **kw)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"PIXEL_LAB_SERVING=http://127.0.0.1:{args.port}/preview.html")
    try: server.serve_forever()
    except KeyboardInterrupt: pass


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("validate"); q.add_argument("asset", type=Path); q.set_defaults(func=cmd_validate)
    q = sub.add_parser("render"); q.add_argument("asset", type=Path); q.add_argument("--output", type=Path); q.add_argument("--scale", type=int, default=16); q.set_defaults(func=cmd_render)
    q = sub.add_parser("compare"); q.add_argument("assets", nargs="+", type=Path); q.add_argument("--output", type=Path); q.add_argument("--scale", type=int, default=12); q.set_defaults(func=cmd_compare)
    q = sub.add_parser("review-bundle"); q.add_argument("asset", type=Path); q.add_argument("--output-root", type=Path, default=DEFAULT_REVIEW_ROOT); q.add_argument("--profile", choices=CADENCE_PROFILES, default="measured16"); q.add_argument("--seed", type=int, default=1); q.set_defaults(func=cmd_review)
    q = sub.add_parser("list"); q.set_defaults(func=cmd_list)
    q = sub.add_parser("serve"); q.add_argument("asset", type=Path); q.add_argument("--output-root", type=Path, default=DEFAULT_REVIEW_ROOT); q.add_argument("--profile", choices=CADENCE_PROFILES, default="measured16"); q.add_argument("--seed", type=int, default=1); q.add_argument("--port", type=int, default=8765); q.set_defaults(func=cmd_serve)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        args.func(args)
        return 0
    except PixelArtError as exc:
        print(f"PIXEL_LAB_ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
