import json, time, urllib.request
def ask(q, mt=600):
    body = {"model": "minimax-m3.1-flash", "messages": [{"role": "user", "content": q}], "max_tokens": mt, "temperature": 0}
    t = time.time()
    req = urllib.request.Request("http://localhost:8000/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=600))
    m = r["choices"][0]["message"]; u = r["usage"]
    ans = (m.get("content") or "").strip()
    rs = m.get("reasoning_content") or m.get("reasoning") or ""
    print("Q:", q)
    print("  answer   :", repr(ans[:400]))
    print("  reasoning: %d chars | %d tok in %.1fs | finish %s\n" % (len(rs), u["completion_tokens"], time.time() - t, r["choices"][0]["finish_reason"]))
ask("What is the capital of France? Answer with one word.")
ask("What is 17 * 23? Reply with just the number.")
ask("Write a Python function is_prime(n). Code only, no explanation.", 800)
ask("Translate to French: The weather is beautiful today.")
