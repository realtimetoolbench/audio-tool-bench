#!/usr/bin/env python3
"""Parallel voice-clone audio cache generation for task directories."""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable


def iter_task_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.json") if p.name != "summary.json")


def shard(items: list[Path], workers: int) -> list[list[Path]]:
    shards = [[] for _ in range(workers)]
    for idx, item in enumerate(items):
        shards[idx % workers].append(item)
    return shards


def worker_main(args: tuple[int, list[str], dict]) -> dict:
    worker_id, task_paths, cfg = args

    # Import inside each subprocess so the parent does not load XTTS.
    from eval.audio.tts_cache import TTSCache

    devices = cfg.get("devices") or []
    if devices:
        os.environ["VOICE_CLONING_DEVICE"] = devices[worker_id % len(devices)]

    cache = TTSCache(
        cache_dir=cfg.get("cache_dir"),
        variant=cfg["variant"],
        tts_backend="voice_cloning",
        clone_manifest=cfg["clone_manifest"],
        clone_accent=cfg.get("clone_accent"),
        clone_policy=cfg["clone_policy"],
        clone_model=cfg["clone_model"],
    )

    progress_path = Path(cfg["progress_dir"]) / f"worker_{worker_id:02d}.jsonl"
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    ok = 0
    skipped = 0
    failed = 0
    started_at = time.time()

    with progress_path.open("a", encoding="utf-8") as log:
        for idx, task_path in enumerate(task_paths, 1):
            record = {
                "worker": worker_id,
                "index": idx,
                "total": len(task_paths),
                "task": task_path,
                "status": None,
                "error": None,
                "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            try:
                if cache.has_cache(task_path):
                    skipped += 1
                    record["status"] = "skipped"
                else:
                    cache.generate_cache(task_path)
                    ok += 1
                    record["status"] = "ok"
            except Exception as exc:  # keep the long run moving
                failed += 1
                record["status"] = "failed"
                record["error"] = repr(exc)
            log.write(json.dumps(record, ensure_ascii=False) + "\n")
            log.flush()

    return {
        "worker": worker_id,
        "tasks": len(task_paths),
        "ok": ok,
        "skipped": skipped,
        "failed": failed,
        "elapsed_sec": round(time.time() - started_at, 2),
        "progress": str(progress_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-root", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--progress-dir", required=True)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--variant", default="default")
    parser.add_argument("--clone-manifest", required=True)
    parser.add_argument("--clone-policy", default="task_hash")
    parser.add_argument("--clone-accent", default=None)
    parser.add_argument(
        "--clone-model",
        default="tts_models/multilingual/multi-dataset/xtts_v2",
    )
    parser.add_argument(
        "--devices",
        default="",
        help="Comma-separated device list assigned round-robin to workers, e.g. cuda:0,cuda:1",
    )
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    task_root = Path(args.task_root)
    tasks = [str(p.resolve()) for p in iter_task_files(task_root)]
    if args.limit:
        tasks = tasks[: args.limit]

    workers = max(1, min(args.workers, len(tasks) or 1))
    cfg = {
        "cache_dir": args.cache_dir,
        "variant": args.variant,
        "clone_manifest": args.clone_manifest,
        "clone_accent": args.clone_accent,
        "clone_policy": args.clone_policy,
        "clone_model": args.clone_model,
        "progress_dir": args.progress_dir,
        "devices": [d.strip() for d in args.devices.split(",") if d.strip()],
    }

    progress_dir = Path(args.progress_dir)
    progress_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "task_root": str(task_root.resolve()),
        "tasks": len(tasks),
        "workers": workers,
        "config": cfg,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (progress_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2, ensure_ascii=False), flush=True)

    jobs = [(i, s, cfg) for i, s in enumerate(shard([Path(p) for p in tasks], workers))]
    failed_workers = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker_main, (wid, [str(p) for p in paths], cfg)) for wid, paths, cfg in jobs]
        for fut in as_completed(futures):
            try:
                print(json.dumps(fut.result(), ensure_ascii=False), flush=True)
            except Exception as exc:
                failed_workers += 1
                print(json.dumps({"worker_failed": repr(exc)}, ensure_ascii=False), flush=True)

    return 1 if failed_workers else 0


if __name__ == "__main__":
    raise SystemExit(main())
