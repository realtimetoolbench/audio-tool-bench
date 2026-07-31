# Audio and Trace Artifacts

The audio for all 1,040 benchmark tasks is tracked in this repository through
Git LFS under `data/audio/tts_1040/` and `data/audio/voice_clone_1040/`. Run
`git lfs install` before cloning, otherwise each `.pcm` file resolves to a
131-byte pointer instead of audio.

An LFS-free copy of the same artifacts is also available as a single anonymous
Figshare deposit (4.19 GB, CC BY 4.0):

[https://figshare.com/s/5635155a03e3faae60d3](https://figshare.com/s/5635155a03e3faae60d3)

| File | Size | Contents |
|---|---:|---|
| `tts_1040.tar.zst` | 1.77 GB | Clean TTS audio for all 1,040 tasks |
| `voice_clone_1040.tar.zst` | 2.4 GB | Voice-cloned rendering of the same 1,040 tasks |
| `traces_1040.tar.zst` | 28 MB | Task traces for the TTS and voice-cloning conditions |
| `SHA256SUMS` | 0.25 kB | Per-file checksums |

Audio is PCM16, 24 kHz, mono. Archives are compressed with Zstandard.

Extract:

```bash
tar --use-compress-program=unzstd -xf tts_1040.tar.zst
```

Verify:

```bash
shasum -a 256 -c SHA256SUMS
```
