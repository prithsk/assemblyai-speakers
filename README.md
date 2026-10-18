# assemblyai-speakers

Who said what on earnings calls, where AssemblyAI's own docs say diarization struggles.

AssemblyAI's docs say diarization "may be performing poorly if a speaker only speaks once or infrequently," recommend 30 seconds of uninterrupted speech per speaker, and cap the default at 10 speakers. Earnings-call Q&A breaks all three: a dozen analysts who each ask one question. In Rev's Earnings-21 eval set, half the calls have 11 to 15 speakers.

Earnings calls announce their own speakers. The host introduces the executives, and the operator announces each analyst. So the first pass reads the speaker count out of its own transcript, and the second pass feeds that count into AssemblyAI's recommended `speaker_options`, a minimum and a maximum two above it. A third pass with the true count from Rev's labels is the ceiling, the same calibration move as an oracle.

## Results

<!-- results:start -->
# AssemblyAI diarization on Earnings-21, 2026-10-18

10 earnings calls, Rev's speaker labels as ground truth. WDER is the share of correctly transcribed words attributed to the wrong speaker; lower is better.

| Setup | WDER, all calls | WDER, calls with more than 10 speakers | Error on frequent speakers | Error on brief speakers (under 300 words) |
|---|---|---|---|---|
| AssemblyAI default | 0.105 | 0.106 | 0.106 | 0.165 |
| Speaker count read from the transcript, passed as speaker_options | 0.218 | 0.217 | 0.213 | 0.310 |
| True speaker count (ceiling) | 0.191 | 0.235 | 0.190 | 0.104 |

| Call | Company | True speakers | Read from transcript | Default labels | WDER default | estimated | true count |
|---|---|---|---|---|---|---|---|
| 4320211 | Monro Inc | 10 | 8 | 10 | 0.049 | 0.048 | 0.048 |
| 4341191 | General Electric | 14 | 3 | 12 | 0.027 | 0.157 | 0.239 |
| 4346818 | Ingersoll Rand | 15 | 16 | 17 | 0.337 | 0.340 | 0.335 |
| 4359971 | Constellium | 10 | 11 | 9 | 0.032 | 0.360 | 0.134 |
| 4365024 | Nextar Media Group | 13 | 2 | 10 | 0.023 | 0.180 | 0.012 |
| 4366522 | Aldeyra Therapeutics Inc | 5 | 7 | 6 | 0.300 | 0.331 | 0.001 |
| 4366893 | Earthstone Energy Inc | 9 | 7 | 10 | 0.162 | 0.174 | 0.174 |
| 4367535 | Affimed | 11 | 13 | 11 | 0.044 | 0.220 | 0.044 |
| 4383161 | Pilgrims Pride Corp | 11 | 7 | 8 | 0.054 | 0.054 | 0.300 |
| 4384964 | Eversource | 15 | 9 | 5 | 0.158 | 0.363 | 0.464 |

## Honest limits

- WDER only scores words both transcripts agree on, so it measures speaker attribution, not transcription accuracy.
- The speaker-count reader is a handful of regex patterns for how earnings-call operators talk. It is domain-specific by design.
- Ten calls. Per-call WDER swings a lot; the word-weighted totals are the result.
- The true-count row uses Rev's labels, so no real deployment gets it. It shows how much of the gap the estimate closes.
<!-- results:end -->

## Metric

Word diarization error rate, WDER: the share of words both transcripts got right that AssemblyAI attributed to the wrong speaker, after the best one-to-one mapping between AssemblyAI's labels and Rev's. AssemblyAI says it optimizes for words attributed to the right speaker, so this scores the thing they care about.

## Run it

```
pip install -r requirements.txt
cp .env.example .env    # ASSEMBLYAI_API_KEY
python bench.py --limit 10
```

Audio, uploads and transcripts are cached, so a dropped connection never costs a second transcription.

## License

MIT. Earnings-21 is from Rev, CC BY-SA 4.0.
