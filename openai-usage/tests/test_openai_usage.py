"""Tests for openai_usage.py. Run: python3 -m unittest discover -s openai-usage/tests

All data is synthetic. No network, no API keys, no real session logs.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, SKILL)

import openai_usage as ou  # noqa: E402

PRICES = os.path.join(SKILL, "prices", "openai-api-2026-11-06.json")
EXAMPLE = os.path.join(HERE, "fixtures", "example")


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = ou.main(["--prices", PRICES] + list(argv))
    return code, out.getvalue()


class TempDir(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write_jsonl(self, name, rows):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        return path

    def write_json(self, name, obj):
        path = os.path.join(self.dir, name)
        with open(path, "w") as handle:
            json.dump(obj, handle)
        return path

    def report(self, *argv):
        code, out = run("--format", "json", *argv)
        self.assertEqual(code, 0)
        return json.loads(out)


def responses(call_id, model, usage, tier="default", run_id="r1", **extra):
    row = {"run": run_id, "call_id": call_id, "api": "responses", "model": model,
           "service_tier": tier, "timestamp": "2026-11-06T10:00:00Z", "usage": usage}
    row.update(extra)
    return row


def usage(inp, cached, out, reasoning, write=None, w30=None, w12=None):
    details = {"cached_tokens": cached}
    if write is not None:
        details["cache_write_tokens"] = write
    if w30 is not None:
        details["cache_write_tokens_details"] = {"ttl_30m_tokens": w30, "ttl_12h_tokens": w12}
    return {"input_tokens": inp, "input_tokens_details": details, "output_tokens": out,
            "output_tokens_details": {"reasoning_tokens": reasoning}, "total_tokens": inp + out}


def codex_session(thread, model, calls, plan="plus", tier="default", parent=None, extra=()):
    rows = [{"timestamp": "2026-11-06T10:00:00Z", "type": "session_meta",
             "payload": dict({"id": thread, "session_id": thread}, **({"parent_thread_id": parent} if parent else {}))},
            {"timestamp": "2026-11-06T10:00:01Z", "type": "event_msg",
             "payload": {"type": "thread_settings_applied", "thread_settings": {"model": model, "service_tier": tier}}}]
    total = {}
    for i, (rid, inp, cached, out, reasoning) in enumerate(calls):
        turn = "%s-turn-%d" % (thread, i)
        u = {"input_tokens": inp, "cached_input_tokens": cached, "cache_write_input_tokens": 0,
             "output_tokens": out, "reasoning_output_tokens": reasoning, "total_tokens": inp + out}
        for k, v in u.items():
            total[k] = total.get(k, 0) + v
        rows.append({"timestamp": "2026-11-06T10:01:%02dZ" % i, "type": "turn_context",
                     "payload": {"turn_id": turn, "model": model}})
        rows.append({"timestamp": "2026-11-06T10:01:%02dZ" % i, "type": "token_usage_record",
                     "payload": {"response_id": rid, "thread_id": thread, "turn_id": turn, "usage": u,
                                 "turn_token_usage": u, "thread_token_usage": dict(total)}})
        rows.append({"timestamp": "2026-11-06T10:01:%02dZ" % i, "type": "event_msg",
                     "payload": {"type": "token_count", "info": {"last_token_usage": u, "total_token_usage": dict(total)},
                                 "rate_limits": {"plan_type": plan}}})
    rows.extend(extra)
    return rows


class PriceTable(unittest.TestCase):
    def test_source_and_rates_are_recorded(self):
        table = ou.load_prices(PRICES)
        self.assertEqual(table["source_url"], "https://developers.openai.com/api/docs/pricing")
        self.assertEqual(table["retrieved_at"][:10], "2026-11-06")
        self.assertEqual(table["long_context_threshold_input_tokens"], 272000)
        for model, entry in table["models"].items():
            for tier, contexts in entry["tiers"].items():
                for context, rates in contexts.items():
                    for name, value in rates.items():
                        if value is not None:
                            self.assertGreater(Decimal(value), 0, (model, tier, context, name))

    def test_spot_values_match_the_pricing_page(self):
        m = ou.load_prices(PRICES)["models"]
        self.assertEqual(m["gpt-6.1-sol"]["tiers"]["standard"]["short"],
                         {"input": "2.00", "output": "10.00", "cached_input": "0.10",
                          "cache_write_30m": "2.50", "cache_write_12h": "5.00"})
        self.assertEqual(m["gpt-6.1-sol"]["tiers"]["standard"]["long"]["output"], "15.00")
        self.assertEqual(m["gpt-5.5"]["tiers"]["fast"]["short"]["input"], "12.50")
        self.assertIsNone(m["gpt-5.5"]["tiers"]["fast"]["long"]["input"])
        self.assertFalse(m["gpt-5.5"]["cache_writes_billed_separately"])
        self.assertTrue(m["gpt-6-luna"]["cache_writes_billed_separately"])
        self.assertEqual(m["gpt-5.3-codex"]["tiers"]["standard"]["all"]["cached_input"], "0.175")
        self.assertEqual(m["gpt-5.6-sol"]["price_valid_until"], "2026-11-30")


class NoDoubleCounting(TempDir):
    def test_cached_is_part_of_input_and_reasoning_part_of_output(self):
        led = self.write_jsonl("l.jsonl", [responses("a", "gpt-5.5", usage(10000, 4000, 1000, 400))])
        r = self.report("--ledger", led)
        self.assertEqual(r["total"]["tokens"]["input"], 10000)
        self.assertEqual(r["total"]["tokens"]["output"], 1000)
        # 6000 x $5 + 4000 x $0.50 + 1000 x $30 (reasoning inside output), per 1M
        self.assertEqual(Decimal(r["total"]["list_price_usd"]), Decimal("0.062"))
        self.assertEqual(r["total"]["status"], "exact")

    def test_cache_write_example_from_the_prompt_caching_guide(self):
        # Guide: input 12000, cached 4000, writes 3000 (30m) + 4000 (12h), at
        # $1 input and $0.10 cached costs $0.01515 for input.
        table = {"schema": "t", "source_url": "u", "retrieved_at": "d", "long_context_threshold_input_tokens": 272000,
                 "service_tier_map": {"default": "standard"},
                 "models": {"m": {"context_pricing": "flat", "cache_writes_billed_separately": True,
                                  "tiers": {"standard": {"all": {"input": "1", "cached_input": "0.10", "output": "0",
                                                                 "cache_write_30m": "1.25", "cache_write_12h": "2.5"}}}}}}
        rec = ou.new_record(api="responses", model="m", model_evidence="response", tier="standard",
                            tier_evidence="response", input=12000, cached=4000, cache_write=7000,
                            write_30m=3000, write_12h=4000, output=0, reasoning=0)
        p = ou.price(rec, table)
        self.assertEqual(p["usd"], Decimal("0.01515"))
        self.assertEqual(p["status"], "exact")

    def test_write_without_lifetime_split_is_a_lower_bound(self):
        led = self.write_jsonl("l.jsonl", [responses("a", "gpt-6.1-sol", usage(12000, 4000, 0, 0, write=7000))])
        r = self.report("--ledger", led)
        # 1000 x 2 + 4000 x 0.10 + 7000 x 2.50 (30m, the cheaper lifetime)
        self.assertEqual(Decimal(r["total"]["list_price_usd"]), Decimal("0.0199"))
        self.assertEqual(r["total"]["status"], "lower_bound")

    def test_chat_completions_fields_and_30m_writes(self):
        row = {"run": "c", "call_id": "chat1", "api": "chat", "model": "gpt-6.1-sol", "service_tier": "default",
               "usage": {"prompt_tokens": 12000, "completion_tokens": 500,
                         "prompt_tokens_details": {"cached_tokens": 4000, "cache_write_tokens": 7000},
                         "completion_tokens_details": {"reasoning_tokens": 300}}}
        r = self.report("--ledger", self.write_jsonl("l.jsonl", [row]))
        # 1000 x 2 + 4000 x 0.10 + 7000 x 2.50 + 500 x 10
        self.assertEqual(Decimal(r["total"]["list_price_usd"]), Decimal("0.0249"))
        self.assertEqual(r["total"]["status"], "exact")
        self.assertEqual(r["total"]["tokens"]["reasoning"], 300)

    def test_agents_turn_without_write_count(self):
        rows = [dict(responses("t1", "gpt-6.1-sol", usage(5000, 1500, 900, 200)), api="agents_turn"),
                dict(responses("t2", "gpt-5.5", usage(5000, 1500, 900, 200)), api="agents_turn")]
        r = self.report("--ledger", self.write_jsonl("l.jsonl", rows))
        self.assertEqual(r["by_model"]["gpt-6.1-sol"]["status"], "lower_bound")
        self.assertEqual(r["by_model"]["gpt-5.5"]["status"], "exact")

    def test_codex_uses_per_response_usage_not_cumulative_counters(self):
        path = self.write_jsonl("s/rollout-x-th1.jsonl", codex_session(
            "th1", "gpt-6.1-terra", [("resp1", 1000, 0, 100, 50), ("resp2", 2000, 1000, 200, 80)]))
        r = self.report("--codex-session", path)
        self.assertEqual(r["total"]["calls"], 2)
        self.assertEqual(r["total"]["tokens"]["input"], 3000)
        self.assertEqual(r["total"]["tokens"]["cached"], 1000)
        self.assertEqual(r["total"]["tokens"]["output"], 300)
        self.assertEqual(r["total"]["tokens"]["reasoning"], 130)

    def test_resume_and_repeated_inputs_do_not_double_count(self):
        first = self.write_jsonl("s/a.jsonl", codex_session("th1", "gpt-6.1-terra", [("resp1", 1000, 0, 100, 50)]))
        # The resumed log repeats resp1 and adds resp2.
        resumed = self.write_jsonl("s/b.jsonl", codex_session(
            "th1", "gpt-6.1-terra", [("resp1", 1000, 0, 100, 50), ("resp2", 500, 0, 10, 0)]))
        same_file = os.path.join(self.dir, "s", ".", "a.jsonl")
        r = self.report("--codex-session", first, "--codex-session", resumed, "--codex-session", same_file)
        self.assertEqual(r["total"]["calls"], 2)
        self.assertEqual(r["total"]["tokens"]["input"], 1500)
        self.assertEqual(r["coverage"]["duplicates_ignored"], 1)
        self.assertEqual(r["coverage"]["session_files"], 2)

    def test_token_count_fallback_takes_deltas(self):
        rows = [{"type": "session_meta", "payload": {"id": "old", "session_id": "old"}},
                {"type": "turn_context", "payload": {"turn_id": "t", "model": "gpt-5.5"}},
                {"type": "event_msg", "payload": {"type": "thread_settings_applied",
                                                  "thread_settings": {"service_tier": "default"}}}]

        def tc(last, total):
            keys = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
            return {"type": "event_msg", "payload": {"type": "token_count", "info": {
                "last_token_usage": dict(zip(keys, last)), "total_token_usage": dict(zip(keys, total))}}}
        # Resumed session: the first total carries 5000 input from before.
        rows += [tc((1000, 0, 100, 10), (6000, 0, 600, 60)),
                 tc((1000, 0, 100, 10), (6000, 0, 600, 60)),     # same request reported twice
                 tc((2000, 1000, 50, 5), (8000, 1000, 650, 65))]
        r = self.report("--codex-session", self.write_jsonl("s/old.jsonl", rows))
        self.assertEqual(r["total"]["calls"], 2)
        self.assertEqual(r["total"]["tokens"]["input"], 3000)
        self.assertEqual(r["total"]["tokens"]["cached"], 1000)
        self.assertEqual(r["total"]["tokens"]["output"], 150)

    def test_token_count_resumed_file_of_the_same_thread(self):
        def tc(last, total):
            keys = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
            return {"type": "event_msg", "payload": {"type": "token_count", "info": {
                "last_token_usage": dict(zip(keys, last)), "total_token_usage": dict(zip(keys, total))}}}
        head = [{"type": "session_meta", "payload": {"id": "old", "session_id": "old"}},
                {"type": "turn_context", "payload": {"turn_id": "t", "model": "gpt-5.5"}},
                {"type": "event_msg", "payload": {"type": "thread_settings_applied",
                                                  "thread_settings": {"service_tier": "default"}}}]
        first = self.write_jsonl("s/a.jsonl", head + [tc((1000, 0, 100, 0), (1000, 0, 100, 0)),
                                                      tc((2000, 0, 100, 0), (3000, 0, 200, 0))])
        # A second file of the same thread: new requests only, totals carried over.
        resumed = self.write_jsonl("s/b.jsonl", head + [tc((500, 0, 10, 0), (3500, 0, 210, 0)),
                                                        tc((700, 0, 20, 0), (4200, 0, 230, 0))])
        # A third file that replays the first file's events verbatim.
        replay = self.write_jsonl("s/c.jsonl", head + [tc((1000, 0, 100, 0), (1000, 0, 100, 0)),
                                                       tc((2000, 0, 100, 0), (3000, 0, 200, 0))])
        r = self.report("--codex-session", first, "--codex-session", resumed, "--codex-session", replay)
        self.assertEqual(r["total"]["calls"], 4)
        self.assertEqual(r["total"]["tokens"]["input"], 4200)
        self.assertEqual(r["total"]["tokens"]["output"], 230)
        self.assertEqual(r["coverage"]["duplicates_ignored"], 2)

    def test_cumulative_ledger_stream(self):
        def snap(seq, inp, out):
            return {"run": "s", "api": "responses", "model": "gpt-5.5", "service_tier": "default", "cumulative": True,
                    "stream": "session-1", "seq": seq, "usage": usage(inp, 0, out, 0)}
        rows = [snap(1, 1000, 100), snap(2, 1000, 100), snap(3, 2500, 300)]
        r = self.report("--ledger", self.write_jsonl("l.jsonl", rows))
        self.assertEqual(r["total"]["tokens"]["input"], 2500)
        self.assertEqual(r["total"]["tokens"]["output"], 300)
        rows = [snap(1, 1000, 100), snap(2, 400, 50)]
        r = self.report("--ledger", self.write_jsonl("l2.jsonl", rows))
        self.assertEqual(r["total"]["tokens"]["input"], 1400)
        self.assertIn("cumulative counter went down; treated as a restart, attribution uncertain",
                      r["coverage"]["notes"])


class MissingIsUnknown(TempDir):
    def test_null_usage_is_unknown_not_zero(self):
        rows = [responses("a", "gpt-5.5", None)]
        r = self.report("--ledger", self.write_jsonl("l.jsonl", rows))
        self.assertEqual(r["total"]["status"], "unknown")
        self.assertEqual(r["total"]["label"], "unknown")
        self.assertEqual(r["total"]["calls_with_unknown"]["input"], 1)
        _, md = run("--ledger", os.path.join(self.dir, "l.jsonl"))
        self.assertIn("List price |", md)
        self.assertIn("| unknown | unknown |", md)
        self.assertNotIn("$0.0000 | exact", md)

    def test_missing_input_files_are_gaps_not_errors(self):
        attr = self.write_json("a.json", {"runs": [{"id": "r1", "source": "ledger", "role": "reviewer", "task": "T1"}]})
        missing = os.path.join(self.dir, "not-written-yet.jsonl")
        r = self.report("--attribution", attr, "--ledger", missing,
                        "--codex-session", os.path.join(self.dir, "gone.jsonl"), "--codex-home", self.dir)
        self.assertEqual(r["total"]["label"], "unknown")
        self.assertEqual(r["coverage"]["files_not_readable"], ["gone.jsonl", "not-written-yet.jsonl"])
        self.assertEqual(r["coverage"]["runs_without_usage"][0]["id"], "r1")
        code, md = run("--ledger", missing, "--codex-home", self.dir)
        self.assertEqual(code, 0)
        self.assertIn("**Total at API list price: unknown** over 0 calls.", md)
        self.assertIn("input file `not-written-yet.jsonl` was not found or not readable", md)
        self.assertNotIn(self.dir, md)

    def test_missing_cached_split_is_priced_at_the_cheapest_rate(self):
        u = {"input_tokens": 10000, "output_tokens": 100, "output_tokens_details": {"reasoning_tokens": 0}}
        r = self.report("--ledger", self.write_jsonl("l.jsonl", [responses("a", "gpt-5.5", u)]))
        # 10000 x $0.50 (cached rate) + 100 x $30
        self.assertEqual(Decimal(r["total"]["list_price_usd"]), Decimal("0.008"))
        self.assertEqual(r["total"]["status"], "lower_bound")
        self.assertTrue(r["total"]["label"].startswith("at least"))

    def test_missing_output_is_a_lower_bound(self):
        u = {"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 0}}
        r = self.report("--ledger", self.write_jsonl("l.jsonl", [responses("a", "gpt-5.5", u)]))
        self.assertEqual(r["total"]["status"], "lower_bound")
        self.assertEqual(r["total"]["calls_with_unknown"]["output"], 1)

    def test_unknown_model_is_unpriced(self):
        rows = [responses("a", "gpt-9-preview", usage(1000, 0, 100, 0)),
                responses("b", "gpt-5.5", usage(1000, 0, 100, 0))]
        r = self.report("--ledger", self.write_jsonl("l.jsonl", rows))
        self.assertEqual(r["by_model"]["gpt-9-preview"]["label"], "unknown")
        # The known call is still priced; the total says "at least".
        self.assertEqual(Decimal(r["total"]["list_price_usd"]), Decimal("0.008"))
        self.assertTrue(r["total"]["label"].startswith("at least"))
        self.assertIn("model gpt-9-preview not in price table", r["coverage"]["notes"])

    def test_snapshot_name_is_an_estimate(self):
        rows = [responses("a", "gpt-5.5-2026-04-23", usage(1000, 0, 100, 0))]
        r = self.report("--ledger", self.write_jsonl("l.jsonl", rows))
        self.assertEqual(r["total"]["status"], "estimate")

    def test_unknown_tier_is_unpriced_unless_assumed(self):
        rows = [responses("a", "gpt-5.5", usage(1000, 0, 100, 0), tier="auto")]
        led = self.write_jsonl("l.jsonl", rows)
        self.assertEqual(self.report("--ledger", led)["total"]["status"], "unknown")
        r = self.report("--ledger", led, "--assume-tier", "standard")
        self.assertEqual(r["total"]["status"], "estimate")
        self.assertIn("service tier standard is assumed, not confirmed by a response", r["coverage"]["notes"])

    def test_priority_response_is_priced_as_fast(self):
        rows = [responses("a", "gpt-5.5", usage(1000, 0, 100, 0), tier="priority")]
        r = self.report("--ledger", self.write_jsonl("l.jsonl", rows))
        # Fast: $12.50 input, $75 output
        self.assertEqual(Decimal(r["total"]["list_price_usd"]), Decimal("0.02"))

    def test_long_context_rates_and_gaps(self):
        rows = [responses("a", "gpt-6.1-sol", usage(300000, 0, 1000, 0)),
                responses("b", "gpt-5.5", usage(300000, 0, 1000, 0), tier="priority")]
        r = self.report("--ledger", self.write_jsonl("l.jsonl", rows))
        # gpt-6.1-sol long: 300000 x $4 + 1000 x $15
        self.assertEqual(Decimal(r["by_model"]["gpt-6.1-sol"]["list_price_usd"]), Decimal("1.215"))
        # The page lists no long-context Fast price for gpt-5.5.
        self.assertEqual(r["by_model"]["gpt-5.5"]["status"], "unknown")

    def test_aggregate_over_threshold_is_a_lower_bound(self):
        row = dict(responses("a", "gpt-6.1-sol", usage(300000, 0, 1000, 0)), granularity="aggregate")
        r = self.report("--ledger", self.write_jsonl("l.jsonl", [row]))
        self.assertEqual(r["total"]["status"], "lower_bound")
        self.assertEqual(Decimal(r["total"]["list_price_usd"]), Decimal("0.61"))

    def test_inconsistent_usage_is_unknown(self):
        rows = [responses("a", "gpt-5.5", usage(1000, 2000, 100, 0))]
        r = self.report("--ledger", self.write_jsonl("l.jsonl", rows))
        self.assertEqual(r["total"]["status"], "unknown")

    def test_promotional_price_after_its_end_date(self):
        rows = [responses("a", "gpt-5.6-sol", usage(1000, 0, 100, 0, write=0, w30=0, w12=0),
                          timestamp="2026-12-01T00:00:00Z")]
        r = self.report("--ledger", self.write_jsonl("l.jsonl", rows))
        self.assertEqual(r["total"]["status"], "estimate")

    def test_requested_model_is_not_proof(self):
        row = responses("a", None, usage(1000, 0, 100, 0))
        del row["model"]
        row["requested_model"] = "gpt-5.5"
        r = self.report("--ledger", self.write_jsonl("l.jsonl", [row]))
        self.assertEqual(r["total"]["status"], "estimate")
        self.assertIn("model is the requested model, not confirmed by a response", r["coverage"]["notes"])


class AttributionAndBilling(TempDir):
    def test_roles_retries_subagents_and_unattributed(self):
        home = os.path.join(self.dir, "codex")
        self.write_jsonl("codex/sessions/rollout-1-parent.jsonl",
                         codex_session("parent", "gpt-6.1-terra", [("p1", 1000, 0, 10, 0)]))
        self.write_jsonl("codex/sessions/rollout-2-child.jsonl",
                         codex_session("child", "gpt-6-luna", [("c1", 500, 0, 10, 0)], parent="parent"))
        self.write_jsonl("codex/sessions/rollout-3-grandchild.jsonl",
                         codex_session("grandchild", "gpt-6-luna", [("g1", 200, 0, 10, 0)], parent="child"))
        stray = self.write_jsonl("other/rollout-4-stray.jsonl",
                                 codex_session("stray", "gpt-6-luna", [("s1", 100, 0, 10, 0)]))
        attr = self.write_json("a.json", {"goal": "g", "runs": [
            {"id": "parent", "source": "codex", "role": "builder", "task": "T1", "attempt": 2},
            {"id": "gone", "source": "codex", "role": "reviewer", "task": "T1", "attempt": 1},
            {"id": "plan", "source": "none", "role": "orchestrator", "task": "plan", "note": "not logged"}]})
        r = self.report("--attribution", attr, "--codex-home", home, "--codex-session", stray)
        rows = {(x["role"], x["task"], x["attempt"]): x for x in r["by_run"]}
        self.assertEqual(rows[("builder", "T1", 2)]["calls"], 3)  # parent, child, grandchild
        self.assertEqual(rows[("unattributed", "-", None)]["calls"], 1)
        self.assertEqual(r["retries"]["calls"], 3)
        self.assertEqual(r["coverage"]["subagent_calls"], 2)
        self.assertEqual(r["coverage"]["runs_without_usage"][0]["id"], "gone")
        self.assertEqual(r["coverage"]["runs_without_usage"][0]["reason"], "session file not found")
        self.assertEqual(r["coverage"]["runs_not_measured"][0]["task"], "plan")
        _, md = run("--attribution", attr, "--codex-home", home)
        self.assertIn("builder / T1 / 2 (retry)", md)
        self.assertIn("**Unknown, not zero**: reviewer / T1 run `gone`: session file not found.", md)

    def test_billing_labels(self):
        sub = self.write_jsonl("s/sub.jsonl", codex_session("t1", "gpt-6.1-terra", [("x1", 1000, 0, 10, 0)]))
        nolabel = self.write_jsonl("s/none.jsonl", codex_session("t2", "gpt-6.1-terra", [("x2", 1000, 0, 10, 0)], plan=None))
        led = self.write_jsonl("l.jsonl", [responses("y1", "gpt-5.5", usage(1000, 0, 10, 0), billing="api")])
        r = self.report("--codex-session", sub, "--codex-session", nolabel, "--ledger", led)
        self.assertEqual(r["kind"], "list-price calculation, not a bill")
        self.assertEqual(r["coverage"]["billing"], {
            "subscription (Codex rate_limits.plan_type=plus)": 1,
            "unknown (not observed)": 1,
            "api (declared in ledger)": 1})
        _, md = run("--codex-session", sub)
        self.assertIn("hypothetical", md)
        self.assertIn("List-price calculation, not a bill.", md)
        self.assertNotIn("billed per token; this figure", md)


class Privacy(TempDir):
    def test_no_content_reaches_any_output(self):
        secret = "SECRET-PROMPT-TEXT"
        rows = codex_session("t1", "gpt-6.1-terra", [("x1", 1000, 0, 10, 0)], extra=[
            {"type": "response_item", "payload": {"type": "message", "content": [{"text": secret}]}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"text": secret}}}])
        rows[0]["payload"]["base_instructions"] = {"text": secret}
        rows[0]["payload"]["cwd"] = "/home/" + secret
        path = self.write_jsonl("s/t1.jsonl", rows)
        for fmt in ("markdown", "json", "records"):
            _, out = run("--codex-session", path, "--format", fmt)
            self.assertNotIn(secret, out, fmt)

    def test_example_fixtures_hold_secrets_that_never_leak(self):
        args = ["--attribution", os.path.join(EXAMPLE, "attribution.json"),
                "--codex-home", os.path.join(EXAMPLE, "codex"), "--ledger", os.path.join(EXAMPLE, "ledger.jsonl")]
        for fmt in ("markdown", "json", "records"):
            _, out = run(*(args + ["--format", fmt]))
            self.assertNotIn("SECRET", out)
            self.assertNotIn("sk-test", out)


class Example(unittest.TestCase):
    ARGS = ["--attribution", os.path.join(EXAMPLE, "attribution.json"),
            "--codex-home", os.path.join(EXAMPLE, "codex"), "--ledger", os.path.join(EXAMPLE, "ledger.jsonl")]

    def test_example_totals(self):
        _, out = run(*(self.ARGS + ["--format", "json"]))
        r = json.loads(out)
        self.assertEqual(r["total"]["calls"], 12)
        self.assertEqual(r["coverage"]["duplicates_ignored"], 2)
        self.assertEqual(Decimal(r["total"]["list_price_usd"]), Decimal("1.363466"))
        self.assertEqual(Decimal(r["retries"]["list_price_usd"]), Decimal("0.154130"))
        self.assertEqual(Decimal(r["by_model"]["gpt-6.1-terra"]["list_price_usd"]), Decimal("0.479880"))
        self.assertEqual(r["total"]["status_counts"], {"exact": 2, "lower_bound": 8, "unknown": 2})

    def test_published_example_report_is_current(self):
        _, out = run(*self.ARGS)
        with open(os.path.join(SKILL, "reference", "example-report.md")) as handle:
            self.assertEqual(handle.read(), out)

    def test_deterministic_and_records_round_trip(self):
        _, a = run(*self.ARGS)
        _, b = run(*self.ARGS)
        self.assertEqual(a, b)
        _, records = run(*(self.ARGS + ["--format", "records"]))
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "records.jsonl")
            with open(path, "w") as handle:
                handle.write(records)
            attr = os.path.join(EXAMPLE, "attribution.json")
            _, again = run("--ledger", path, "--attribution", attr, "--codex-home", tmp, "--format", "json")
            _, first = run(*(self.ARGS + ["--format", "json"]))
            again, first = json.loads(again), json.loads(first)
            self.assertEqual(again["total"]["list_price_usd"], first["total"]["list_price_usd"])
            self.assertEqual(again["by_model"], first["by_model"])
            # Subagent calls stay with the run that spawned them without the session files.
            self.assertEqual(again["by_run"], first["by_run"])
            self.assertEqual(again["coverage"]["subagent_calls"], 1)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
