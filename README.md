# assemblyai-speakers

Who said what on earnings calls, where AssemblyAI's own docs say diarization struggles.

AssemblyAI's docs say diarization "may be performing poorly if a speaker only speaks once or infrequently," recommend 30 seconds of uninterrupted speech per speaker, and cap the default at 10 speakers. Earnings-call Q&A breaks all three: a dozen analysts who each ask one question. In Rev's Earnings-21 eval set, half the calls have 11 to 15 speakers.

Earnings calls announce their own speakers. The host introduces the executives, and the operator announces each analyst. So the first pass reads the speaker count out of its own transcript, and the second pass feeds that count into AssemblyAI's recommended `speaker_options`, a minimum and a maximum two above it. A third pass with the true count from Rev's labels is the ceiling, the same calibration move as an oracle.

## Results

<!-- results:start -->
_Run it to populate._
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
