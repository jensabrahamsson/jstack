#!/usr/bin/env python3
"""Token usage and API list-price estimate for OpenAI models.

Reads Codex CLI session logs and a JSONL ledger of OpenAI API usage
objects, drops duplicates, attributes usage to role, task and attempt, and
prices it with a pinned copy of OpenAI's API price list.

OpenAI models only. Python 3.9+ standard library only. The tool reads
ids, model names, service tiers, timestamps and token counts; it never
reads or writes prompts, messages, code or tool output.

The USD figure is always a list-price calculation, never a bill.
"""

import argparse
import collections
import glob
import hashlib
import json
import os
import re
import sys
from decimal import Decimal

STATUS_RANK = {"exact": 0, "estimate": 1, "lower_bound": 2, "unknown": 3}
MILLION = Decimal(1000000)
CATEGORIES = ("input", "cached", "cache_write", "output", "reasoning")
DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------

def new_record(**kw):
    rec = {
        "source": None,          # codex-session | codex-token-count | ledger
        "run": None,             # Codex thread id or ledger run id
        "parent_run": None,      # Codex parent thread id (subagent)
        "key": None,             # dedupe key (response id / call id)
        "timestamp": None,
        "model": None,
        "model_evidence": None,  # response | requested | None
        "tier": None,            # standard | batch | flex | fast | ultrafast
        "tier_evidence": None,   # response | declared | configured | assumed
        "billing": None,         # subscription | api | None
        "billing_evidence": None,
        "granularity": "request",  # request | aggregate
        "api": None,
        "input": None, "cached": None, "cache_write": None,
        "write_30m": None, "write_12h": None,
        "output": None, "reasoning": None,
        "nontext": False,
        "flags": [],
    }
    rec.update(kw)
    return rec


def count(value):
    """A token count, or None when missing or malformed. Never coerces to 0."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def dig(obj, *path):
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def short_str(value, limit=120):
    return value if isinstance(value, str) and len(value) <= limit else None


# --------------------------------------------------------------------------
# Codex CLI session logs ($CODEX_HOME/sessions/**/rollout-*-<thread>.jsonl)
# --------------------------------------------------------------------------

def iter_json_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                yield event


def codex_meta(path, max_lines=20):
    """First session_meta of a session file: this thread's own metadata."""
    for i, event in enumerate(iter_json_lines(path)):
        if event.get("type") == "session_meta" and isinstance(event.get("payload"), dict):
            p = event["payload"]
            return {
                "thread_id": short_str(p.get("id")),
                "session_id": short_str(p.get("session_id")),
                "parent_thread_id": short_str(p.get("parent_thread_id")),
                "forked": bool(p.get("forked_from_id")),
            }
        if i >= max_lines:
            break
    return None


def parse_codex_file(path, tier_map):
    """Return (meta, records). Reads only allow-listed metadata fields."""
    meta = codex_meta(path) or {"thread_id": None, "session_id": None,
                                "parent_thread_id": None, "forked": False}
    thread = meta["thread_id"]
    turn_model = {}
    latest_model = None
    configured_tier = None
    plan_type = None
    records = []
    fallback = []
    prev_total = None

    for event in iter_json_lines(path):
        etype = event.get("type")
        p = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = short_str(event.get("timestamp"), 40)
        if etype == "turn_context":
            model = short_str(p.get("model"), 80)
            turn_model[p.get("turn_id")] = model
            latest_model = model
        elif etype == "event_msg" and p.get("type") == "thread_settings_applied":
            tier = short_str(dig(p, "thread_settings", "service_tier"), 40)
            if tier:
                configured_tier = tier
        elif etype == "event_msg" and p.get("type") == "token_count":
            plan = short_str(dig(p, "rate_limits", "plan_type"), 40)
            if plan:
                plan_type = plan
            info = p.get("info")
            if isinstance(info, dict):
                fallback.append((ts, latest_model, configured_tier, info))
        elif etype == "token_usage_record":
            u = p.get("usage") if isinstance(p.get("usage"), dict) else {}
            write = count(u.get("cache_write_input_tokens"))
            run = short_str(p.get("thread_id")) or thread
            rec = new_record(
                source="codex-session", run=run,
                # A record copied from another thread (fork, resume) keeps
                # that thread; this file's parent is not its parent.
                parent_run=meta["parent_thread_id"] if run == thread else None,
                key=short_str(p.get("response_id")),
                timestamp=ts, api="codex",
                model=turn_model.get(p.get("turn_id")),
                input=count(u.get("input_tokens")),
                cached=count(u.get("cached_input_tokens")),
                # Codex logs report 0 cache writes even when most input is a
                # cache read, so only a positive value counts as observed.
                cache_write=write if write else None,
                output=count(u.get("output_tokens")),
                reasoning=count(u.get("reasoning_output_tokens")),
            )
            rec["model_evidence"] = "requested" if rec["model"] else None
            rec["tier"] = tier_map.get(configured_tier) if configured_tier else None
            rec["tier_evidence"] = "configured" if rec["tier"] else None
            if rec["key"] is None:
                rec["flags"].append("no response id; duplicates cannot be detected")
            records.append(rec)

    if not records and fallback:
        # Older logs: token_count events carry a per-request
        # last_token_usage and a cumulative total_token_usage. A repeated
        # total is the same request reported twice. The first event counts
        # only its own request, so a total carried over from a resumed
        # session is not counted again.
        for ts, model, tier, info in fallback:
            total = info.get("total_token_usage") if isinstance(info.get("total_token_usage"), dict) else {}
            last = info.get("last_token_usage") if isinstance(info.get("last_token_usage"), dict) else {}
            fields = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
            snapshot = tuple(count(total.get(f)) for f in fields)
            known = any(v is not None for v in snapshot)
            if known and prev_total is not None and snapshot == prev_total:
                continue
            flags = ["from token_count events (no per-response id)"]
            if prev_total is None or any(a is None or b is None or a < b for a, b in zip(snapshot, prev_total)):
                values = tuple(count(last.get(f)) for f in fields)
                if prev_total is not None:
                    flags.append("cumulative counter went down; counted this request only")
            else:
                values = tuple(a - b for a, b in zip(snapshot, prev_total))
            prev_total = snapshot if known else prev_total
            rec = new_record(
                source="codex-token-count", run=thread, parent_run=meta["parent_thread_id"],
                # The cumulative total identifies the point in the thread, so
                # a resumed file that replays earlier events dedupes against
                # the original while new requests in it never collide.
                key=("token-count:%s:%s" % (thread, ",".join(str(v) for v in snapshot))
                     if thread and known else None),
                timestamp=ts, api="codex",
                model=model, model_evidence="requested" if model else None,
                input=values[0], cached=values[1], output=values[2], reasoning=values[3],
                flags=flags,
            )
            rec["tier"] = tier_map.get(tier) if tier else None
            rec["tier_evidence"] = "configured" if rec["tier"] else None
            records.append(rec)

    for rec in records:
        if plan_type:
            rec["billing"] = "subscription"
            rec["billing_evidence"] = "Codex rate_limits.plan_type=%s" % plan_type
    meta["path"] = path
    meta["usage_records"] = len(records)
    return meta, records


def codex_files(codex_home):
    roots = [os.path.join(codex_home, "sessions"), os.path.join(codex_home, "archived_sessions")]
    files = []
    for root in roots:
        files.extend(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True))
    return sorted(files)


def find_codex_threads(codex_home, thread_ids):
    """Session files for the given threads plus every subagent below them."""
    files = codex_files(codex_home)
    by_thread = {}
    children = collections.defaultdict(list)
    for path in files:
        meta = codex_meta(path)
        if not meta or not meta["thread_id"]:
            continue
        by_thread.setdefault(meta["thread_id"], []).append(path)
        if meta["parent_thread_id"]:
            children[meta["parent_thread_id"]].append(meta["thread_id"])
    wanted, queue = [], list(thread_ids)
    seen = set()
    while queue:
        tid = queue.pop(0)
        if tid in seen:
            continue
        seen.add(tid)
        wanted.extend(by_thread.get(tid, []))
        queue.extend(children.get(tid, []))
    return wanted, {t for t in thread_ids if t not in by_thread}


# --------------------------------------------------------------------------
# Ledger: one JSON object per OpenAI API response (metadata only)
# --------------------------------------------------------------------------

def usage_from_ledger(entry):
    api = entry.get("api")
    u = entry.get("usage")
    out = {k: None for k in ("input", "cached", "cache_write", "write_30m", "write_12h",
                             "output", "reasoning")}
    nontext = False
    if api == "normalized":
        for k, f in (("input", "input_tokens"), ("cached", "cached_input_tokens"),
                     ("cache_write", "cache_write_tokens"), ("write_30m", "cache_write_30m_tokens"),
                     ("write_12h", "cache_write_12h_tokens"), ("output", "output_tokens"),
                     ("reasoning", "reasoning_tokens")):
            out[k] = count(entry.get(f))
        return out, False
    if not isinstance(u, dict):
        return out, False
    if api in ("responses", "agents_turn"):
        out["input"] = count(u.get("input_tokens"))
        out["cached"] = count(dig(u, "input_tokens_details", "cached_tokens"))
        out["cache_write"] = count(dig(u, "input_tokens_details", "cache_write_tokens"))
        out["write_30m"] = count(dig(u, "input_tokens_details", "cache_write_tokens_details", "ttl_30m_tokens"))
        out["write_12h"] = count(dig(u, "input_tokens_details", "cache_write_tokens_details", "ttl_12h_tokens"))
        out["output"] = count(u.get("output_tokens"))
        out["reasoning"] = count(dig(u, "output_tokens_details", "reasoning_tokens"))
    elif api == "chat":
        out["input"] = count(u.get("prompt_tokens"))
        out["cached"] = count(dig(u, "prompt_tokens_details", "cached_tokens"))
        out["cache_write"] = count(dig(u, "prompt_tokens_details", "cache_write_tokens"))
        out["output"] = count(u.get("completion_tokens"))
        out["reasoning"] = count(dig(u, "completion_tokens_details", "reasoning_tokens"))
        for path in (("prompt_tokens_details", "audio_tokens"), ("prompt_tokens_details", "image_tokens"),
                     ("completion_tokens_details", "audio_tokens")):
            if (count(dig(u, *path)) or 0) > 0:
                nontext = True
    return out, nontext


def parse_ledger(path, tier_map):
    records, stream_prev = [], {}
    cumulative = collections.defaultdict(list)
    for n, entry in enumerate(iter_json_lines(path)):
        tokens, nontext = usage_from_ledger(entry)
        model = short_str(entry.get("model"), 80)
        evidence = short_str(entry.get("model_evidence"), 20) or ("response" if model else None)
        if not model and short_str(entry.get("requested_model"), 80):
            model, evidence = entry["requested_model"], "requested"
        tier_raw = short_str(entry.get("service_tier"), 40)
        tier, tier_ev = None, None
        if entry.get("batch") is True:
            tier, tier_ev = "batch", "declared"
        elif entry.get("api") == "normalized" and short_str(entry.get("tier"), 20):
            tier, tier_ev = entry["tier"], short_str(entry.get("tier_evidence"), 20)
        elif tier_raw in tier_map:
            tier, tier_ev = tier_map[tier_raw], "response"
        rec = new_record(
            source="ledger", run=short_str(entry.get("run")), api=short_str(entry.get("api"), 20),
            parent_run=short_str(entry.get("parent_run")) if entry.get("api") == "normalized" else None,
            key=short_str(entry.get("call_id")),
            timestamp=short_str(entry.get("timestamp"), 40), model=model,
            model_evidence=evidence if model else None, tier=tier, tier_evidence=tier_ev,
            billing=entry.get("billing") if entry.get("billing") in ("api", "subscription") else None,
            nontext=nontext, granularity=entry.get("granularity") if entry.get("granularity") in ("request", "aggregate") else "request",
        )
        rec.update(tokens)
        if rec["billing"]:
            rec["billing_evidence"] = "declared in ledger"
        if entry.get("cumulative") is True:
            stream = short_str(entry.get("stream")) or rec["run"] or "default"
            cumulative[stream].append((entry.get("seq", n), rec))
            continue
        if rec["key"] is None:
            rec["flags"].append("no call_id; duplicates cannot be detected")
        records.append(rec)

    # Cumulative snapshots: count the difference from the previous snapshot.
    for stream, snaps in cumulative.items():
        snaps.sort(key=lambda item: (item[0] if isinstance(item[0], int) else 0))
        prev = None
        for seq, rec in snaps:
            values = {k: rec[k] for k in ("input", "cached", "cache_write", "write_30m", "write_12h", "output", "reasoning")}
            if prev is not None and values == prev:
                continue
            delta = dict(values)
            reset = False
            if prev is not None:
                for k, v in values.items():
                    if v is None or prev[k] is None:
                        delta[k] = None
                    elif v < prev[k]:
                        reset = True
                    else:
                        delta[k] = v - prev[k]
                if reset:
                    delta = dict(values)
                    rec["flags"].append("cumulative counter went down; treated as a restart, attribution uncertain")
            prev = values
            rec.update(delta)
            rec["granularity"] = "aggregate"
            rec["key"] = "cumulative:%s:%s" % (stream, seq)
            rec["flags"].append("delta of a cumulative counter")
            records.append(rec)
    return records


# --------------------------------------------------------------------------
# Pricing
# --------------------------------------------------------------------------

def load_prices(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    table = json.loads(raw.decode("utf-8"))
    table["_path"] = path
    table["_sha256"] = hashlib.sha256(raw).hexdigest()
    return table


def rate(rates, name):
    value = rates.get(name)
    return Decimal(value) if value is not None else None


def price(rec, table):
    """Return {usd, status, notes}. usd is a Decimal or None.

    Rule: a split or rate that was not observed is priced at the cheapest
    value it could have had, and the result is marked lower_bound. A record
    without a known model, tier or any usage gets no amount (unknown).
    """
    notes = []

    def result(usd, status):
        return {"usd": usd, "status": status, "notes": notes}

    if rec["input"] is None and rec["output"] is None:
        notes.append("usage missing (unknown, not zero)")
        return result(None, "unknown")
    if rec["nontext"]:
        notes.append("audio or image tokens; not covered by the text price table")
        return result(None, "unknown")
    model = rec["model"]
    if not model:
        notes.append("model not observed")
        return result(None, "unknown")
    entry = table["models"].get(model)
    status = "exact"
    if entry is None and DATE_SUFFIX.search(model) and DATE_SUFFIX.sub("", model) in table["models"]:
        entry = table["models"][DATE_SUFFIX.sub("", model)]
        notes.append("snapshot %s priced as %s" % (model, DATE_SUFFIX.sub("", model)))
        status = "estimate"
    if entry is None:
        notes.append("model %s not in price table" % model)
        return result(None, "unknown")
    if rec["tier"] is None:
        notes.append("service tier not observed")
        return result(None, "unknown")
    tier = entry["tiers"].get(rec["tier"])
    if tier is None:
        notes.append("no %s price listed for %s" % (rec["tier"], model))
        return result(None, "unknown")
    if rec["model_evidence"] != "response":
        notes.append("model is the requested model, not confirmed by a response")
        status = "estimate"
    if rec["tier_evidence"] not in ("response", "declared"):
        notes.append("service tier %s is %s, not confirmed by a response" % (rec["tier"], rec["tier_evidence"]))
        status = "estimate"

    lower = []
    threshold = table["long_context_threshold_input_tokens"]
    if entry["context_pricing"] == "flat":
        rates = tier["all"]
    elif rec["input"] is not None and rec["input"] > threshold and rec["granularity"] == "request":
        rates = tier["long"]
        notes.append("long-context rates (input > %d tokens)" % threshold)
        if all(v is None for v in rates.values()):
            notes.append("no long-context %s price listed for %s" % (rec["tier"], model))
            return result(None, "unknown")
    else:
        rates = tier["short"]
        if rec["input"] is None or (rec["granularity"] == "aggregate" and rec["input"] > threshold):
            lower.append("request length unknown; short-context rates used")

    usd = Decimal(0)

    def add(tokens, rate_name, label):
        nonlocal usd
        if not tokens:
            return
        r = rate(rates, rate_name)
        if r is None:
            lower.append("no listed %s rate; %s tokens unpriced" % (label, label))
            return
        usd += Decimal(tokens) * r / MILLION

    separate_writes = entry.get("cache_writes_billed_separately", False)
    if rec["input"] is None:
        lower.append("input tokens missing")
    elif rec["cached"] is None:
        cheapest = "cached_input" if rate(rates, "cached_input") is not None else "input"
        add(rec["input"], cheapest, "input")
        lower.append("cached-input split missing; all input priced at the %s rate" % cheapest.replace("_", "-"))
    else:
        write = rec["cache_write"] if separate_writes else None
        ordinary = rec["input"] - rec["cached"] - (write or 0)
        if ordinary < 0:
            notes.append("inconsistent usage: cached and written tokens exceed input")
            return result(None, "unknown")
        add(ordinary, "input", "input")
        add(rec["cached"], "cached_input", "cached-input")
        if separate_writes and write is None:
            lower.append("cache writes not reported; uncached input priced at the ordinary input rate (writes cost 1.25x or 2.5x)")
        elif write:
            w30, w12 = rec["write_30m"], rec["write_12h"]
            if w30 is None or w12 is None or w30 + w12 != write:
                # 12-hour writes exist only in the Responses API, so a Chat
                # Completions write is a 30-minute write. Elsewhere the
                # 30-minute rate is the cheaper of the two.
                if rec["api"] != "chat":
                    lower.append("cache-write lifetime split missing; 30-minute write rate used")
                w30, w12 = write, 0
            add(w30, "cache_write_30m", "30-minute cache-write")
            add(w12, "cache_write_12h", "12-hour cache-write")
    if rec["output"] is None:
        lower.append("output tokens missing")
    else:
        if rec["reasoning"] is not None and rec["reasoning"] > rec["output"]:
            notes.append("inconsistent usage: reasoning exceeds output")
            return result(None, "unknown")
        add(rec["output"], "output", "output")  # reasoning is part of output

    until = entry.get("price_valid_until")
    if until and rec["timestamp"] and rec["timestamp"][:10] > until:
        notes.append("usage after the listed price's end date %s" % until)
        status = "estimate" if status == "exact" else status
    if lower:
        notes.extend(lower)
        status = "lower_bound"
    return result(usd, status)


# --------------------------------------------------------------------------
# Collection, attribution, aggregation
# --------------------------------------------------------------------------

def collect(args, table, attribution):
    tier_map = table["service_tier_map"]
    runs = attribution.get("runs", []) if attribution else []
    files, missing_threads = [], set()
    codex_ids = [r["id"] for r in runs if r.get("source", "codex") == "codex" and r.get("id")]
    if codex_ids:
        found, missing_threads = find_codex_threads(args.codex_home, codex_ids)
        files.extend(found)
    files.extend(args.codex_session or [])
    metas, records, unreadable = [], [], []
    for path in dict.fromkeys(os.path.realpath(f) for f in files):  # each file once
        try:
            meta, recs = parse_codex_file(path, tier_map)
        except OSError:
            unreadable.append(os.path.basename(path))  # a gap, never a crash
            continue
        metas.append(meta)
        records.extend(recs)
    for path in args.ledger or []:
        try:
            records.extend(parse_ledger(path, tier_map))
        except OSError:
            unreadable.append(os.path.basename(path))
    args.unreadable = unreadable

    unique, duplicates = [], 0
    seen = set()
    for rec in records:
        if rec["key"] is not None:
            if rec["key"] in seen:
                duplicates += 1
                continue
            seen.add(rec["key"])
        unique.append(rec)

    if args.assume_tier:
        for rec in unique:
            if rec["tier"] is None:
                rec["tier"], rec["tier_evidence"] = args.assume_tier, "assumed"
    return metas, unique, duplicates, missing_threads


def attribute(records, attribution, parents):
    """Attach role, task and attempt. A Codex subagent thread inherits the
    run of the nearest listed ancestor thread, and says so."""
    runs = {r["id"]: r for r in (attribution or {}).get("runs", []) if r.get("id")}
    default_billing = (attribution or {}).get("billing")
    for rec in records:
        run = runs.get(rec["run"])
        how = "listed"
        ancestor, hops = rec["parent_run"], 0
        while run is None and ancestor and hops < 20:
            if ancestor in runs:
                run, how = runs[ancestor], "subagent of %s" % ancestor
            ancestor, hops = parents.get(ancestor), hops + 1
        if run is None:
            rec["role"], rec["task"], rec["attempt"], rec["attribution"] = "unattributed", "-", None, "not listed"
        else:
            rec["role"] = run.get("role", "unattributed")
            rec["task"] = run.get("task", "-")
            rec["attempt"] = run.get("attempt")
            rec["outcome"] = run.get("outcome")
            rec["attribution"] = how
        if rec["billing"] is None:
            declared = (run or {}).get("billing") or default_billing
            if declared in ("api", "subscription"):
                rec["billing"], rec["billing_evidence"] = declared, "declared in attribution"


class Bucket(object):
    def __init__(self):
        self.calls = 0
        self.tokens = {k: 0 for k in CATEGORIES}
        self.unknown = {k: 0 for k in CATEGORIES}
        self.usd = Decimal(0)
        self.status = collections.Counter()
        self.models = set()

    def add(self, rec):
        self.calls += 1
        for k in CATEGORIES:
            if rec[k] is None:
                self.unknown[k] += 1
            else:
                self.tokens[k] += rec[k]
        if rec["price"]["usd"] is not None:
            self.usd += rec["price"]["usd"]
        self.status[rec["price"]["status"]] += 1
        self.models.add(rec["model"] or "unknown model")

    def worst(self):
        return max(self.status, key=lambda s: STATUS_RANK[s]) if self.status else "unknown"


def usd_label(bucket):
    worst = bucket.worst()
    amount = "$%s" % bucket.usd.quantize(Decimal("0.0001"))
    if worst == "unknown" and bucket.status["unknown"] == bucket.calls:
        return "unknown"
    if worst in ("lower_bound", "unknown"):
        return "at least " + amount
    if worst == "estimate":
        return "~" + amount
    return amount


def calls(n):
    return "%d call%s" % (n, "" if n == 1 else "s")


def tok(bucket, key):
    value = "{:,}".format(bucket.tokens[key])
    if bucket.unknown[key]:
        if bucket.unknown[key] == bucket.calls:
            return "unknown"
        return ">= %s (%s unknown)" % (value, calls(bucket.unknown[key]))
    return value


def summarize(args, table, attribution, metas, records, duplicates, missing_threads):
    for rec in records:
        rec["price"] = price(rec, table)
    parents = {m["thread_id"]: m["parent_thread_id"] for m in metas if m["thread_id"]}
    for rec in records:  # normalized records carry the chain without session files
        if rec["run"] and rec["parent_run"]:
            parents.setdefault(rec["run"], rec["parent_run"])
    attribute(records, attribution, parents)

    by_model = collections.OrderedDict()
    by_run = collections.OrderedDict()
    total = Bucket()
    retries = Bucket()
    for rec in sorted(records, key=lambda r: (r["timestamp"] or "", r["key"] or "")):
        by_model.setdefault(rec["model"] or "unknown model", Bucket()).add(rec)
        label = (rec["role"], rec["task"], rec["attempt"], rec.get("outcome"))
        by_run.setdefault(label, Bucket()).add(rec)
        total.add(rec)
        if isinstance(rec["attempt"], int) and rec["attempt"] > 1:
            retries.add(rec)

    runs = (attribution or {}).get("runs", [])
    seen_runs = {r["run"] for r in records} | {r["parent_run"] for r in records if r["parent_run"]}
    sessions_without_usage = [m for m in metas if m["usage_records"] == 0]
    coverage = {
        "runs_listed": len(runs),
        "runs_with_usage": [r["id"] for r in runs if r.get("id") in seen_runs],
        "runs_not_measured": [{"id": r.get("id"), "role": r.get("role"), "task": r.get("task"),
                               "note": r.get("note")} for r in runs if r.get("source") == "none"],
        "runs_without_usage": [{"id": r.get("id"), "role": r.get("role"), "task": r.get("task"),
                                "reason": "session file not found" if r.get("id") in missing_threads else "no usage records"}
                               for r in runs if r.get("source", "codex") != "none" and r.get("id") not in seen_runs],
        "session_files": len(metas),
        "files_not_readable": list(getattr(args, "unreadable", [])),
        "session_files_without_usage": [os.path.basename(m["path"]) for m in sessions_without_usage
                                        if m["thread_id"] not in {r.get("id") for r in runs}],
        "duplicates_ignored": duplicates,
        "calls": len(records),
        "calls_by_status": dict(total.status),
        "unattributed_calls": sum(1 for r in records if r["role"] == "unattributed"),
        "subagent_calls": sum(1 for r in records if r["attribution"].startswith("subagent")),
        "notes": collections.Counter(n for r in records for n in r["price"]["notes"] + r["flags"]),
        "billing": collections.Counter("%s (%s)" % (r["billing"] or "unknown", r["billing_evidence"] or "not observed")
                                       for r in records),
    }
    return {"by_model": by_model, "by_run": by_run, "total": total, "retries": retries,
            "coverage": coverage, "records": records}


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

EXCLUDED = [
    "Per-call tool fees (web search, file search) and hosted container sessions.",
    "The 10% regional-processing or FedRAMP uplift: the endpoint is not visible in usage.",
    "Audio, image and realtime tokens: the pinned table holds text-token rates only.",
]


def render_markdown(args, table, attribution, s):
    lines = []
    goal = args.goal or (attribution or {}).get("goal") or "unnamed goal"
    total = s["total"]
    cov = s["coverage"]
    lines.append("# OpenAI usage: %s" % goal)
    lines.append("")
    lines.append("OpenAI models only. **List-price calculation, not a bill.** "
                 "Prices: %s, retrieved %s (table `%s`, sha256 `%s`)."
                 % (table["source_url"], table["retrieved_at"], os.path.basename(table["_path"]), table["_sha256"]))
    lines.append("")
    counts = ", ".join("%d %s" % (n, st) for st, n in sorted(total.status.items(), key=lambda x: STATUS_RANK[x[0]]))
    lines.append("**Total at API list price: %s** over %s%s."
                 % (usd_label(total), calls(total.calls), " (%s)" % counts if counts else ""))
    if s["retries"].calls:
        lines.append("Of which retries (attempt > 1): %s over %s." % (usd_label(s["retries"]), calls(s["retries"].calls)))
    lines.append("")
    lines.append("## Billing")
    lines.append("")
    for label, n in cov["billing"].most_common():
        lines.append("- %s: %s" % (calls(n), label))
    if any(k.startswith("subscription") for k in cov["billing"]):
        lines.append("- Subscription calls are not billed per token. Their USD figure is a hypothetical: what the same "
                     "tokens would cost at API list price. OpenAI's Codex pricing page: \"API token prices are separate "
                     "from subscription usage; don't use them to estimate included tasks.\"")
    if any(k.startswith("api") for k in cov["billing"]):
        lines.append("- API calls are billed per token; this figure is an estimate. Reconcile with the organization's billing records.")
    if any(k.startswith("unknown") for k in cov["billing"]):
        lines.append("- Unknown billing: no evidence of how these calls were paid for.")
    lines.append("")
    header = "| {} | Calls | Input | Cached input | Cache writes | Output | Reasoning (in output) | List price | Status |"
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---|"

    def row(name, b):
        return "| %s | %d | %s | %s | %s | %s | %s | %s | %s |" % (
            name, b.calls, tok(b, "input"), tok(b, "cached"), tok(b, "cache_write"), tok(b, "output"),
            tok(b, "reasoning"), usd_label(b), b.worst())

    lines.append("## By model")
    lines.append("")
    lines.append(header.format("Model"))
    lines.append(sep)
    for model, b in s["by_model"].items():
        lines.append(row("`%s`" % model, b))
    lines.append(row("**Total**", total))
    lines.append("")
    lines.append("## By role, task and attempt")
    lines.append("")
    lines.append(header.format("Role / task / attempt"))
    lines.append(sep)
    for (role, task, attempt, outcome), b in s["by_run"].items():
        name = "%s / %s / %s" % (role, task, attempt if attempt is not None else "-")
        if isinstance(attempt, int) and attempt > 1:
            name += " (retry)"
        if outcome:
            name += " (%s)" % outcome
        lines.append(row(name + " (" + ", ".join(sorted(b.models)) + ")", b))
    lines.append("")
    lines.append("Input includes cached input and cache writes; output includes reasoning. Nothing is counted twice.")
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append("- Measured: %s from %d Codex session files and the ledgers given; %d duplicate records ignored."
                 % (calls(cov["calls"]), cov["session_files"], cov["duplicates_ignored"]))
    lines.append("- Runs listed: %d; with usage: %d." % (cov["runs_listed"], len(cov["runs_with_usage"])))
    for r in cov["runs_without_usage"]:
        lines.append("- **Unknown, not zero**: %s / %s run `%s`: %s." % (r["role"], r["task"], r["id"], r["reason"]))
    for r in cov["runs_not_measured"]:
        lines.append("- **Not measured**: %s / %s%s." % (r["role"], r["task"], ": " + r["note"] if r["note"] else ""))
    for name in cov["files_not_readable"]:
        lines.append("- **Unknown, not zero**: input file `%s` was not found or not readable." % name)
    for name in cov["session_files_without_usage"]:
        lines.append("- **Unknown, not zero**: session file `%s` has no usage records." % name)
    if cov["unattributed_calls"]:
        lines.append("- %s not attributed to a listed run." % calls(cov["unattributed_calls"]))
    if cov["subagent_calls"]:
        lines.append("- %s from subagent threads, attributed to the run that spawned them." % calls(cov["subagent_calls"]))
    lines.append("")
    if cov["notes"]:
        lines.append("Estimates, lower bounds and gaps:")
        lines.append("")
        for note, n in cov["notes"].most_common():
            lines.append("- %s: %s" % (calls(n), note))
        lines.append("")
    lines.append("Not included in any amount:")
    lines.append("")
    for item in EXCLUDED:
        lines.append("- " + item)
    return "\n".join(lines) + "\n"


def to_json(args, table, attribution, s):
    def bucket(b):
        return {"calls": b.calls, "tokens": b.tokens, "calls_with_unknown": b.unknown,
                "list_price_usd": str(b.usd.quantize(Decimal("0.000001"))), "label": usd_label(b),
                "status": b.worst(), "status_counts": dict(b.status)}
    cov = dict(s["coverage"])
    cov["notes"] = dict(cov["notes"])
    cov["billing"] = dict(cov["billing"])
    return {
        "goal": args.goal or (attribution or {}).get("goal"),
        "kind": "list-price calculation, not a bill",
        "prices": {"source_url": table["source_url"], "retrieved_at": table["retrieved_at"],
                   "file": os.path.basename(table["_path"]), "sha256": table["_sha256"]},
        "total": bucket(s["total"]),
        "retries": bucket(s["retries"]),
        "by_model": {m: bucket(b) for m, b in s["by_model"].items()},
        "by_run": [dict(role=k[0], task=k[1], attempt=k[2], outcome=k[3], **bucket(b)) for k, b in s["by_run"].items()],
        "coverage": cov,
        "excluded": EXCLUDED,
    }


def to_records(records):
    """Normalized metadata-only records; re-readable as a ledger (api=normalized)."""
    for rec in records:
        yield {
            "api": "normalized", "run": rec["run"], "parent_run": rec["parent_run"], "call_id": rec["key"],
            "source": rec["source"], "timestamp": rec["timestamp"], "model": rec["model"],
            "model_evidence": rec["model_evidence"], "tier": rec["tier"], "tier_evidence": rec["tier_evidence"],
            "billing": rec["billing"], "granularity": rec["granularity"],
            "input_tokens": rec["input"], "cached_input_tokens": rec["cached"],
            "cache_write_tokens": rec["cache_write"], "cache_write_30m_tokens": rec["write_30m"],
            "cache_write_12h_tokens": rec["write_12h"], "output_tokens": rec["output"],
            "reasoning_tokens": rec["reasoning"],
        }


def default_prices():
    here = os.path.dirname(os.path.abspath(__file__))
    found = sorted(glob.glob(os.path.join(here, "prices", "openai-api-*.json")))
    return found[-1] if found else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--prices", default=default_prices(), help="pinned price table (default: newest in prices/)")
    parser.add_argument("--attribution", help="JSON file mapping runs to role, task and attempt")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex"))
    parser.add_argument("--codex-session", action="append", help="a Codex session JSONL file (repeatable)")
    parser.add_argument("--ledger", action="append", help="a JSONL ledger of API usage objects (repeatable)")
    parser.add_argument("--assume-tier", choices=["standard", "batch", "flex", "fast", "ultrafast"],
                        help="tier for calls with no observed or configured tier; recorded as an assumption")
    parser.add_argument("--goal", help="goal name for the report")
    parser.add_argument("--format", choices=["markdown", "json", "records"], default="markdown")
    args = parser.parse_args(argv)
    if not args.prices:
        parser.error("no price table found; pass --prices")
    table = load_prices(args.prices)
    attribution = None
    if args.attribution:
        with open(args.attribution, "r", encoding="utf-8") as handle:
            attribution = json.load(handle)
    metas, records, duplicates, missing = collect(args, table, attribution)
    if args.format == "records":
        for rec in to_records(records):
            sys.stdout.write(json.dumps(rec, sort_keys=True) + "\n")
        return 0
    s = summarize(args, table, attribution, metas, records, duplicates, missing)
    if args.format == "json":
        json.dump(to_json(args, table, attribution, s), sys.stdout, indent=1, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(args, table, attribution, s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
