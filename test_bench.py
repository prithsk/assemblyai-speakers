import bench
ref = [("good", "0"), ("morning", "0"), ("thanks", "1"), ("everyone", "1"), ("hi", "2"), ("there", "2")]
same = [{"text": w, "speaker": s} for w, s in [("Good", "A"), ("morning,", "A"), ("thanks", "B"), ("everyone.", "B"), ("hi", "C"), ("there", "C")]]
assert bench.wder(bench.align(ref, same)) == 0.0                                    # different label names, same split
merged = [{"text": w, "speaker": s} for w, s in [("good", "A"), ("morning", "A"), ("thanks", "B"), ("everyone", "B"), ("hi", "B"), ("there", "B")]]
assert abs(bench.wder(bench.align(ref, merged)) - 2 / 6) < 1e-9                     # speakers 1 and 2 merged
ins = [{"text": "um", "speaker": "A"}] + same
assert len(bench.align(ref, ins)) == 6                                              # an inserted word doesn't break alignment
text = ("Good morning. Joining me today are Mike Broderick, our CEO, and Brian D'Ambrosia, our CFO. "
        "Our first question comes from Bret Jordan with Jefferies. Thanks. Our next question comes from the line of Daniel Imbro. "
        "We'll go to Scot Ciccarelli with Truist.")
n, execs, analysts = bench.estimate_speakers(text)
assert set(analysts) == {"Bret Jordan", "Daniel Imbro", "Scot Ciccarelli"}, analysts
assert "Mike Broderick" in execs and n == 1 + len(execs) + 3, (n, execs)
print("all tests passed")
