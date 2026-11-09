"""Tests for jstack_cli.py. Run: python3 -m pytest delivery-graph/tests -q

All data is synthetic. Git tests build temporary repositories.
"""

import contextlib
import io
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, SKILL)

import jstack_cli as jc  # noqa: E402


def task(tid, **kw):
    base = {
        "id": tid, "title": tid, "traces_to": ["R1"],
        "acceptance_criteria": ["AC1"], "blocked_by": [],
        "scope": ["src/%s/" % tid.lower()], "status": "ready",
        "branch": None, "base_sha": None, "tip_sha": None,
        "worktree": None, "review": None, "verifications": [],
        "repair": {"max_attempts": 3, "attempts": []}, "landed": None,
    }
    base.update(kw)
    return base


def graph(*tasks, **kw):
    g = {"version": 1, "questions": [], "tasks": list(tasks)}
    g.update(kw)
    return g


def write_plan(directory, g, name="PLAN.md"):
    path = os.path.join(directory, name)
    with open(path, "w") as handle:
        handle.write("# Plan\n\n%s\nplaceholder\n%s\n\n```jstack-graph\n%s\n```\n"
                     % (jc.VIEW_START, jc.VIEW_END, json.dumps(g, indent=2)))
    return path


def _concurrent_transition(job):
    plan, tid = job
    return jc.main(["--plan", plan, "transition", tid, "in_progress"])


def run_cli(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = jc.main(list(argv))
    return code, out.getvalue()


def git(repo, *args):
    proc = subprocess.run(
        ["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"] + list(args),
        capture_output=True, text=True)
    assert proc.returncode == 0, (args, proc.stdout, proc.stderr)
    return proc.stdout.strip()


class TempDir(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def make_repo(self):
        repo = os.path.join(self.dir, "repo")
        os.makedirs(repo)
        git(repo, "init", "-q", "-b", "main")
        with open(os.path.join(repo, "f.txt"), "w") as handle:
            handle.write("base\n")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "base")
        return repo


class Validate(unittest.TestCase):
    def test_valid_graph(self):
        self.assertEqual(jc.validate(graph(task("T1"))), [])

    def test_duplicate_ids(self):
        errs = jc.validate(graph(task("T1"), task("T1")))
        self.assertIn("duplicate task id: T1", errs)

    def test_missing_dependency(self):
        errs = jc.validate(graph(task("T1", blocked_by=["T9"])))
        self.assertTrue(any("unknown task/question T9" in e for e in errs), errs)

    def test_question_dependency_must_be_declared(self):
        g = graph(task("T1", blocked_by=["Q1"]),
                  questions=[{"id": "Q1", "answered": False}])
        self.assertEqual(jc.validate(g), [])

    def test_missing_work_area_and_traces(self):
        errs = jc.validate(graph(task("T1", scope=[], traces_to=[])))
        self.assertTrue(any("missing work area" in e for e in errs), errs)
        self.assertTrue(any("traces_to is empty" in e for e in errs), errs)

    def test_cycle(self):
        errs = jc.validate(graph(task("T1", blocked_by=["T2"]),
                                 task("T2", blocked_by=["T1"])))
        self.assertTrue(any("dependency cycle" in e for e in errs), errs)

    def test_self_cycle(self):
        errs = jc.validate(graph(task("T1", blocked_by=["T1"])))
        self.assertTrue(any("cycle" in e for e in errs), errs)

    def test_bad_verification_record(self):
        bad = task("T1", verifications=[{"command": "pytest", "result": "pass"}])
        errs = jc.validate(graph(bad))
        self.assertTrue(any("verifications[0] missing revision" in e for e in errs), errs)


class Ready(unittest.TestCase):
    def test_ready_computation(self):
        g = graph(task("T1"),
                  task("T2", blocked_by=["T1"], status="blocked"),
                  task("T3", blocked_by=["T1", "Q1"], status="blocked"),
                  questions=[{"id": "Q1", "answered": False}])
        self.assertEqual(jc.ready_tasks(g), ["T1"])
        g["tasks"][0]["status"] = "integrated"
        self.assertEqual(jc.ready_tasks(g), ["T2"])
        g["questions"][0]["answered"] = True
        self.assertEqual(jc.ready_tasks(g), ["T2", "T3"])

    def test_done_and_verified_blockers_satisfy(self):
        for status in ("integrated", "verified", "done"):
            g = graph(task("T1", status=status),
                      task("T2", blocked_by=["T1"], status="blocked"))
            self.assertEqual(jc.ready_tasks(g), ["T2"], status)

    def test_review_does_not_satisfy_blocker(self):
        g = graph(task("T1", status="review"),
                  task("T2", blocked_by=["T1"], status="blocked"))
        self.assertEqual(jc.ready_tasks(g), [])


class Transitions(unittest.TestCase):
    def errs(self, g, tid, new, repo=None):
        return jc.transition_errors(g, jc.tasks_by_id(g)[tid], new, repo)

    def test_illegal_transition(self):
        errs = self.errs(graph(task("T1", status="blocked")), "T1", "integrated")
        self.assertTrue(any("illegal transition" in e for e in errs), errs)

    def test_done_is_terminal(self):
        errs = self.errs(graph(task("T1", status="done")), "T1", "ready")
        self.assertTrue(any("illegal transition" in e for e in errs), errs)

    def test_start_requires_satisfied_blockers(self):
        g = graph(task("T1", status="review"),
                  task("T2", blocked_by=["T1"], status="ready"))
        self.assertTrue(any("blockers not satisfied" in e
                            for e in self.errs(g, "T2", "in_progress")))

    def test_scope_overlap_blocks_parallel_start(self):
        g = graph(task("T1", status="in_progress", scope=["src/api/"]),
                  task("T2", status="ready", scope=["src/api/export.py"]))
        self.assertTrue(any("overlaps" in e for e in self.errs(g, "T2", "in_progress")))

    def test_disjoint_scope_can_start(self):
        g = graph(task("T1", status="in_progress", scope=["src/a/"]),
                  task("T2", status="ready", scope=["src/b/"]))
        self.assertEqual(self.errs(g, "T2", "in_progress"), [])

    def test_review_to_integrated_happy_path_no_git(self):
        t = task("T1", status="review", tip_sha="aaa",
                 review={"sha": "aaa", "verdict": "pass"},
                 verifications=[{"command": "pytest -q", "result": "pass",
                                 "revision": "aaa", "environment": "local",
                                 "criteria": ["AC1"]}])
        self.assertEqual(self.errs(graph(t), "T1", "integrated"), [])

    def test_stale_review_sha_recorded_tip(self):
        t = task("T1", status="review", tip_sha="bbb",
                 review={"sha": "aaa", "verdict": "pass"},
                 verifications=[{"command": "pytest", "result": "pass",
                                 "revision": "aaa", "environment": "local",
                                 "criteria": ["AC1"]}])
        errs = self.errs(graph(t), "T1", "integrated")
        self.assertTrue(any("stale review" in e for e in errs), errs)

    def test_review_fail_blocks_integration(self):
        t = task("T1", status="review", tip_sha="aaa",
                 review={"sha": "aaa", "verdict": "fail"})
        self.assertTrue(any("passing review" in e
                            for e in self.errs(graph(t), "T1", "integrated")))

    def test_verification_at_old_revision_detected(self):
        t = task("T1", status="review", tip_sha="bbb",
                 review={"sha": "bbb", "verdict": "pass"},
                 verifications=[{"command": "pytest", "result": "pass",
                                 "revision": "aaa", "environment": "local",
                                 "criteria": ["AC1"]}])
        errs = self.errs(graph(t), "T1", "integrated")
        self.assertTrue(any("does not cover" in e or "old revision" in e
                            for e in errs), errs)

    def test_verification_missing_criteria_detected(self):
        t = task("T1", status="review", tip_sha="aaa",
                 acceptance_criteria=["AC1", "AC2"],
                 review={"sha": "aaa", "verdict": "pass"},
                 verifications=[{"command": "pytest", "result": "pass",
                                 "revision": "aaa", "environment": "local",
                                 "criteria": ["AC1"]}])
        errs = self.errs(graph(t), "T1", "integrated")
        self.assertTrue(any("AC2" in e for e in errs), errs)

    def test_failed_verification_does_not_cover(self):
        t = task("T1", status="review", tip_sha="aaa",
                 review={"sha": "aaa", "verdict": "pass"},
                 verifications=[{"command": "pytest", "result": "fail",
                                 "revision": "aaa", "environment": "local",
                                 "criteria": ["AC1"]}])
        self.assertTrue(self.errs(graph(t), "T1", "integrated"))

    def test_verified_requires_candidate_coverage(self):
        t = task("T1", status="integrated",
                 verifications=[{"command": "pytest", "result": "pass",
                                 "revision": "cand1", "environment": "local",
                                 "criteria": ["AC1"]}])
        self.assertEqual(self.errs(graph(t, candidate_sha="cand1"),
                                   "T1", "verified"), [])
        self.assertTrue(self.errs(graph(t, candidate_sha="cand2"),
                                  "T1", "verified"))

    def test_done_requires_landed_record(self):
        t = task("T1", status="verified")
        self.assertTrue(any("landed record" in e
                            for e in self.errs(graph(t), "T1", "done")))


class RepairBudget(unittest.TestCase):
    def attempts(self, sigs, diagnoses=None):
        return [{"n": i + 1, "failure_signature": s,
                 "diagnosis": (diagnoses[i] if diagnoses else "d%d" % i),
                 "result": "fail"} for i, s in enumerate(sigs)]

    def test_budget_exhaustion_blocks_more_repair(self):
        t = task("T1", status="in_progress",
                 repair={"max_attempts": 2, "attempts": self.attempts(["a", "b"])})
        errs = jc.transition_errors(graph(t), t, "repairing", None)
        self.assertTrue(any("budget exhausted" in e for e in errs), errs)

    def test_budget_exhaustion_blocks_retry(self):
        t = task("T1", status="repairing",
                 repair={"max_attempts": 2, "attempts": self.attempts(["a", "b"])})
        errs = jc.transition_errors(graph(t), t, "in_progress", None)
        self.assertTrue(any("budget exhausted" in e for e in errs), errs)

    def test_repeated_failure_needs_new_diagnosis(self):
        t = task("T1", status="repairing",
                 repair={"max_attempts": 5,
                         "attempts": self.attempts(["KeyError", "KeyError"],
                                                   diagnoses=["same", "same"])})
        errs = jc.transition_errors(graph(t), t, "in_progress", None)
        self.assertTrue(any("new diagnosis required" in e for e in errs), errs)

    def test_repeated_failure_with_new_diagnosis_can_retry(self):
        t = task("T1", status="repairing",
                 repair={"max_attempts": 5,
                         "attempts": self.attempts(["KeyError", "KeyError"],
                                                   diagnoses=["old", "new cause"])})
        self.assertEqual(jc.transition_errors(graph(t), t, "in_progress", None), [])

    def test_different_failure_can_retry(self):
        t = task("T1", status="repairing",
                 repair={"max_attempts": 5,
                         "attempts": self.attempts(["a", "b"])})
        self.assertEqual(jc.transition_errors(graph(t), t, "in_progress", None), [])


class GitChecks(TempDir):
    def branch_with_commit(self, repo, branch, content="work\n"):
        git(repo, "checkout", "-q", "-b", branch)
        with open(os.path.join(repo, "f.txt"), "w") as handle:
            handle.write(content)
        git(repo, "commit", "-q", "-am", "work on %s" % branch)
        head = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "main")
        return head

    def test_stale_review_against_real_branch_head(self):
        repo = self.make_repo()
        head = self.branch_with_commit(repo, "feat/t1")
        t = task("T1", status="review", branch="feat/t1", tip_sha=head,
                 review={"sha": "0" * 40, "verdict": "pass"},
                 verifications=[{"command": "pytest", "result": "pass",
                                 "revision": head, "environment": "local",
                                 "criteria": ["AC1"]}])
        errs = jc.transition_errors(graph(t), t, "integrated", repo)
        self.assertTrue(any("stale review" in e for e in errs), errs)
        t["review"]["sha"] = head
        git(repo, "merge", "-q", "--no-ff", "feat/t1", "-m", "merge t1")
        self.assertEqual(jc.transition_errors(graph(t), t, "integrated", repo), [])

    def test_zero_own_commit_branch_is_never_merged(self):
        repo = self.make_repo()
        git(repo, "branch", "feat/fresh")
        merged, reason = jc.is_merged(task("T1", branch="feat/fresh"), repo)
        self.assertFalse(merged)
        self.assertIn("zero own commits", reason)

    def test_merged_branch_by_ancestor_heuristic(self):
        repo = self.make_repo()
        self.branch_with_commit(repo, "feat/t1")
        git(repo, "merge", "-q", "--no-ff", "feat/t1", "-m", "merge t1")
        merged, _ = jc.is_merged(task("T1", branch="feat/t1"), repo)
        self.assertTrue(merged)

    def test_unmerged_branch(self):
        repo = self.make_repo()
        self.branch_with_commit(repo, "feat/t1")
        merged, _ = jc.is_merged(task("T1", branch="feat/t1"), repo)
        self.assertFalse(merged)

    def test_landed_record_is_primary_and_tip_must_not_move(self):
        repo = self.make_repo()
        head = self.branch_with_commit(repo, "feat/t1")
        git(repo, "merge", "-q", "--no-ff", "feat/t1", "-m", "merge t1")
        landing = git(repo, "rev-parse", "HEAD")
        t = task("T1", branch="feat/t1",
                 landed={"tip_sha": head, "landing_sha": landing})
        self.assertTrue(jc.is_merged(t, repo)[0])
        t["landed"]["tip_sha"] = "0" * 40
        self.assertFalse(jc.is_merged(t, repo)[0])

    def test_done_transition_uses_landed_evidence(self):
        repo = self.make_repo()
        head = self.branch_with_commit(repo, "feat/t1")
        git(repo, "merge", "-q", "--no-ff", "feat/t1", "-m", "merge t1")
        landing = git(repo, "rev-parse", "HEAD")
        t = task("T1", status="verified", branch="feat/t1",
                 landed={"tip_sha": head, "landing_sha": landing})
        self.assertEqual(jc.transition_errors(graph(t), t, "done", repo), [])
        t2 = task("T1", status="verified", branch="feat/t1", landed=None)
        self.assertTrue(jc.transition_errors(graph(t2), t2, "done", repo))


class Restart(TempDir):
    def test_duplicate_inflight_branch_flagged(self):
        g = graph(task("T1", status="in_progress", branch="feat/x"),
                  task("T2", status="review", branch="feat/x"))
        warns = jc.restart_warnings(g, None)
        self.assertTrue(any("duplicate in-flight" in w for w in warns), warns)

    def test_in_progress_without_worktree_flagged_in_real_repo(self):
        repo = self.make_repo()
        git(repo, "branch", "feat/t1")
        g = graph(task("T1", status="in_progress", branch="feat/t1"))
        warns = jc.restart_warnings(g, repo)
        self.assertTrue(any("no worktree holds" in w for w in warns), warns)

    def test_in_progress_with_worktree_is_quiet(self):
        repo = self.make_repo()
        wt = os.path.join(self.dir, "wt-t1")
        git(repo, "worktree", "add", "-q", "-b", "feat/t1", wt)
        g = graph(task("T1", status="in_progress", branch="feat/t1", worktree=wt))
        warns = jc.restart_warnings(g, repo)
        self.assertEqual([w for w in warns if w.startswith("T1")], [], warns)

    def test_ready_task_with_existing_branch_flagged_as_duplicate_start(self):
        repo = self.make_repo()
        git(repo, "branch", "feat/t1")
        g = graph(task("T1", status="ready", branch="feat/t1"))
        warns = jc.restart_warnings(g, repo)
        self.assertTrue(any("do not start a duplicate" in w for w in warns), warns)

    def test_moved_branch_tip_flagged(self):
        repo = self.make_repo()
        git(repo, "branch", "feat/t1")
        g = graph(task("T1", status="review", branch="feat/t1", tip_sha="0" * 40))
        warns = jc.restart_warnings(g, repo)
        self.assertTrue(any("moved" in w for w in warns), warns)


class CliRoundTrip(TempDir):
    def test_validate_ready_status_commands(self):
        plan = write_plan(self.dir, graph(task("T1"),
                                          task("T2", blocked_by=["T1"], status="blocked")))
        self.assertEqual(run_cli("--plan", plan, "validate")[0], 0)
        code, out = run_cli("--plan", plan, "ready")
        self.assertEqual((code, out.strip()), (0, "T1"))
        code, out = run_cli("--plan", plan, "status")
        self.assertEqual(code, 0)
        self.assertIn("Ready (frontier): T1", out)

    def test_validate_command_fails_on_cycle(self):
        plan = write_plan(self.dir, graph(task("T1", blocked_by=["T2"]),
                                          task("T2", blocked_by=["T1"])))
        code, out = run_cli("--plan", plan, "validate")
        self.assertEqual(code, 1)
        self.assertIn("cycle", out)

    def test_transition_writes_status_and_generated_view(self):
        plan = write_plan(self.dir, graph(task("T1")))
        code, _ = run_cli("--plan", plan, "transition", "T1", "in_progress")
        self.assertEqual(code, 0)
        _, g = jc.load_plan(plan)
        self.assertEqual(g["tasks"][0]["status"], "in_progress")
        with open(plan) as handle:
            text = handle.read()
        self.assertIn("| T1 T1 |", text)
        self.assertIn("in_progress", text)

    def test_illegal_transition_refuses_and_does_not_write(self):
        plan = write_plan(self.dir, graph(task("T1", status="blocked")))
        code, out = run_cli("--plan", plan, "transition", "T1", "done")
        self.assertEqual(code, 1)
        self.assertIn("illegal transition", out)
        _, g = jc.load_plan(plan)
        self.assertEqual(g["tasks"][0]["status"], "blocked")

    def test_render_round_trip_is_idempotent(self):
        g = graph(task("T1"), task("T2", blocked_by=["T1"], status="blocked"))
        plan = write_plan(self.dir, g)
        self.assertEqual(run_cli("--plan", plan, "render", "--write")[0], 0)
        with open(plan) as handle:
            first = handle.read()
        self.assertEqual(run_cli("--plan", plan, "render", "--write")[0], 0)
        with open(plan) as handle:
            self.assertEqual(handle.read(), first)
        _, loaded = jc.load_plan(plan)
        self.assertEqual(loaded, g)
        self.assertIn(jc.render_status(g), first)

    def test_check_command_reports_stale_review(self):
        repo = self.make_repo()
        git(repo, "checkout", "-q", "-b", "feat/t1")
        with open(os.path.join(repo, "f.txt"), "w") as handle:
            handle.write("work\n")
        git(repo, "commit", "-q", "-am", "work")
        head = git(repo, "rev-parse", "HEAD")
        t = task("T1", status="review", branch="feat/t1", tip_sha=head,
                 review={"sha": "0" * 40, "verdict": "pass"})
        plan = write_plan(repo, graph(t))
        code, out = run_cli("--plan", plan, "--repo", repo, "check", "T1")
        self.assertEqual(code, 1)
        self.assertIn("stale review", out)

    def test_missing_block_is_an_error(self):
        path = os.path.join(self.dir, "PLAN.md")
        with open(path, "w") as handle:
            handle.write("# no graph\n")
        code, out = run_cli("--plan", path, "validate")
        self.assertEqual(code, 1)
        self.assertIn("no ```jstack-graph block", out)


class AtomicLockedWrites(TempDir):
    def test_crash_before_replace_leaves_old_file_intact(self):
        plan = write_plan(self.dir, graph(task("T1")))
        with open(plan) as handle:
            before = handle.read()
        _, g = jc.load_plan(plan)
        g["tasks"][0]["status"] = "in_progress"
        with unittest.mock.patch.object(jc.os, "replace", side_effect=OSError("crash")):
            with self.assertRaises(OSError):
                jc.save_plan(plan, before, g)
        with open(plan) as handle:
            self.assertEqual(handle.read(), before)

    def test_two_concurrent_transitions_both_land(self):
        plan = write_plan(self.dir, graph(task("T1", scope=["src/a/"]),
                                          task("T2", scope=["src/b/"])))
        ctx = multiprocessing.get_context("fork")
        with ctx.Pool(2) as pool:
            codes = pool.map(_concurrent_transition, [(plan, "T1"), (plan, "T2")])
        self.assertEqual(codes, [0, 0])
        _, g = jc.load_plan(plan)
        self.assertEqual([t["status"] for t in g["tasks"]], ["in_progress", "in_progress"])
        self.assertTrue(os.path.exists(jc.lock_path_for(plan)))


class IntegrationProof(TempDir):
    def branch_with_commit(self, repo, branch):
        git(repo, "checkout", "-q", "-b", branch)
        with open(os.path.join(repo, "f.txt"), "w") as handle:
            handle.write("work\n")
        git(repo, "commit", "-q", "-am", "work on %s" % branch)
        head = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "main")
        return head

    def reviewed(self, head, branch="feat/t1"):
        return task("T1", status="review", branch=branch, tip_sha=head,
                    review={"sha": head, "verdict": "pass"},
                    verifications=[{"command": "pytest", "result": "pass",
                                    "revision": head, "environment": "local",
                                    "criteria": ["AC1"]}])

    def test_refused_when_reviewed_sha_not_in_integration_branch(self):
        repo = self.make_repo()
        head = self.branch_with_commit(repo, "feat/t1")
        t = self.reviewed(head)
        errs = jc.transition_errors(graph(t), t, "integrated", repo)
        self.assertTrue(any("proof" in e and "integration branch" in e for e in errs), errs)

    def test_success_after_merge_into_custom_integration_branch(self):
        repo = self.make_repo()
        head = self.branch_with_commit(repo, "feat/t1")
        git(repo, "branch", "int/goal")
        git(repo, "checkout", "-q", "int/goal")
        git(repo, "merge", "-q", "--no-ff", "feat/t1", "-m", "merge t1")
        git(repo, "checkout", "-q", "main")
        t = self.reviewed(head)
        g = graph(t, integration_branch="int/goal")
        self.assertEqual(jc.transition_errors(g, t, "integrated", repo), [])

    def test_success_via_landed_record(self):
        repo = self.make_repo()
        head = self.branch_with_commit(repo, "feat/t1")
        landing = git(repo, "rev-parse", "main")
        t = self.reviewed(head)
        t["landed"] = {"tip_sha": head, "landing_sha": landing}
        self.assertEqual(jc.transition_errors(graph(t), t, "integrated", repo), [])


class StartGuardsExtra(unittest.TestCase):
    def errs(self, g, tid, new):
        return jc.transition_errors(g, jc.tasks_by_id(g)[tid], new, None)

    def test_repairing_to_in_progress_scope_overlap(self):
        g = graph(task("T1", status="in_progress", scope=["src/api/"]),
                  task("T2", status="repairing", scope=["src/api/x.py"]))
        self.assertTrue(any("overlaps" in e for e in self.errs(g, "T2", "in_progress")))

    def test_repairing_to_in_progress_duplicate_branch(self):
        g = graph(task("T1", status="review", branch="feat/x"),
                  task("T2", status="repairing", branch="feat/x", scope=["src/z/"]))
        self.assertTrue(any("duplicate start" in e for e in self.errs(g, "T2", "in_progress")))

    def test_review_to_in_progress_scope_overlap(self):
        g = graph(task("T1", status="in_progress", scope=["src/api/"]),
                  task("T2", status="review", scope=["src/api/y.py"], tip_sha="a" * 40))
        self.assertTrue(any("overlaps" in e for e in self.errs(g, "T2", "in_progress")))

    def test_repairing_to_in_progress_disjoint_ok(self):
        g = graph(task("T1", status="in_progress", scope=["src/a/"]),
                  task("T2", status="repairing", scope=["src/b/"]))
        self.assertEqual(self.errs(g, "T2", "in_progress"), [])


class ExactIdAndDelivery(TempDir):
    def test_warn_mentions_task_exact_token(self):
        self.assertFalse(jc.warn_mentions_task("T10: in_progress but no worktree", "T1"))
        self.assertTrue(jc.warn_mentions_task("T10: in_progress but no worktree", "T10"))
        self.assertTrue(jc.warn_mentions_task("duplicate branch used by T1, T10", "T1"))

    def test_check_t1_does_not_report_t10_warning(self):
        repo = self.make_repo()
        g = graph(task("T1"), task("T10", status="in_progress", branch="feat/t10"))
        plan = write_plan(repo, g)
        code, out = run_cli("--plan", plan, "--repo", repo, "check", "T1")
        self.assertEqual(code, 0, out)
        self.assertNotIn("no worktree holds", out)
        code, out = run_cli("--plan", plan, "--repo", repo, "check", "T10")
        self.assertIn("no worktree holds", out)

    def test_ready_branch_warning_reports_commits_ahead(self):
        repo = self.make_repo()
        git(repo, "checkout", "-q", "-b", "feat/t1")
        with open(os.path.join(repo, "f.txt"), "w") as handle:
            handle.write("work\n")
        git(repo, "commit", "-q", "-am", "work")
        git(repo, "checkout", "-q", "main")
        warns = jc.restart_warnings(graph(task("T1", status="ready", branch="feat/t1")), repo)
        self.assertTrue(any("1 commits ahead" in w for w in warns), warns)

    def test_done_uses_delivery_branch(self):
        repo = self.make_repo()
        git(repo, "checkout", "-q", "-b", "feat/t1")
        with open(os.path.join(repo, "f.txt"), "w") as handle:
            handle.write("work\n")
        git(repo, "commit", "-q", "-am", "work")
        head = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "main")
        git(repo, "checkout", "-q", "-b", "release")
        git(repo, "merge", "-q", "--no-ff", "feat/t1", "-m", "merge t1")
        landing = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "main")
        t = task("T1", status="verified", branch="feat/t1",
                 landed={"tip_sha": head, "landing_sha": landing})
        self.assertEqual(jc.transition_errors(graph(t, delivery_branch="release"), t, "done", repo), [])
        self.assertTrue(jc.transition_errors(graph(t), t, "done", repo))


class RecordCommands(TempDir):
    SHA = "a" * 40

    def test_record_review_verification_attempt_and_set_tip(self):
        plan = write_plan(self.dir, graph(task("T1")))
        self.assertEqual(run_cli("--plan", plan, "record-review", "T1", "--sha", self.SHA,
                                 "--verdict", "pass", "--reviewer", "opus")[0], 0)
        self.assertEqual(run_cli("--plan", plan, "record-verification", "T1", "--command",
                                 "pytest -q", "--result", "pass", "--revision", self.SHA,
                                 "--environment", "local", "--criteria", "AC1,AC2")[0], 0)
        self.assertEqual(run_cli("--plan", plan, "record-attempt", "T1",
                                 "--failure-signature", "KeyError", "--diagnosis", "d1",
                                 "--result", "fail", "--started-at", "2026-01-01T00:00:00Z",
                                 "--ended-at", "2026-01-01T00:10:00Z")[0], 0)
        self.assertEqual(run_cli("--plan", plan, "set-tip", "T1", "--sha", self.SHA)[0], 0)
        _, g = jc.load_plan(plan)
        t = g["tasks"][0]
        self.assertEqual(t["review"], {"sha": self.SHA, "verdict": "pass", "reviewer": "opus"})
        self.assertEqual(t["verifications"][0]["criteria"], ["AC1", "AC2"])
        self.assertEqual(t["repair"]["attempts"][0]["n"], 1)
        self.assertEqual(t["repair"]["attempts"][0]["started_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(t["tip_sha"], self.SHA)

    def test_record_rejects_short_sha_and_does_not_write(self):
        plan = write_plan(self.dir, graph(task("T1")))
        code, out = run_cli("--plan", plan, "set-tip", "T1", "--sha", "abc123")
        self.assertEqual(code, 1)
        self.assertIn("40-hex", out)
        _, g = jc.load_plan(plan)
        self.assertIsNone(g["tasks"][0]["tip_sha"])
        code, out = run_cli("--plan", plan, "record-review", "T1", "--sha", "xyz",
                            "--verdict", "pass", "--reviewer", "r")
        self.assertEqual(code, 1)

    def test_record_verification_rejects_bad_revision_and_empty_criteria(self):
        plan = write_plan(self.dir, graph(task("T1")))
        code, _ = run_cli("--plan", plan, "record-verification", "T1", "--command", "pytest",
                          "--result", "pass", "--revision", "short",
                          "--environment", "local", "--criteria", "AC1")
        self.assertEqual(code, 1)
        code, _ = run_cli("--plan", plan, "record-verification", "T1", "--command", "pytest",
                          "--result", "pass", "--revision", self.SHA,
                          "--environment", "local", "--criteria", ",,")
        self.assertEqual(code, 1)

    def test_record_unknown_task(self):
        plan = write_plan(self.dir, graph(task("T1")))
        code, out = run_cli("--plan", plan, "set-tip", "T9", "--sha", self.SHA)
        self.assertEqual(code, 1)
        self.assertIn("unknown task", out)


class RepairSeconds(unittest.TestCase):
    def timed(self, seconds, max_seconds=60):
        return task("T1", status="repairing", repair={
            "max_attempts": 5, "max_seconds": max_seconds,
            "attempts": [{"n": 1, "failure_signature": "x", "diagnosis": "d",
                          "result": "fail",
                          "started_at": "2026-01-01T00:00:00Z",
                          "ended_at": "2026-01-01T00:%02d:%02dZ" % (seconds // 60, seconds % 60)}]})

    def test_max_seconds_enforced_from_timestamps(self):
        t = self.timed(120)
        errs = jc.transition_errors(graph(t), t, "in_progress", None)
        self.assertTrue(any("budget exhausted" in e and "seconds" in e for e in errs), errs)
        t2 = task("T1", status="in_progress", repair=t["repair"])
        errs = jc.transition_errors(graph(t2), t2, "repairing", None)
        self.assertTrue(any("budget exhausted" in e for e in errs), errs)

    def test_max_seconds_ignored_without_timestamps(self):
        t = task("T1", status="repairing", repair={
            "max_attempts": 5, "max_seconds": 1,
            "attempts": [{"n": 1, "failure_signature": "x", "diagnosis": "d", "result": "fail"}]})
        self.assertEqual(jc.transition_errors(graph(t), t, "in_progress", None), [])

    def test_max_seconds_within_budget_ok(self):
        t = self.timed(30)
        self.assertEqual(jc.transition_errors(graph(t), t, "in_progress", None), [])
        self.assertEqual(jc.repair_seconds(t), 30.0)


if __name__ == "__main__":
    unittest.main()


def test_save_plan_keeps_file_mode(tmp_path):
    import stat
    import jstack_cli
    plan = tmp_path / "PLAN.md"
    plan.write_text("x\n```jstack-graph\n{\"version\": 1, \"tasks\": []}\n```\n", encoding="utf-8")
    plan.chmod(0o644)
    text, graph = jstack_cli.load_plan(str(plan))
    jstack_cli.save_plan(str(plan), text, graph)
    assert stat.S_IMODE(plan.stat().st_mode) == 0o644
