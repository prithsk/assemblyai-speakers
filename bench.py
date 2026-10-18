"""assemblyai-speakers: who said what, on earnings calls, where AssemblyAI's own docs say diarization struggles.

AssemblyAI's docs say diarization "may be performing poorly if a speaker only speaks once or infrequently," recommend
30 seconds of uninterrupted speech per speaker, and default to at most 10 speakers. Earnings-call Q&A breaks all three:
a dozen analysts who each ask one question, and half the Earnings-21 eval calls have 11 to 15 speakers.

Earnings calls announce their own speakers ("our next question comes from Jane Smith with Goldman"). So pass one reads
the speaker count out of its own transcript; pass two feeds that count into AssemblyAI's recommended speaker_options
(minimum, and maximum a little above). A third pass with the true count from Rev's labels is the ceiling.

Metric: word diarization error rate (WDER), the share of correctly transcribed words attributed to the wrong speaker,
after the best one-to-one mapping between AssemblyAI's labels and Rev's.

  python bench.py --limit 10        # needs ASSEMBLYAI_API_KEY in .env
"""
import argparse, collections, csv, difflib, io, json, re, statistics, time, datetime as dt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from common import ROOT, need, os

RAW = "https://raw.githubusercontent.com/revdotcom/speech-datasets/main/earnings21/"
API = "https://api.assemblyai.com/v2"
CACHE = ROOT / "cache"

def session():
    s = requests.Session()   # your connection drops; retry everything with backoff
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=8, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
                                                        allowed_methods=None, raise_on_status=False)))
    return s
HTTP = session()

def files():
    rows = list(csv.DictReader(io.StringIO(HTTP.get(RAW + "eval10-file-metadata.csv", timeout=60).text)))
    return [(r["file_id"], r["company_name"]) for r in rows]

def reference(fid):
    lines = HTTP.get(RAW + f"transcripts/nlp_references/{fid}.nlp", timeout=60).text.splitlines()[1:]
    return [(l.split("|")[0], l.split("|")[1]) for l in lines if l.strip()]

def norm(w): return re.sub(r"[^a-z0-9']", "", w.lower())

def audio(fid):
    p = CACHE / "audio" / f"{fid}.mp3"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(HTTP.get(RAW + f"media/{fid}.mp3", timeout=600).content)
    return p

def upload(fid):
    p = CACHE / f"{fid}.upload"
    if not p.exists():
        r = HTTP.post(f"{API}/upload", headers={"authorization": os.environ["ASSEMBLYAI_API_KEY"]}, data=audio(fid).read_bytes(), timeout=600)
        if r.status_code >= 400: raise SystemExit(f"upload failed {r.status_code}: {r.text[:300]}")
        p.write_text(r.json()["upload_url"])
    return p.read_text()

def transcribe(fid, name, opts):
    p = CACHE / f"{fid}-{name}.json"
    if p.exists(): return json.loads(p.read_text())
    h = {"authorization": os.environ["ASSEMBLYAI_API_KEY"]}
    r = HTTP.post(f"{API}/transcript", headers=h, json={"audio_url": upload(fid), "speaker_labels": True, **opts}, timeout=60)
    if r.status_code >= 400: raise SystemExit(f"transcript request failed {r.status_code}: {r.text[:300]}")
    tid = r.json()["id"]
    while True:
        j = HTTP.get(f"{API}/transcript/{tid}", headers=h, timeout=60).json()
        if j["status"] == "completed": break
        if j["status"] == "error": raise SystemExit(f"{fid} {name}: {j.get('error')}")
        time.sleep(5)
    out = {"text": j.get("text", ""), "words": [{"text": w["text"], "speaker": w.get("speaker")} for w in j.get("words", [])]}
    p.write_text(json.dumps(out)); return out

NAME = r"([A-Z][a-z]+(?:\s[A-Z]\.)?\s(?:[A-Z][a-z]*[A-Z']?[a-z]+(?:-[A-Z][a-z]+)?))"
ANALYST = [r"(?i:question (?:comes|is coming) from)(?i: the line of)? " + NAME, r"(?i:go|turn) to(?i: the line of)? " + NAME + r"(?:,)? (?i:with|from|at|of)\b",
           r"(?i:next question is from)(?i: the line of)? " + NAME, r"(?i:line of) " + NAME]
HOSTS = [r"(?i:joining me|with me|joined by|on the call)(?i: today| this morning| this afternoon)?(?i: on the call)?(?i: are| is|,| today)?(.{0,240})"]

def estimate_speakers(text):
    """Speaker count from the call's own words: the operator, the executives the host introduces, each analyst the operator announces."""
    analysts = {m for pat in ANALYST for m in re.findall(pat, text)}
    execs = set()
    for pat in HOSTS:
        for chunk in re.findall(pat, text):
            execs |= set(re.findall(NAME, chunk))
    execs -= analysts
    return 1 + max(1, len(execs)) + len(analysts), sorted(execs), sorted(analysts)

def align(ref, hyp_words):
    """Word pairs (ref_speaker, hyp_speaker) for words both transcripts got right."""
    r = [norm(t) for t, _ in ref]; h = [norm(w["text"]) for w in hyp_words]
    sm = difflib.SequenceMatcher(None, r, h, autojunk=False); pairs = []
    for b in sm.get_matching_blocks():
        for k in range(b.size):
            if r[b.a + k]: pairs.append((ref[b.a + k][1], hyp_words[b.b + k]["speaker"]))
    return pairs

def wder(pairs):
    """Share of aligned words on the wrong speaker after the best one-to-one label mapping."""
    if not pairs: return float("nan")
    from scipy.optimize import linear_sum_assignment
    R = sorted({a for a, _ in pairs}); H = sorted({str(b) for _, b in pairs})
    c = collections.Counter((a, str(b)) for a, b in pairs)
    cost = [[-c[(a, b)] for b in H] for a in R]
    rows, cols = linear_sum_assignment(cost)
    right = sum(-cost[i][j] for i, j in zip(rows, cols))
    return 1 - right / len(pairs)

def wder_split(pairs, ref, brief_words=300):
    from scipy.optimize import linear_sum_assignment
    if not pairs: return float("nan"), float("nan"), float("nan")
    total = collections.Counter(s for _, s in ref)
    R = sorted({a for a, _ in pairs}); H = sorted({str(b) for _, b in pairs})
    c = collections.Counter((a, str(b)) for a, b in pairs)
    rows, cols = linear_sum_assignment([[-c[(a, b)] for b in H] for a in R])
    mapped = {R[i]: H[j] for i, j in zip(rows, cols)}
    def err(sel):
        g = [(a, str(b)) for a, b in pairs if sel(a)]
        return (sum(mapped.get(a) != b for a, b in g) / len(g)) if g else float("nan")
    return err(lambda a: True), err(lambda a: total[a] >= brief_words), err(lambda a: total[a] < brief_words)

def main(limit):
    need("ASSEMBLYAI_API_KEY"); CACHE.mkdir(exist_ok=True); rows = []
    for fid, company in files()[:limit]:
        ref = reference(fid); true_n = len({s for _, s in ref})
        base = transcribe(fid, "default", {})
        est, execs, analysts = estimate_speakers(base["text"])
        runs = {"default": base,
                "estimated": transcribe(fid, f"estimated{est}", {"speaker_options": {"min_speakers_expected": est, "max_speakers_expected": est + 2}}),
                "oracle": transcribe(fid, f"oracle{true_n}", {"speakers_expected": true_n})}
        res = {"file": fid, "company": company, "true": true_n, "est_count": est}
        for k, t in runs.items():
            pairs = align(ref, t["words"]); res[k] = wder(pairs); res[k + "_n"] = len(pairs)
            _, res[k + "_frequent"], res[k + "_brief"] = wder_split(pairs, ref)
            res[k + "_labels"] = len({w["speaker"] for w in t["words"] if w["speaker"]})
        rows.append(res)
        print(f"  {company[:24]:24s} true {true_n:2d} | est {est:2d} | WDER default {res['default']:.3f} ({res['default_labels']} labels) "
              f"| estimated {res['estimated']:.3f} | oracle {res['oracle']:.3f}", flush=True)
    def agg(k):
        n = sum(r[k + "_n"] for r in rows); return sum(r[k] * r[k + "_n"] for r in rows) / n if n else float("nan")
    over = [r for r in rows if r["true"] > 10]
    out = [f"# AssemblyAI diarization on Earnings-21, {dt.date.today()}", "",
           f"{len(rows)} earnings calls, Rev's speaker labels as ground truth. WDER is the share of correctly transcribed words attributed to the wrong speaker; lower is better.", "",
           "| Setup | WDER, all calls | WDER, calls with more than 10 speakers | Error on frequent speakers | Error on brief speakers (under 300 words) |", "|---|---|---|---|---|"]
    for name, k in [("AssemblyAI default", "default"), ("Speaker count read from the transcript, passed as speaker_options", "estimated"), ("True speaker count (ceiling)", "oracle")]:
        sub = (sum(r[k] * r[k + "_n"] for r in over) / sum(r[k + "_n"] for r in over)) if over else float("nan")
        out.append(f"| {name} | {agg(k):.3f} | {sub:.3f} | {statistics.mean(r[k + '_frequent'] for r in rows):.3f} | {statistics.mean(x for x in (r[k + '_brief'] for r in rows) if x == x):.3f} |")
    out += ["", "| Call | Company | True speakers | Read from transcript | Default labels | WDER default | estimated | true count |", "|---|---|---|---|---|---|---|---|"]
    out += [f"| {r['file']} | {r['company']} | {r['true']} | {r['est_count']} | {r['default_labels']} | {r['default']:.3f} | {r['estimated']:.3f} | {r['oracle']:.3f} |" for r in rows]
    out += ["", "## Honest limits", "",
            "- WDER only scores words both transcripts agree on, so it measures speaker attribution, not transcription accuracy.",
            "- The speaker-count reader is a handful of regex patterns for how earnings-call operators talk. It is domain-specific by design.",
            "- Ten calls. Per-call WDER swings a lot; the word-weighted totals are the result.",
            "- The true-count row uses Rev's labels, so no real deployment gets it. It shows how much of the gap the estimate closes."]
    s = "\n".join(out); (ROOT / "results").mkdir(exist_ok=True); (ROOT / "results" / f"{dt.date.today()}.md").write_text(s, encoding="utf-8"); print(s)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=10); main(ap.parse_args().limit)
