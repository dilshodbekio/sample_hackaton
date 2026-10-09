"""ask/stream tekshiruvi: python tests/ask_check.py '<json body>' """
import sys, json, time, httpx
body = sys.argv[1]
t0 = time.time(); ev = []
with httpx.stream("POST", "http://localhost:8001/ask/stream", content=body.encode(), headers={"Content-Type": "application/json"}, timeout=60) as r:
    print("HTTP", r.status_code, r.headers.get("content-type"))
    buf = ""
    for c in r.iter_text():
        buf += c
        while "\n\n" in buf:
            raw, buf = buf.split("\n\n", 1)
            lines = raw.split("\n")
            e = lines[0][7:]; d = json.loads(lines[1][6:])
            ev.append((round(time.time()-t0, 2), e, d))
print("order:", [e for _, e, _ in ev if e != "token"][:5], "tokens:", sum(e == "token" for _, e, _ in ev))
toks = [t for t, e, _ in ev if e == "token"]
if toks: print("first/last token t:", toks[0], toks[-1])
print("text:", "".join(d["text"] for _, e, d in ev if e == "token")[:400])
for _, e, d in ev:
    if e != "token": print(e, json.dumps(d, ensure_ascii=False)[:600])
