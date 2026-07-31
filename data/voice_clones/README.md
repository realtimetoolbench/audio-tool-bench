# Voice clone manifests

This directory stores the Common Voice reference manifests used by the
voice-cloning stress tests.

For reproducibility, the anonymized release includes the small selected
reference clips used by the paper's 28-speaker Common Voice profile:

- `commonvoice_28speaker_manifest.json`
- `commonvoice_28speaker_refs/*.wav`

The benchmark assigns speakers deterministically from the task transcript hash,
so these files are enough to regenerate the same XTTS cache layout used by the
paper experiments. If you want to rebuild the manifest from a local Common Voice
download instead, use:

Build a manifest from a local CommonVoice split:

```bash
python scripts/audio/build_commonvoice_manifest.py \
  --commonvoice-root /path/to/cv-corpus/en \
  --validated-tsv validated.tsv \
  --clips-dir clips \
  --language en \
  --verify-files \
  --output data/voice_clones/commonvoice_manifest.json
```

Each speaker entry must include `speaker_id`, `reference_wavs`, `language`,
`accent`, and `reference_hash`.

Accent labels are normalized with lowercase snake-case names. The paper's accent
conditions use:

- `united_states_english`
- `england_english`
- `australian_english`
- `scottish_english`
- `india_and_south_asia_india_pakistan_sri_lanka`
