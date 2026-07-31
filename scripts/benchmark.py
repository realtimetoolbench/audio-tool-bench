#!/usr/bin/env python3
"""Unified public entrypoint for Audio Tool Bench reproduction.

This script intentionally keeps the release-facing workflow in one place:

  python scripts/benchmark.py doctor
  python scripts/benchmark.py tasks
  python scripts/benchmark.py config --profile voiceclone --provider openai --model gpt-realtime-1.5
  python scripts/benchmark.py run --profile voiceclone --provider openai --model gpt-realtime-1.5
  python scripts/benchmark.py status --trace-root outputs/traces/voiceclone_1040
  python scripts/benchmark.py eval --trace-root outputs/traces/voiceclone_1040 --model-dir openai_gpt-realtime-1.5

Lower-level evaluator and audio helper modules remain available for the
implementation, but this is the only user-facing runner documented by the
anonymous release.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
TASK_SETS = [
    "reactive",
    "proactive/strong",
    "proactive/medium",
    "proactive/weak",
    "interruption/speech",
    "interruption/tool",
]
DEFAULT_TASK_ROOT = ROOT / "data/tasks"
DEFAULT_TRACE_ROOT = ROOT / "outputs/traces/default_1040"
DEFAULT_AUDIO_ROOT = ROOT / "outputs/audio"
VOICE_CLONE_MANIFEST = ROOT / "data/voice_clones/commonvoice_28speaker_manifest.json"
APPENDIX_SEED = "appendix_accent_noise_644_20260608"
APPENDIX_COUNTS = {
    "reactive": 111,
    "proactive/strong": 153,
    "proactive/medium": 152,
    "proactive/weak": 76,
    "interruption/speech": 57,
    "interruption/tool": 95,
}
NON_US_ACCENTS = [
    "england_english",
    "australian_english",
    "scottish_english",
    "india_and_south_asia_india_pakistan_sri_lanka",
]
NOISE_CLASSES = ["OOFFICE", "DKITCHEN", "PCAFETER", "PRESTO", "TMETRO", "NRIVER"]


@dataclass(frozen=True)
class ShardJob:
    task_set: str
    label: str
    shard_index: int
    task_dir: Path
    trace_dir: Path
    task_count: int


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def task_counts(task_root: Path) -> dict[str, int]:
    return {task_set: len(sorted((task_root / task_set).glob("*.json"))) for task_set in TASK_SETS}


def stable_int(*parts: str) -> int:
    digest = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def stable_choice(options: list[str], *parts: str) -> str:
    return options[stable_int(*parts) % len(options)]


def print_task_counts(task_root: Path) -> int:
    counts = task_counts(task_root)
    total = sum(counts.values())
    print(f"task_root={rel(task_root)}")
    for task_set in TASK_SETS:
        print(f"{task_set:22s} {counts[task_set]:4d}")
    print(f"{'total':22s} {total:4d}")
    if task_root == DEFAULT_TASK_ROOT and total != 1040:
        print(f"warning: default task root should contain 1040 tasks, found {total}", file=sys.stderr)
        return 1
    return 0


def run_command(cmd: list[str], *, env: dict[str, str] | None = None, log_file: Path | None = None) -> int:
    merged_env = os.environ.copy()
    merged_env["PYTHONPATH"] = f"{ROOT}{os.pathsep}{merged_env['PYTHONPATH']}" if merged_env.get("PYTHONPATH") else str(ROOT)
    merged_env.setdefault("AUDIO_TOOL_BENCH_AUDIO_ROOT", str(DEFAULT_AUDIO_ROOT))
    if proxy := merged_env.get("AUDIO_TOOL_BENCH_PROXY"):
        merged_env.setdefault("OPENAI_REALTIME_PROXY", proxy)
        merged_env.setdefault("HTTP_PROXY", proxy)
        merged_env.setdefault("HTTPS_PROXY", proxy)
        merged_env.setdefault("http_proxy", merged_env["HTTP_PROXY"])
        merged_env.setdefault("https_proxy", merged_env["HTTPS_PROXY"])
    try:
        cert = subprocess.check_output([sys.executable, "-m", "certifi"], text=True).strip()
    except Exception:
        cert = ""
    if cert:
        merged_env.setdefault("SSL_CERT_FILE", cert)
        merged_env.setdefault("REQUESTS_CA_BUNDLE", cert)
    if env:
        for key, value in env.items():
            if value == "":
                merged_env.pop(key, None)
            else:
                merged_env[key] = value
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("w", encoding="utf-8") as handle:
            proc = subprocess.run(cmd, cwd=ROOT, env=merged_env, stdout=handle, stderr=subprocess.STDOUT)
        return proc.returncode
    proc = subprocess.run(cmd, cwd=ROOT, env=merged_env)
    return proc.returncode


def doctor(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "scripts/audio/check_voiceclone_setup.py"]
    if args.import_xtts:
        cmd.append("--import-xtts")
    if args.demand_root:
        cmd.extend(["--demand-root", args.demand_root])
    rc = run_command(cmd)
    rc = rc or print_task_counts(DEFAULT_TASK_ROOT)
    return rc


def config(args: argparse.Namespace) -> int:
    counts = task_counts(args.task_root)
    total = sum(counts.values())
    condition = args.condition or "clean"
    env = provider_env(args.provider)
    provider_notes = {
        "openai": "OpenAI Realtime client defaults, with the voice-cloning profile using the release OpenAI VAD compatibility env.",
        "gemini": "Gemini Live automatic activity detection as implemented by the release adapter.",
        "qwen": "Qwen Omni adapter defaults; voice defaults to Ethan when --voice is omitted.",
        "grok": "Grok Voice adapter defaults, including local padding/force-commit behavior implemented by the release adapter.",
    }
    command_args = profile_args(args.profile, args.condition)
    if args.provider == "qwen" and not args.voice:
        voice = "Ethan"
    else:
        voice = args.voice or "provider-default"

    print("Audio Tool Bench effective public profile")
    print(f"profile={args.profile}")
    print(f"condition={condition}")
    print(f"provider={args.provider}")
    print(f"model={args.model}")
    print(f"voice={voice}")
    print(f"task_root={rel(args.task_root)}")
    print(f"task_total={total}")
    for task_set in TASK_SETS:
        print(f"task_count.{task_set}={counts[task_set]}")
    print(f"trace_root={rel(args.trace_root)}")
    print(f"log_root={rel(args.log_root)}")
    print(f"shards={args.shards}")
    print(f"attempts={args.attempts}")
    print(f"delay={args.delay}")
    print(f"skip_existing={args.skip_existing}")
    print(f"profile_args={' '.join(command_args)}")
    visible_env = {key: value for key, value in env.items() if value}
    print(f"provider_env={json.dumps(visible_env, sort_keys=True)}")
    print(f"provider_note={provider_notes.get(args.provider, 'Provider adapter defaults as implemented in eval/models.')}")
    if args.profile == "voiceclone":
        print(f"voice_clone_manifest={rel(VOICE_CLONE_MANIFEST)}")
        print("clone_policy=task_hash")
        print("clone_model=tts_models/multilingual/multi-dataset/xtts_v2")
        print("turn_detection=server_vad")
        print("all_tools=true")
    else:
        print("tts_backend=openai")
    return 0


def profile_args(profile: str, condition: str | None) -> list[str]:
    if profile == "openai-tts":
        return ["--tts-backend", "openai"]
    if profile == "voiceclone":
        args = [
            "--tts-backend",
            "voice_cloning",
            "--clone-manifest",
            rel(VOICE_CLONE_MANIFEST),
            "--clone-policy",
            "task_hash",
            "--clone-model",
            "tts_models/multilingual/multi-dataset/xtts_v2",
            "--turn-detection",
            "server_vad",
            "--all-tools",
        ]
        if condition == "accent-us":
            args.extend(["--clone-accent", "united_states_english"])
        elif condition == "noise-mixed":
            args.extend(["--audio-variant", "noisy"])
        return args
    raise ValueError(f"unknown profile: {profile}")


def provider_env(provider: str) -> dict[str, str]:
    env: dict[str, str] = {
        "AUDIO_TOOL_BENCH_SERVER_VAD_SILENCE_MS": "",
        "AUDIO_TOOL_BENCH_GROK_PURE_OFFICIAL_VAD": "",
    }
    if provider == "openai":
        env["AUDIO_TOOL_BENCH_SERVER_VAD_SILENCE_MS"] = "3000"
    elif provider == "qwen":
        env["AUDIO_TOOL_BENCH_SERVER_VAD_SILENCE_MS"] = "800"
    return env


def selected_tasks(task_root: Path, task_set: str, limit_per_subset: int | None) -> list[Path]:
    files = sorted((task_root / task_set).glob("*.json"))
    if limit_per_subset is not None:
        files = files[:limit_per_subset]
    return files


def missing_tasks(task_files: list[Path], trace_dir: Path, skip_existing: bool) -> list[Path]:
    if not skip_existing:
        return task_files
    existing = {path.stem for path in trace_dir.glob("*.json")}
    return [path for path in task_files if path.stem not in existing]


def make_shards(task_files: list[Path], shard_count: int, task_set: str) -> list[Path]:
    shard_count = max(1, min(shard_count, len(task_files)))
    temp_root = Path(tempfile.mkdtemp(prefix=f"audio_tool_bench_{task_set.replace('/', '_')}_"))
    shard_dirs = [temp_root / f"shard_{idx}" for idx in range(shard_count)]
    for shard_dir in shard_dirs:
        shard_dir.mkdir(parents=True, exist_ok=True)
    for idx, task_file in enumerate(task_files):
        target = shard_dirs[idx % shard_count] / task_file.name
        target.symlink_to(task_file.resolve())
    return shard_dirs


def subset_trace_name(task_set: str, condition: str | None) -> str:
    if condition in {"accent-us", "accent-non-us", "noise-mixed"}:
        return f"{condition.replace('-', '_')}/{task_set}"
    return task_set


def run_shard(job: ShardJob, args: argparse.Namespace, extra: list[str], env: dict[str, str]) -> tuple[ShardJob, int]:
    cmd = [
        sys.executable,
        "-m",
        "eval",
        "batch",
        "--provider",
        args.provider,
        "--model",
        args.model,
        "--tasks",
        rel(job.task_dir),
        "--task-set-name",
        subset_trace_name(job.task_set, args.condition),
        "--trace-root",
        rel(args.trace_root),
        "--delay",
        str(args.delay),
    ]
    if args.voice:
        cmd.extend(["--voice", args.voice])
    if args.skip_existing:
        cmd.append("--skip-existing")
    cmd.extend(extra)
    log_file = args.log_root / f"{args.provider}_{args.model}_{job.label.replace('/', '_')}_shard{job.shard_index}.log"
    final_rc = 1
    for attempt in range(1, args.attempts + 1):
        rc = run_command(cmd, env=env, log_file=log_file)
        shard_task_ids = [path.stem for path in job.task_dir.glob("*.json")]
        done = sum(1 for task_id in shard_task_ids if (job.trace_dir / f"{task_id}.json").exists())
        if rc == 0 and done >= job.task_count:
            final_rc = 0
            break
        final_rc = rc
        time.sleep(5)
    return job, final_rc


def run(args: argparse.Namespace) -> int:
    counts = task_counts(args.task_root)
    total = sum(counts.values())
    if args.task_root == DEFAULT_TASK_ROOT and total != 1040:
        print(f"default data/tasks must contain 1040 tasks; found {total}", file=sys.stderr)
        return 2
    if args.expected_total is not None and total != args.expected_total:
        print(f"expected {args.expected_total} tasks under {rel(args.task_root)}, found {total}", file=sys.stderr)
        return 2
    env = provider_env(args.provider)
    if args.provider == "qwen" and not args.voice:
        args.voice = "Ethan"
    total_tasks = 0
    failures = 0
    model_dir = args.trace_root / f"{args.provider}_{args.model}"
    for task_set in TASK_SETS:
        trace_name = subset_trace_name(task_set, args.condition)
        trace_dir = model_dir / trace_name
        trace_dir.mkdir(parents=True, exist_ok=True)
        task_files = selected_tasks(args.task_root, task_set, args.limit_per_subset)
        if args.condition == "accent-non-us":
            groups: dict[str, list[Path]] = {accent: [] for accent in NON_US_ACCENTS}
            for task_file in task_files:
                accent = stable_choice(NON_US_ACCENTS, APPENDIX_SEED, task_set, task_file.name)
                groups[accent].append(task_file)
        else:
            groups = {"": task_files}

        for accent, group_files in groups.items():
            task_files_for_run = missing_tasks(group_files, trace_dir, args.skip_existing)
            if not task_files_for_run:
                continue
            total_tasks += len(task_files_for_run)
            run_condition = args.condition
            if args.condition == "accent-non-us":
                run_condition = None
            extra = profile_args(args.profile, run_condition)
            if accent:
                extra.extend(["--clone-accent", accent])
            jobs: list[ShardJob] = []
            shard_dirs = make_shards(task_files_for_run, args.shards, f"{trace_name}_{accent}")
            for shard_index, shard_dir in enumerate(shard_dirs):
                shard_count = len(list(shard_dir.glob("*.json")))
                if shard_count:
                    label = f"{trace_name}_{accent}" if accent else trace_name
                    jobs.append(ShardJob(task_set, label, shard_index, shard_dir, trace_dir, shard_count))
            label = f"{task_set}" + (f" accent={accent}" if accent else "")
            print(f"starting {label}: missing={len(task_files_for_run)} shards={len(jobs)}")
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.shards, len(jobs))) as pool:
                    futures = [pool.submit(run_shard, job, args, extra, env) for job in jobs]
                    for future in concurrent.futures.as_completed(futures):
                        job, rc = future.result()
                        if rc:
                            failures += job.task_count
                            print(f"failed rc={rc}: {job.task_set}/shard{job.shard_index}", file=sys.stderr)
            finally:
                if shard_dirs:
                    shutil.rmtree(shard_dirs[0].parent, ignore_errors=True)
    print(f"ran {total_tasks} missing tasks profile={args.profile} provider={args.provider} model={args.model}")
    print(f"task_root={rel(args.task_root)} trace_root={rel(args.trace_root)} shards={args.shards}")
    print(f"completed={total_tasks - failures}/{total_tasks} failed={failures}")
    return 1 if failures else 0


def status(args: argparse.Namespace) -> int:
    expected = task_counts(args.task_root)
    expected_total = sum(expected.values())
    print(f"trace_root={rel(args.trace_root)}")
    print(f"task_root={rel(args.task_root)} expected_total={expected_total}")
    print("| Model | Coverage | reactive | strong | medium | weak | speech | tool |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    model_dirs = sorted(p for p in args.trace_root.glob("*") if p.is_dir())
    if args.model_dir:
        model_dirs = [args.trace_root / args.model_dir]
    for model_dir in model_dirs:
        counts = {task_set: len(sorted((model_dir / subset_trace_name(task_set, args.condition)).glob("*.json"))) for task_set in TASK_SETS}
        total = sum(counts.values())
        print(
            f"| {model_dir.name} | {total}/{expected_total} | "
            f"{counts['reactive']}/{expected['reactive']} | "
            f"{counts['proactive/strong']}/{expected['proactive/strong']} | "
            f"{counts['proactive/medium']}/{expected['proactive/medium']} | "
            f"{counts['proactive/weak']}/{expected['proactive/weak']} | "
            f"{counts['interruption/speech']}/{expected['interruption/speech']} | "
            f"{counts['interruption/tool']}/{expected['interruption/tool']} |"
        )
    return 0


def evaluate(args: argparse.Namespace) -> int:
    model_dir = args.trace_root / args.model_dir
    if not model_dir.exists():
        print(f"missing model trace dir: {rel(model_dir)}", file=sys.stderr)
        return 2
    jobs = [
        [sys.executable, "eval/evaluators/evaluate_reactive.py", rel(args.task_root / "reactive"), rel(model_dir / subset_trace_name("reactive", args.condition))],
        [sys.executable, "eval/evaluators/evaluate_traces.py", rel(model_dir / subset_trace_name("proactive/strong", args.condition)), "--task-dir", rel(args.task_root / "proactive/strong")],
        [sys.executable, "eval/evaluators/evaluate_traces.py", rel(model_dir / subset_trace_name("proactive/medium", args.condition)), "--task-dir", rel(args.task_root / "proactive/medium")],
        [sys.executable, "eval/evaluators/evaluate_traces.py", rel(model_dir / subset_trace_name("proactive/weak", args.condition)), "--task-dir", rel(args.task_root / "proactive/weak")],
        [sys.executable, "eval/evaluators/evaluate_interruption.py", rel(args.task_root / "interruption"), rel(model_dir / (args.condition.replace("-", "_") if args.condition else "interruption"))],
    ]
    rc = 0
    for cmd in jobs:
        rc = run_command(cmd) or rc
    return rc


def make_subset(args: argparse.Namespace) -> int:
    output_root = args.output_root.resolve()
    subset_root = output_root / "subsets" / "all"
    if subset_root.exists():
        shutil.rmtree(subset_root)
    manifest: dict[str, object] = {
        "seed": args.seed,
        "source_task_root": rel(args.task_root.resolve()),
        "output_root": rel(output_root),
        "counts": APPENDIX_COUNTS,
        "tasks": {},
        "accent_non_us": {},
        "noise_mixed": {},
    }
    for task_set, count in APPENDIX_COUNTS.items():
        files = sorted((args.task_root / task_set).glob("*.json"))
        if len(files) < count:
            print(f"not enough tasks for {task_set}: need {count}, found {len(files)}", file=sys.stderr)
            return 2
        ranked = sorted(files, key=lambda path: stable_int(args.seed, task_set, path.name))
        selected = sorted(ranked[:count])
        out_dir = subset_root / task_set
        out_dir.mkdir(parents=True, exist_ok=True)
        task_entries = []
        for path in selected:
            target = out_dir / path.name
            target.symlink_to(path.resolve())
            rel_path = rel(path.resolve())
            task_entries.append(rel_path)
            manifest["accent_non_us"][rel_path] = stable_choice(NON_US_ACCENTS, args.seed, task_set, path.name)
            manifest["noise_mixed"][rel_path] = stable_choice(NOISE_CLASSES, args.seed, task_set, path.name)
        manifest["tasks"][task_set] = task_entries
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "subset_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {rel(output_root / 'subset_manifest.json')}")
    return print_task_counts(subset_root)


def prepare_noise(args: argparse.Namespace) -> int:
    from scripts.ablation.audio_mix.inject_noise import inject_for_task

    task_files = [path for task_set in TASK_SETS for path in selected_tasks(args.task_root, task_set, args.limit_per_subset)]
    if args.generate_clean:
        for path in task_files:
            cmd = [
                sys.executable,
                "-m",
                "eval",
                "tts-generate",
                rel(path),
                "--tts-backend",
                "voice_cloning",
                "--clone-manifest",
                rel(VOICE_CLONE_MANIFEST),
                "--clone-policy",
                "task_hash",
                "--clone-model",
                "tts_models/multilingual/multi-dataset/xtts_v2",
            ]
            rc = run_command(cmd)
            if rc:
                return rc
    results = []
    for index, path in enumerate(task_files, 1):
        noise_class = stable_choice(NOISE_CLASSES, args.seed, path.as_posix())
        try:
            result = inject_for_task(
                path,
                rng=__import__("random").Random(stable_int(args.seed, path.name)),
                tts_backend="voice_cloning",
                clone_manifest=rel(VOICE_CLONE_MANIFEST),
                clone_policy="task_hash",
                snr_db=args.snr_db,
                noise_class=noise_class,
            )
        except Exception as exc:
            result = {"task": path.stem, "status": "fail", "error": f"{type(exc).__name__}: {exc}"}
        results.append(result)
        print(f"[{index}/{len(task_files)}] {rel(path)} {result.get('status')} {result.get('noise_class', '')}")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    failed = sum(1 for item in results if item.get("status") != "ok")
    print(f"wrote {rel(args.summary)}; ok={len(results)-failed}/{len(results)} failed={failed}")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified Audio Tool Bench runner")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check local reproduction setup")
    p.add_argument("--import-xtts", action="store_true", help="also import Coqui TTS")
    p.add_argument("--demand-root", help="optional DEMAND_16k root")
    p.set_defaults(func=doctor)

    p = sub.add_parser("tasks", help="show task-set counts")
    p.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    p.set_defaults(func=lambda a: print_task_counts(a.task_root))

    p = sub.add_parser("config", help="print the effective public benchmark profile without running")
    p.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    p.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    p.add_argument("--log-root", type=Path, default=ROOT / "outputs/logs/benchmark")
    p.add_argument("--profile", choices=["openai-tts", "voiceclone"], default="openai-tts")
    p.add_argument("--condition", choices=["accent-us", "accent-non-us", "noise-mixed"], default=None)
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--voice")
    p.add_argument("--shards", type=int, default=1)
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--delay", type=float, default=1.5)
    p.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True)
    p.set_defaults(func=config)

    p = sub.add_parser("make-subset", help="create deterministic appendix subset symlinks")
    p.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    p.add_argument("--output-root", type=Path, default=ROOT / "outputs/experiments/appendix_accent_noise_644")
    p.add_argument("--seed", default=APPENDIX_SEED)
    p.set_defaults(func=make_subset)

    p = sub.add_parser("prepare-noise", help="create noisy PCM cache for mixed-noise condition")
    p.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    p.add_argument("--summary", type=Path, default=ROOT / "outputs/experiments/noise_mixed_summary.json")
    p.add_argument("--seed", default=APPENDIX_SEED)
    p.add_argument("--snr-db", type=float, default=15.0)
    p.add_argument("--limit-per-subset", type=int)
    p.add_argument("--generate-clean", action="store_true", help="generate missing clean XTTS cache before mixing")
    p.set_defaults(func=prepare_noise)

    p = sub.add_parser("run", help="run one model over the benchmark")
    p.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    p.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    p.add_argument("--log-root", type=Path, default=ROOT / "outputs/logs/benchmark")
    p.add_argument("--profile", choices=["openai-tts", "voiceclone"], default="openai-tts")
    p.add_argument("--condition", choices=["accent-us", "accent-non-us", "noise-mixed"], default=None)
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--voice")
    p.add_argument("--shards", type=int, default=1)
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--delay", type=float, default=1.5)
    p.add_argument("--limit-per-subset", type=int)
    p.add_argument("--expected-total", type=int)
    p.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True)
    p.set_defaults(func=run)

    p = sub.add_parser("status", help="print trace coverage")
    p.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    p.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    p.add_argument("--model-dir")
    p.add_argument("--condition", choices=["accent-us", "accent-non-us", "noise-mixed"], default=None)
    p.set_defaults(func=status)

    p = sub.add_parser("eval", help="run evaluators for one model trace directory")
    p.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    p.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    p.add_argument("--model-dir", required=True, help="directory name under trace-root, e.g. openai_gpt-realtime-1.5")
    p.add_argument("--condition", choices=["accent-us", "accent-non-us", "noise-mixed"], default=None)
    p.set_defaults(func=evaluate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.task_root = args.task_root.resolve() if hasattr(args, "task_root") else DEFAULT_TASK_ROOT
    if hasattr(args, "trace_root"):
        args.trace_root = args.trace_root.resolve()
    if hasattr(args, "log_root"):
        args.log_root = args.log_root.resolve()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
