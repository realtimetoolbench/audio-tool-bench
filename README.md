# Audio Tool Bench

> **Anonymous Notice**: This repository is an anonymized snapshot for **NeurIPS 2026** double-blind review. All author identifiers, affiliations, and personal paths have been removed. Full code and data will be released upon publication.

Audio Tool Bench evaluates **end-to-end tool-calling for voice-native AI** — Realtime/Live API models that consume streaming audio and emit tool calls within a single WebSocket session. The benchmark probes information gathering, tool-invocation timing, multi-turn memory, and recovery from interruptions.

## What's in this repository

| Path | Description |
|---|---|
| `eval/` | Evaluation framework (CLI, Realtime API clients, scenario runner, TTS, tool implementations) |
| `scripts/benchmark.py` | Unified public runner for setup checks, task counts, batch runs, coverage, and evaluation |
| `scripts/audio/` | Internal helpers for Common Voice / XTTS reference manifest preparation |
| `scripts/task_gen/` | Internal task-generation utilities |
| `analysis/` | Analysis code and compact generated snapshots needed by the paper plots |
| `tests/` | Smoke tests |
| `data/tasks/` | **Default 1040-task benchmark** (Reactive, Proactive×3, Interruption×2) |
| `data/multi_step_tasks/` | Multi-step task definitions |
| `data/results/` | Pre-computed score snapshots |
| `data/voice_clones/` | Selected Common Voice reference clips and manifests for XTTS voice-cloning stress tests |
| `data/audio/tts_1040/` | OpenAI TTS audio for the 1040-task benchmark |
| `data/audio/voice_clone_1040/` | Voice-cloned audio for the same 1040 tasks |
| `data/traces/reviewer_release_1040_main/` | Raw main-evaluation traces |
| `data/traces/reactive_tool_robustness_30303010_v1/` | Raw controlled latency/failure traces and evaluation metadata |

Both audio caches mirror `data/tasks/` directly by canonical task ID; there is
no separate `original`/`expand` layer.

## What's not in this repository

Run logs, paper figures, and generated paper tables are not bundled. The full
TTS, voice-cloning, and raw trace artifacts are included through Git LFS. Install
Git LFS before cloning or pulling the release:

```bash
git lfs install
git clone <repository-url>
```

The small Common Voice reference set used by the voice-cloning appendix
experiments is bundled under `data/voice_clones/` so XTTS, accent, and mixed
noise runs can be reproduced deterministically. DEMAND background-noise audio is
not bundled; set `AUDIO_TOOL_BENCH_DEMAND_ROOT` to a local DEMAND_16k download.

The full pre-computed datasets, human baselines, and ablation traces will be released as supplementary material upon acceptance.

## Supported providers

| Provider | Default model | Env var |
|---|---|---|
| OpenAI | `gpt-realtime-mini` | `OPENAI_API_KEY` |
| Google | `gemini-2.5-flash-native-audio-preview-12-2025` | `GOOGLE_API_KEY` |
| xAI | `grok-3-fast` | `XAI_API_KEY` |
| Alibaba | `qwen3-omni-flash-realtime` | `DASHSCOPE_API_KEY` |
| ByteDance | `doubao-1.5-realtime-voice-pro` | `VOLCENGINE_API_KEY` |
| Zhipu | `glm-4-voice` | `ZHIPU_API_KEY` |
| MiniMax | `speech-2.6` | `MINIMAX_API_KEY` |

`OPENAI_API_KEY` is always required (TTS synthesis uses OpenAI). Other keys are needed only for the corresponding provider.

## Setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt

export OPENAI_API_KEY="..."
export GOOGLE_API_KEY="..."
# ... per-provider keys as needed
```

Optional voice-cloning / accent / noise setup:

```bash
pip install -r requirements-voice-cloning.txt
python scripts/audio/check_voiceclone_setup.py --import-xtts
```

Python 3.10 or 3.11 is recommended for Coqui TTS. If XTTS is already downloaded,
point to the local model directory containing `config.json`:

```bash
export VOICE_CLONING_MODEL_PATH=/path/to/tts_models--multilingual--multi-dataset--xtts_v2
export VOICE_CLONING_DEVICE=cuda          # or cpu
export AUDIO_TOOL_BENCH_AUDIO_ROOT=$PWD/outputs/audio
export AUDIO_TOOL_BENCH_TRACE_ROOT=$PWD/outputs/traces
```

If `VOICE_CLONING_MODEL_PATH` is unset, Coqui TTS will download/load the named
XTTS model on first use.

For noise runs, set the DEMAND root:

```bash
export AUDIO_TOOL_BENCH_DEMAND_ROOT=/path/to/DEMAND_16k
python scripts/audio/check_voiceclone_setup.py --demand-root "$AUDIO_TOOL_BENCH_DEMAND_ROOT"
```

Expected DEMAND layout:

```text
DEMAND_16k/
  DKITCHEN/DKITCHEN/ch01.wav
  OOFFICE/OOFFICE/ch01.wav
  PCAFETER/PCAFETER/ch01.wav
  PRESTO/PRESTO/ch01.wav
  TMETRO/TMETRO/ch01.wav
  NRIVER/NRIVER/ch01.wav
```

## Common Voice references

The anonymized release includes the selected 28-speaker Common Voice reference
profile used by the paper:

```text
data/voice_clones/commonvoice_28speaker_manifest.json
data/voice_clones/commonvoice_28speaker_refs/*.wav
```

Speaker assignment is deterministic:

```text
task transcript hash + accent filter + clone policy -> speaker id
```

To regenerate a manifest from a local Common Voice split:

```bash
python scripts/audio/build_commonvoice_manifest.py \
  --commonvoice-root /path/to/cv-corpus/en \
  --validated-tsv validated.tsv \
  --clips-dir clips \
  --language en \
  --refs-per-speaker 1 \
  --max-speakers 28 \
  --verify-files \
  --output data/voice_clones/commonvoice_manifest.json
```

To build an accent-labeled manifest from a Hugging Face Common Voice derivative:

```bash
python scripts/audio/build_accented_commonvoice_manifest.py \
  --target-accents united_states_english,england_english,australian_english,scottish_english,india_and_south_asia_india_pakistan_sri_lanka \
  --speakers-per-accent 2 \
  --output data/voice_clones/commonvoice_accent_manifest.json
```

## End-to-end smoke test

```bash
# 1. Check local setup and task counts
python scripts/benchmark.py doctor

# 2. Run a tiny OpenAI-TTS smoke pass: 1 task from each subset
python scripts/benchmark.py run \
  --profile openai-tts \
  --provider openai \
  --model gpt-realtime-mini \
  --limit-per-subset 1 \
  --trace-root outputs/traces/smoke_openai_tts

# 3. Check coverage
python scripts/benchmark.py status --trace-root outputs/traces/smoke_openai_tts
```

Voice-cloning smoke test:

```bash
python scripts/benchmark.py run \
  --profile voiceclone \
  --provider openai \
  --model gpt-realtime-1.5 \
  --limit-per-subset 1 \
  --trace-root outputs/traces/smoke_voiceclone
```

## Unified benchmark runner

All release-facing runs go through one entrypoint:

```bash
python scripts/benchmark.py <doctor|tasks|config|make-subset|prepare-noise|run|status|eval> ...
```

The default benchmark root is `data/tasks`, containing 1040 tasks:

```bash
python scripts/benchmark.py tasks
```

## Paper profiles

The public runner exposes paper-level presets instead of requiring reviewers to
manually tune provider-specific realtime adapters. Provider clients keep their
adapter defaults in `eval/models/`; the runner fixes the benchmark-facing
variables that define each reported condition.

| Profile / condition | Intended use | Fixed release-facing variables |
|---|---|---|
| `--profile openai-tts` | Main clean benchmark with OpenAI TTS prompts | `tts_backend=openai`, task root, provider/model, delay, attempts, trace layout |
| `--profile voiceclone` | Voice-cloning stress test and appendix baseline | Common Voice 28-speaker manifest, XTTS v2, `task_hash` clone policy, `server_vad`, `--all-tools` |
| `--condition accent-us` | Appendix US-accent voice-cloning condition | `voiceclone` plus `united_states_english` accent filter |
| `--condition accent-non-us` | Appendix non-US accent condition | `voiceclone` plus deterministic balanced assignment across four non-US Common Voice accents |
| `--condition noise-mixed` | Appendix mixed-noise condition | `voiceclone` plus deterministic DEMAND scene noise at 15 dB SNR |

Inspect the effective public configuration before launching a run:

```bash
python scripts/benchmark.py config \
  --profile voiceclone \
  --provider openai \
  --model gpt-realtime-1.5 \
  --shards 6
```

Run the full default 1040-task benchmark for one model:

```bash
python scripts/benchmark.py run \
  --profile openai-tts \
  --provider openai \
  --model gpt-realtime-mini \
  --shards 6 \
  --trace-root outputs/traces/openai_tts_1040

python scripts/benchmark.py status --trace-root outputs/traces/openai_tts_1040
python scripts/benchmark.py eval \
  --trace-root outputs/traces/openai_tts_1040 \
  --model-dir openai_gpt-realtime-mini
```

Run the default 1040-task voice-cloning profile:

```bash
python scripts/benchmark.py run \
  --profile voiceclone \
  --provider openai \
  --model gpt-realtime-1.5 \
  --shards 6 \
  --trace-root outputs/traces/voiceclone_1040
```

The optional expanded stress-test uses the same runner with a separate expanded
task root. The anonymous release defaults to 1040 tasks; if you prepare a
1288-task root, pass it explicitly:

```bash
python scripts/benchmark.py run \
  --profile voiceclone \
  --task-root data/tasks_1288 \
  --expected-total 1288 \
  --provider openai \
  --model gpt-realtime-1.5 \
  --shards 6 \
  --trace-root outputs/traces/voiceclone_1288
```

Accent and mixed-noise appendix conditions are also selected through the unified
runner. To reproduce the 644-task appendix subset, first create the deterministic
subset symlinks:

```bash
python scripts/benchmark.py make-subset \
  --output-root outputs/experiments/appendix_accent_noise_644
```

Then pass that subset root to the run commands:

```bash
python scripts/benchmark.py run \
  --profile voiceclone \
  --task-root outputs/experiments/appendix_accent_noise_644/subsets/all \
  --condition accent-us \
  --provider openai \
  --model gpt-realtime-1.5 \
  --trace-root outputs/traces/appendix_accent_us_644

python scripts/benchmark.py run \
  --profile voiceclone \
  --task-root outputs/experiments/appendix_accent_noise_644/subsets/all \
  --condition accent-non-us \
  --provider openai \
  --model gpt-realtime-1.5 \
  --trace-root outputs/traces/appendix_accent_non_us_644
```

The noise condition expects that `AUDIO_TOOL_BENCH_DEMAND_ROOT` is set. Prepare
the noisy XTTS cache once, then run with `--condition noise-mixed`:

```bash
python scripts/benchmark.py prepare-noise \
  --task-root outputs/experiments/appendix_accent_noise_644/subsets/all \
  --generate-clean

python scripts/benchmark.py run \
  --profile voiceclone \
  --task-root outputs/experiments/appendix_accent_noise_644/subsets/all \
  --condition noise-mixed \
  --provider openai \
  --model gpt-realtime-1.5 \
  --trace-root outputs/traces/appendix_noise_mixed_644
```

Low-level one-off commands are still available through `python -m eval` for
debugging single tasks, but benchmark reproduction should use
`scripts/benchmark.py`.

Noise details: `scripts/ablation/audio_mix/inject_noise.py` mixes DEMAND scene
noise into the clean XTTS PCM cache at 15 dB SNR and writes the result under each
task's `noisy/` audio-variant directory. The mixed appendix condition balances
`OOFFICE`, `DKITCHEN`, `PCAFETER`, `PRESTO`, `TMETRO`, and `NRIVER`.
The non-US accent condition deterministically balances
`england_english`, `australian_english`, `scottish_english`, and
`india_and_south_asia_india_pakistan_sri_lanka`.

## CLI options

| Flag | Description | Default |
|---|---|---|
| `--provider` / `-p` | Provider name | `openai` |
| `--model` | Model identifier | provider-specific |
| `--voice` | Voice/persona | provider-specific |
| `--region` | Region (Qwen) | `cn` |
| `--realtime` / `-r` | Stream at real-time playback rate | off |
| `--time-scale` / `-t` | Time-scale factor | `1.0` |
| `--output` | Output filename | auto |
| `--tts-backend` | TTS backend: `openai` or `voice_cloning` | `openai` |
| `--clone-manifest` | Common Voice clone manifest for XTTS | none |
| `--clone-accent` | Optional normalized accent filter | none |
| `--audio-variant` | Audio cache variant: `default`, `no_prosody`, `noisy` | `default` |
| `--all-tools` | Register the full expanded tool catalog | off |

## Task schema

```json
{
  "name": "gen_000000",
  "description": "User books a ride with explicit pickup and destination",
  "tool_category": "transportation",
  "chunks": [
    {
      "role": "user",
      "content": "Get me an economy car from China World Trade Center to Beijing South Railway Station",
      "timestamp": 0.0
    }
  ],
  "expected_tools": [
    {"tool": "request_ride", "params": {"pickup": "...", "destination": "..."}}
  ]
}
```

## Trace schema

```json
{
  "task_name": "gen_000000",
  "metadata": {"provider": "openai", "realtime_model": "gpt-realtime-mini"},
  "steps": [
    {
      "step_id": 1,
      "input_chunk": {"content": "...", "audio_size_bytes": 12345},
      "assistant_response": "...",
      "tool_executions": [
        {"tool_name": "request_ride", "arguments": {}, "result": {}}
      ],
      "total_latency_ms": 1234.5
    }
  ],
  "summary": {"total_steps": 1, "total_tool_calls": 1}
}
```

## Citation

```bibtex
@inproceedings{anonymous2026audiotoolbench,
  title     = {Audio Tool Bench: Evaluating End-to-End Tool-Calling for Voice-Native AI},
  author    = {Anonymous},
  booktitle = {Advances in Neural Information Processing Systems},
  year      = {2026},
  note      = {Under review}
}
```

## References

- [Berkeley Function Calling Leaderboard (BFCL)](https://gorilla.cs.berkeley.edu/leaderboard.html)
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)
- [Gemini Live API](https://ai.google.dev/gemini-api/docs/live)
