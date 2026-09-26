#!/usr/bin/env python3
"""LLM/RL/训练/Agent 实习监控（法国 + 美国）。
每次运行：拉全部源 -> 归一化 -> 过滤(实习 × 主题 × 地区) -> 与 state.json 比对 -> 邮件通知新增。
用法：python3 monitor.py [--full] [--dry] [--days N]
  --full  邮件里发全部命中（不只新增），用于首轮基线
  --dry   不发邮件，只打印
  --days  LinkedIn 只看最近 N 天（默认 7）
"""
import json, os, re, sys, time, html, ssl, smtplib, urllib.request, urllib.parse, urllib.error, datetime as dt
from email.mime.text import MIMEText
from email.header import Header

BASE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE, "state.json")
LOG = os.path.join(BASE, "monitor.log")
ARGS = set(a for a in sys.argv[1:] if a.startswith("--"))
DAYS = 7
for i, a in enumerate(sys.argv):
    if a == "--days": DAYS = int(sys.argv[i + 1])

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9,fr;q=0.8"}
CTX = ssl.create_default_context()
FAILS = []

def log(msg):
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f: f.write(line + "\n")

def get(url, data=None, hdr=None, timeout=30, retries=2):
    h = dict(UA); h.update(hdr or {})
    for i in range(retries + 1):
        try:
            r = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503, 999) and i < retries: time.sleep(6 * (i + 1)); continue
            return e.code, ""
        except Exception as e:
            if i < retries: time.sleep(3); continue
            return -1, str(e)[:100]
    return -1, ""

def strip(s): return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ")
def sq(s): return re.sub(r"\s+", " ", s or "").strip()

# ---------------- sources ----------------
ASHBY = ("mistral.ai hcompany dust nabla gladia photoroom ami poolside alan qonto ledger sorare pennylane doctolib owkin inato "
         "elevenlabs alpic whitecircle kestra omi adaption akur8 backmarket seloger sunday voodoo tako "
         "openai cohere perplexity cursor cognition sierra harvey fireworks cerebras modal thinkingmachines replit runway suno "
         "pika synthesia notion linear supabase langchain llamaindex factory rogo ramp inngest temporal lexroom ssi snowflake").split()
GREENHOUSE = "anthropic xai togetherai datadog scaleai helsing databricks dataiku algolia mirakl magic thealleninstitute characterai waymo glean writer cresta abridge openevidence hippocraticai".split()
LEVER = "tri palantir agicap aircall blablacar contentsquare pigment qonto scality swile".split()
WORKABLE = "huggingface".split()

def src_ashby(rows):
    for t in ASHBY:
        c, b = get(f"https://api.ashbyhq.com/posting-api/job-board/{t}")
        if c != 200 or not b.startswith("{"): FAILS.append(f"ashby/{t}:{c}"); continue
        for j in json.loads(b).get("jobs", []):
            if j.get("isListed") is False: continue
            locs = [j.get("location") or ""] + [s.get("location", "") for s in (j.get("secondaryLocations") or [])]
            if j.get("isRemote"): locs.append("Remote")
            rows.append(dict(src="ashby", company=t, title=j.get("title", ""), loc=", ".join(l for l in locs if l),
                             etype=j.get("employmentType", ""), pub=(j.get("publishedAt") or "")[:10],
                             url=j.get("jobUrl", ""), desc=j.get("descriptionPlain") or ""))

def src_greenhouse(rows):
    for t in GREENHOUSE:
        c, b = get(f"https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true")
        if c != 200 or not b.startswith("{"): FAILS.append(f"greenhouse/{t}:{c}"); continue
        for j in json.loads(b).get("jobs", []):
            loc = (j.get("location") or {}).get("name", "")
            offs = [o.get("name", "") for o in (j.get("offices") or [])]
            rows.append(dict(src="greenhouse", company=t, title=j.get("title", ""), loc=", ".join([loc] + offs),
                             etype="", pub=(j.get("first_published") or j.get("updated_at") or "")[:10],
                             url=j.get("absolute_url", ""), desc=strip(j.get("content", ""))))

def src_lever(rows):
    for t in LEVER:
        c, b = get(f"https://api.lever.co/v0/postings/{t}?mode=json")
        if c != 200 or not b.startswith("["): FAILS.append(f"lever/{t}:{c}"); continue
        for j in json.loads(b):
            cat = j.get("categories") or {}
            ts = j.get("createdAt"); pub = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).strftime("%Y-%m-%d") if ts else ""
            rows.append(dict(src="lever", company=t, title=j.get("text", ""),
                             loc=", ".join(x for x in [cat.get("location", ""), j.get("country", ""), j.get("workplaceType", "")] if x),
                             etype=cat.get("commitment", ""), pub=pub, url=j.get("hostedUrl", ""),
                             desc=j.get("descriptionPlain") or strip(j.get("description", ""))))

def src_workable(rows):
    for t in WORKABLE:
        c, b = get(f"https://apply.workable.com/api/v1/widget/accounts/{t}?details=true")
        if c != 200 or not b.startswith("{"): FAILS.append(f"workable/{t}:{c}"); continue
        for j in json.loads(b).get("jobs", []):
            rows.append(dict(src="workable", company=t, title=j.get("title", ""),
                             loc=", ".join(x for x in [j.get("city", ""), j.get("state", ""), j.get("country", ""), "Remote" if j.get("remote") else ""] if x),
                             etype=j.get("employment_type", ""), pub=(j.get("published_on") or j.get("published") or "")[:10],
                             url=j.get("url", "") or j.get("application_url", ""), desc=strip(j.get("description", ""))))

def src_nvidia(rows):
    base = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite"
    hdr = {"Content-Type": "application/json", "Accept": "application/json"}
    got = []
    for off in range(0, 400, 20):
        body = json.dumps({"appliedFacets": {"workerSubType": ["0c40f6bd1d8f10adf6dae42e46d44a17"]}, "limit": 20, "offset": off, "searchText": ""}).encode()
        c, b = get(base + "/jobs", data=body, hdr=hdr)
        if c != 200: FAILS.append(f"nvidia:{c}"); break
        js = json.loads(b).get("jobPostings", [])
        got += js
        if len(js) < 20: break
    for j in got:
        t = j.get("title", "")
        if not (T_TITLE.search(t) or T_RESEARCH.search(t)): continue  # 只对标题命中的取详情（省请求）
        c, b = get(base + j.get("externalPath", ""), hdr={"Accept": "application/json"})
        info = json.loads(b).get("jobPostingInfo", {}) if c == 200 else {}
        loc = ", ".join([info.get("location", "")] + [x for x in (info.get("additionalLocations") or [])]) or j.get("locationsText", "")
        rows.append(dict(src="nvidia", company="NVIDIA", title=t, loc=loc, etype="Intern",
                         pub=(info.get("startDate") or "")[:10], url="https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite" + j.get("externalPath", ""),
                         desc=strip(info.get("jobDescription", ""))))
        time.sleep(0.5)

def src_amazon(rows):
    for country in ("FRA", "USA"):
        for q in ("machine learning", "language model", "reinforcement learning", "generative AI"):
            u = "https://www.amazon.jobs/en/search.json?" + urllib.parse.urlencode({"base_query": q, "country": country, "job_type": "Internship", "result_limit": 100, "offset": 0})
            c, b = get(u)
            if c != 200: FAILS.append(f"amazon/{country}:{c}"); continue
            for j in json.loads(b).get("jobs", []):
                rows.append(dict(src="amazon", company="Amazon", title=j.get("title", ""), loc=j.get("normalized_location", "") or country,
                                 etype=j.get("job_schedule_type", ""), pub=(j.get("posted_date") or "")[:10],
                                 url="https://www.amazon.jobs" + j.get("job_path", ""), desc=strip(j.get("description_short", "") or j.get("description", ""))))
            time.sleep(0.5)

def src_google(rows):
    seen = set()
    for q in ("intern", "student researcher", "research intern"):
        for page in (1, 2, 3):
            u = "https://www.google.com/about/careers/applications/jobs/results/?" + urllib.parse.urlencode({"q": q, "location": ["France", "United States"], "employment_type": "INTERN", "page": page}, doseq=True)
            c, b = get(u)
            if c != 200: FAILS.append(f"google:{c}"); break
            found = re.findall(r"jobs/results/(\d+)-([\w-]+)", b)
            if not found: break
            for jid, slug in found:
                if jid in seen: continue
                seen.add(jid)
                rows.append(dict(src="google", company="Google/DeepMind", title=slug.replace("-", " ").title(), loc="",
                                 etype="Intern", pub="", url=f"https://www.google.com/about/careers/applications/jobs/results/{jid}-{slug}", desc=""))
            time.sleep(1)

def src_apple(rows):
    for q in ("machine learning intern", "AI research intern", "large language model"):
        u = "https://jobs.apple.com/en-us/search?" + urllib.parse.urlencode({"search": q, "sort": "newest", "location": "united-states-USA+france-FRAC"})
        c, b = get(u)
        if c != 200: FAILS.append(f"apple:{c}"); continue
        for jid, inner in re.findall(r'<a[^>]+href="/en-us/details/(\d+)[^"]*"[^>]*>(.*?)</a>', b, re.S):
            rows.append(dict(src="apple", company="Apple", title=sq(strip(inner)), loc="", etype="",
                             pub="", url=f"https://jobs.apple.com/en-us/details/{jid}", desc=""))
        time.sleep(1)

def src_inria(rows):
    c, b = get("https://jobs.inria.fr/public/classic/en/offres?type=Stage")
    if c != 200: FAILS.append(f"inria:{c}"); return
    seen = set()
    for m in re.finditer(r'href="(/public/classic/en/offres/([\w-]+))"[^>]*>(.*?)</a>', b, re.S):
        path, jid, inner = m.groups()
        title = sq(strip(inner))
        if jid in seen or not title or jid == "map": continue
        seen.add(jid)
        # 取标题后 600 字的上下文作为简述（含团队/地点）
        ctxt = sq(strip(b[m.end():m.end() + 1500]))[:400]
        rows.append(dict(src="inria", company="Inria", title=title, loc="France " + ctxt[:120], etype="",
                         pub="", url="https://jobs.inria.fr" + path, desc=ctxt))

LI_CARD = re.compile(r"<li>(.*?)</li>", re.S)
LI_F = {k: re.compile(p, re.S) for k, p in dict(
    urn=r'data-entity-urn="urn:li:jobPosting:(\d+)"', title=r'class="base-search-card__title"[^>]*>\s*(.*?)\s*</h3>',
    comp=r'class="base-search-card__subtitle"[^>]*>\s*(?:<a[^>]*>)?\s*(.*?)\s*(?:</a>)?\s*</h4>',
    loc=r'class="job-search-card__location"[^>]*>\s*(.*?)\s*</span>', date=r'<time[^>]*datetime="([\d-]+)"',
    link=r'<a class="base-card__full-link[^"]*"\s+href="([^"?]+)').items()}
LI_Q = {"France": ["LLM intern", "stage LLM", "stage agent IA", "stage reinforcement learning", "stage NLP deep learning", "stage recherche IA",
                   "research intern machine learning", "post-training intern", "stage fine-tuning modèle", "stage IA générative"],
        "United States": ["LLM research intern", "reinforcement learning intern", "AI research intern", "machine learning research intern",
                          "LLM agent intern", "post-training intern", "foundation model intern", "NLP research intern"]}

def src_linkedin(rows):
    seen = set()
    for loc, kws in LI_Q.items():
        for kw in kws:
            for start in (0, 25, 50):
                u = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + urllib.parse.urlencode(
                    {"keywords": kw, "location": loc, "f_JT": "I", "f_TPR": f"r{DAYS * 86400}", "start": start})
                c, b = get(u)
                if c != 200 or not b:
                    if c != 200: FAILS.append(f"linkedin:{c}")
                    break
                cards = LI_CARD.findall(b)
                if not cards: break
                for blk in cards:
                    m = LI_F["urn"].search(blk)
                    if not m or m.group(1) in seen: continue
                    seen.add(m.group(1))
                    g = lambda k: sq(strip(LI_F[k].search(blk).group(1))) if LI_F[k].search(blk) else ""
                    rows.append(dict(src="linkedin", company=g("comp"), title=g("title"), loc=g("loc") or loc, etype="Internship",
                                     pub=g("date"), url=(LI_F["link"].search(blk).group(1) if LI_F["link"].search(blk) else f"https://www.linkedin.com/jobs/view/{m.group(1)}"),
                                     desc=""))
                if len(cards) < 10: break
                time.sleep(1.5)
            time.sleep(1)

# ---------------- filters ----------------
T_INTERN = re.compile(r"\bintern(ship|s|e|es)?\b|\bstage\b|stagiaire|student researcher|\bco-?op\b|\bthesis\b|\bph\.?d\.? intern|research assistant", re.I)
T_TITLE = re.compile(r"llm|language model|foundation model|frontier|reinforcement|\brl\b|rlhf|post-?training|pre-?training|pretrain|fine-?tun|alignment|"
                     r"\bagents?\b|agentic|genai|gen ai|generative|g[ée]n[ée]rati|\bnlp\b|natural language|deep learning|multimodal|reasoning|interpretab|ai safety|"
                     r"model training|llm inference|\bml research|speech|transformer|diffusion|vision-language|\bvlm\b|world model|"
                     r"mod[èe]les? de langage|apprentissage par renforcement|apprentissage profond|intelligence artificielle|\bia\b", re.I)
T_RESEARCH = re.compile(r"research intern|research scientist|research engineer|ai research|machine learning research|applied scien|ai scientist|ai engineer|"
                        r"machine learning engineer|\bml engineer|\bml\b intern|machine learning intern|\bai\b.*intern|intern.*\bai\b|recherche", re.I)
T_DESC = re.compile(r"llm|large language|language model|foundation model|reinforcement learning|\brl\b|rlhf|rlvr|grpo|\bppo\b|post-?training|pre-?training|"
                    r"fine-?tun|alignment|agentic|multi-?agent|\bagents?\b|tool[- ]use|function calling|\bmcp\b|generative ai|genai|\btransformers?\b|"
                    r"model training|distributed training|diffusion|\bnlp\b|natural language|multimodal|vision-language|reasoning|interpretab|"
                    r"modèles? de langage|apprentissage par renforcement|ia générative", re.I)
T_GENERIC = re.compile(r"machine learning|\bml\b|\bai\b|\bia\b|data scien|research|scientist|deep learning|science", re.I)
G_FR = re.compile(r"\bfrance\b|paris|île-de-france|ile-de-france|saclay|palaiseau|grenoble|\blyon\b|toulouse|sophia|nantes|lille|bordeaux|montpellier|rennes|"
                  r"strasbourg|\bnice\b|marseille|v[ée]lizy|orsay|gif-sur|massy|boulogne|nanterre|issy|puteaux|levallois|montrouge|courbevoie|saint-denis|clichy|neuilly|rueil|versailles|[ée]vry", re.I)
G_US = re.compile(r"united states|\busa?\b|u\.s\.|san francisco|bay area|palo alto|mountain view|menlo park|sunnyvale|santa clara|san jose|redwood|cupertino|"
                  r"los angeles|seattle|bellevue|redmond|new york|\bnyc\b|boston|cambridge, ma|austin|chicago|pittsburgh|denver|remote \(us|us remote|remote - us|"
                  r"\bcalifornia\b|\bwashington\b|\bmassachusetts\b|\btexas\b|"
                  r", (al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy)\b", re.I)
T_START = re.compile(r"[^.\n]{0,60}(?:avril|april|printemps|spring|\bmars\b|march|\bmai\b|\bmay 2027|2027|f[ée]vrier|february)[^.\n]{0,60}", re.I)
ALT_ONLY = re.compile(r"alternan|apprenti|apprenticeship", re.I)
T_AIGEN = re.compile(r"intelligence artificielle|\bia\b", re.I)  # 标题只含这些 = 泛 AI，降 B
PUB = "/opt/dingyuanying-chat/nginx/certbot-www/.well-known/acme-challenge/intern-7f3a-latest_report.txt"  # 经 dyy.youchun.tech:80 公开，供云端 routine 取报告发邮件（云沙箱连不上 IP:8080）

ESN = re.compile(r"\balten\b|astek|aubay|capgemini|sopra|\batos\b|accenture|wavestone|\bey\b|\bbain\b|\bbcg\b|deloitte|kpmg|\bpwc\b|\bcgi\b|devoteam|inetum|onepoint|"
                 r"sia partners|\btalan\b|mc2i|converteo|expleo|akkodis|davidson|altran|segula|assystem|\beviden\b|mckinsey|quantumblack|infosys|wipro|tcs\b|cognizant|"
                 r"orange business|econocom|neurones|ausy|sii\b|alithya|magellan|keyrus|micropole|artefact|ekimetrics|fifty-five|niji", re.I)

def classify(r):
    title = r["title"]; desc = (r["desc"] or "")[:5000]
    is_intern = bool(T_INTERN.search(title) or T_INTERN.search(r.get("etype", "")) or r["src"] in ("google", "nvidia"))
    if not is_intern: return None
    if ALT_ONLY.search(title) and not T_INTERN.search(title): return None
    core = [m.group(0) for m in T_TITLE.finditer(title) if not T_AIGEN.fullmatch(m.group(0))]
    if core: tier = "A"
    elif T_TITLE.search(title): tier = "A" if T_DESC.search(desc) else "B"  # 标题只有泛 IA/AI
    elif T_RESEARCH.search(title): tier = "A" if T_DESC.search(desc) else ("B" if not desc else None)
    elif T_DESC.search(desc) and T_GENERIC.search(title): tier = "B"
    else: tier = None
    if not tier: return None
    if ESN.search(r["company"]): tier = "C"
    loc = r["loc"] or ""
    geo = "FR" if G_FR.search(loc) else "US" if G_US.search(loc) else "?"
    if geo == "?" and r["src"] == "linkedin": geo = "FR" if "France" in loc else "US"
    if geo == "?" and loc: return None  # 有地点但既非法国也非美国
    m = T_START.search(desc)
    r.update(tier=tier, geo=geo, start_hint=sq(m.group(0))[:140] if m else "")
    return r

def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())

# ---------------- main ----------------
def main():
    rows = []
    for name, fn in [("ashby", src_ashby), ("greenhouse", src_greenhouse), ("lever", src_lever), ("workable", src_workable),
                     ("nvidia", src_nvidia), ("amazon", src_amazon), ("google", src_google), ("apple", src_apple), ("inria", src_inria), ("linkedin", src_linkedin)]:
        n0 = len(rows)
        try: fn(rows)
        except Exception as e: FAILS.append(f"{name}:EXC {type(e).__name__} {str(e)[:80]}")
        log(f"{name}: {len(rows) - n0} raw")
    hits, bykey = {}, {}
    for r in sorted(rows, key=lambda r: r["src"] == "linkedin"):  # 非 LinkedIn 源优先（有描述）
        c = classify(dict(r))
        if not c or not c["url"]: continue
        k = norm(c["company"])[:12] + "|" + norm(c["title"])
        if k in bykey: continue
        bykey[k] = 1; hits.setdefault(c["url"].split("?")[0], c)
    log(f"raw={len(rows)} hits={len(hits)} fails={len(FAILS)}")

    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    today = dt.date.today().isoformat()
    new = {k: v for k, v in hits.items() if k not in state}
    for k, v in new.items(): state[k] = dict(first_seen=today, title=v["title"], company=v["company"], geo=v["geo"], tier=v["tier"])
    if "--dry" not in ARGS: json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(list(hits.values()), open(os.path.join(BASE, "latest_hits.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    show = hits if "--full" in ARGS else new
    body = render(show, new, hits, today)
    open(os.path.join(BASE, "latest_report.txt"), "w", encoding="utf-8").write(body)
    if os.path.isdir(os.path.dirname(PUB)):
        open(PUB, "w", encoding="utf-8").write(body); os.chmod(PUB, 0o644)
    print(body)
    weekday = dt.date.today().weekday()
    if "--dry" in ARGS: return
    git_push(today)  # 报告+状态推到 GitHub，云端 routine 从仓库读（云沙箱出站只放行 GitHub 等白名单域名）
    if show or weekday == 0:  # 有新增才发；周一强制发一封心跳
        nfr = sum(1 for v in new.values() if v["geo"] == "FR"); nus = sum(1 for v in new.values() if v["geo"] == "US")
        subj = f"实习监控 {today} · {'全量' if '--full' in ARGS else '新增'} {len(show)}（FR {nfr} / US {nus}）· 库 {len(hits)}"
        try: send(subj, body)
        except Exception as e: log(f"SMTP failed ({type(e).__name__}: {e}); report published at {PUB} for the cloud mailer routine")

def render(show, new, hits, today):
    out = [f"实习监控 {today} · 新增 {len(new)} · 当前在挂命中 {len(hits)} · 显示 {len(show)}", ""]
    order = {"A": 0, "B": 1, "C": 2}
    for geo, flag in (("FR", "🇫🇷 FRANCE"), ("US", "🇺🇸 USA"), ("?", "🌐 Google/Apple（法国+美国合并查询，点开看地点）")):
        items = sorted([v for v in show.values() if v["geo"] == geo], key=lambda v: (order[v["tier"]], v["company"].lower(), v["title"]))
        if not items: continue
        out.append(f"{flag}  ({len(items)})")
        for v in items:
            meta = " · ".join(x for x in [sq(v['loc'])[:60], f"发布 {v['pub']}" if v["pub"] else "", f"[{v['src']}]"] if x)
            out.append(f"[{v['tier']}] {v['company']} — {sq(v['title'])}  ({meta})")
            if v["start_hint"]: out.append(f"    起始线索: …{v['start_hint']}…")
            out.append(f"    {v['url']}")
        out.append("")
    out.append("说明: [A]=标题直接命中 LLM/RL/训练/Agent/AI 研究；[B]=标题泛 ML/AI 研究但无描述可核；[C]=ESN/咨询公司（多为 adoption 非研发）。起始线索=描述里含 2027/春/4月 的句子，没有=帖子未写。")
    out.append(f"源: Ashby {len(ASHBY)} + Greenhouse {len(GREENHOUSE)} + Lever {len(LEVER)} + Workable {len(WORKABLE)} 个看板, NVIDIA, Amazon, Google, Apple, Inria, LinkedIn(FR {len(LI_Q['France'])} 词 / US {len(LI_Q['United States'])} 词, 近 {DAYS} 天)")
    if FAILS: out.append("失败源: " + ", ".join(sorted(set(FAILS))))
    return "\n".join(out)

def git_push(today):
    import subprocess
    if not os.path.isdir(os.path.join(BASE, ".git")): return
    try:
        subprocess.run(["git", "add", "-A"], cwd=BASE, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", f"report {today}"], cwd=BASE, capture_output=True)  # 无变化时 commit 失败可忽略
        r = subprocess.run(["git", "push", "-q"], cwd=BASE, capture_output=True, text=True, timeout=120)
        log("git push ok" if r.returncode == 0 else f"git push failed: {r.stderr.strip()[:200]}")
    except Exception as e:
        log(f"git push exception: {type(e).__name__}: {e}")

def send(subject, body):
    env = {}
    for line in open(os.path.join(BASE, "secrets.env"), encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1); env[k] = v
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8"); msg["From"] = env["SMTP_USER"]; msg["To"] = env["MAIL_TO"]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as s:
        s.login(env["SMTP_USER"], env["SMTP_PASS"]); s.sendmail(env["SMTP_USER"], env["MAIL_TO"].split(","), msg.as_string())
    log(f"SENT: {subject}")

if __name__ == "__main__":
    main()
