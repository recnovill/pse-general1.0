"""Bounded, event-sourced research workflow. No network or arbitrary execution."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import time

from . import __version__, adapters, claims


class EngineError(ValueError):
    """Invalid contract, integrity failure or prohibited transition."""


MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_JOURNAL_BYTES = 64 * 1024 * 1024
ZERO = "0" * 64


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise EngineError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    try:
        p = Path(path)
        if p.stat().st_size > MAX_JOURNAL_BYTES:
            raise EngineError("JSON exceeds the local size limit")
        return json.loads(p.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=lambda s: (_ for _ in ()).throw(EngineError(f"Nonfinite JSON number: {s}")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EngineError(f"Cannot read JSON: {exc}") from exc


def _finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise EngineError("Nonfinite numeric value")
    if isinstance(value, dict):
        for item in value.values():
            _finite(item)
    elif isinstance(value, list):
        for item in value:
            _finite(item)


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise EngineError(f"{name}: nonempty trimmed text required")
    return value


def _integer(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        raise EngineError(f"{name}: integer >= {minimum} required")


def _fields(obj, required, optional=()):
    if not isinstance(obj, dict) or any(not isinstance(k, str) for k in obj) or set(obj) - set(required) - set(optional) or set(required) - set(obj):
        raise EngineError(f"Invalid fields; expected {sorted(required)}, optional {sorted(optional)}")


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value):
        raise EngineError("IDs must start with a letter and use only letters, digits, _ or -")
    return value


def _strings(value, name, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value):
        raise EngineError(f"{name}: list required")
    for x in value:
        _text(x, name)


def validate_plan(plan):
    _finite(plan)
    _fields(plan, {"version", "case_id", "objective", "scope", "success_criteria", "limitations", "budget", "questions", "branches", "checks"})
    if type(plan["version"]) is not int or plan["version"] != 2:
        raise EngineError("Plan version must be 2; retain version 1 cases with their original runtime and migrate a copy explicitly")
    _identifier(plan["case_id"])
    for name in ("objective", "scope", "success_criteria"):
        _text(plan[name], name)
    _strings(plan["limitations"], "limitations")
    _fields(plan["budget"], {"max_checks", "max_units", "max_rounds", "max_seconds"})
    for key, value in plan["budget"].items():
        _integer(value, key)
    seen = set()
    def register(items, name, minimum):
        if not isinstance(items, list) or len(items) < minimum:
            raise EngineError(f"{name}: at least {minimum} entries required")
        ids = set()
        for item in items:
            if not isinstance(item, dict):
                raise EngineError(f"{name}: object required")
            identity = _identifier(item.get("id"))
            if identity in seen:
                raise EngineError(f"Duplicate ID: {identity}")
            ids.add(identity)
            seen.add(identity)
        return ids
    questions = register(plan["questions"], "questions", 2)
    question_texts = set()
    for q in plan["questions"]:
        _fields(q, {"id", "text", "purpose"})
        _text(q["text"], "question text")
        _text(q["purpose"], "question purpose")
        normalized = " ".join(q["text"].casefold().split())
        if normalized in question_texts:
            raise EngineError("Questions must not have identical text")
        question_texts.add(normalized)
    branches = register(plan["branches"], "branches", 3)
    approaches, roles = set(), set()
    for b in plan["branches"]:
        _fields(b, {"id", "question_id", "role", "hypothesis", "approach", "falsifier"})
        if not isinstance(b["question_id"], str) or not isinstance(b["role"], str) or b["question_id"] not in questions or b["role"] not in {"baseline", "alternative", "critical"}:
            raise EngineError("Invalid branch question or role")
        roles.add(b["role"])
        for name in ("hypothesis", "approach", "falsifier"):
            _text(b[name], name)
        normalized = " ".join(b["approach"].casefold().split())
        if normalized in approaches:
            raise EngineError("Branches must not have identical approaches")
        approaches.add(normalized)
    if roles != {"baseline", "alternative", "critical"}:
        raise EngineError("baseline, alternative and critical roles required")
    checks = register(plan["checks"], "checks", 1)
    covered, challenge = set(), False
    for check in plan["checks"]:
        _fields(check, {"id", "branch_ids", "method", "params", "decision_link", "critical", "challenge", "cost_units"}, {"revises"})
        _strings(check["branch_ids"], "branch_ids")
        if len(check["branch_ids"]) != len(set(check["branch_ids"])) or not set(check["branch_ids"]) <= branches:
            raise EngineError("Invalid branch references")
        covered.update(check["branch_ids"])
        _text(check["decision_link"], "decision_link")
        _integer(check["cost_units"], "cost_units")
        if type(check["critical"]) is not bool or type(check["challenge"]) is not bool:
            raise EngineError("critical and challenge must be booleans")
        if check["challenge"] and not check["critical"]:
            raise EngineError("Challenge checks must be critical")
        challenge |= check["challenge"]
        if "revises" in check:
            _strings(check["revises"], "revises")
            if len(set(check["revises"])) != len(check["revises"]) or not set(check["revises"]) <= checks or check["id"] in check["revises"]:
                raise EngineError("Invalid revises references")
        try:
            adapters.validate(check)
        except (ValueError, TypeError, KeyError) as exc:
            raise EngineError(f"Invalid check {check['id']}: {exc}") from exc
    if covered != branches or not challenge:
        raise EngineError("Every branch needs a check and a critical challenge is required")
    return deepcopy(plan)


def _no_links(path):
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise EngineError("Symbolic links and junctions are not allowed")


def _safe(root, relative):
    if not isinstance(relative, str) or "\\" in relative or ":" in relative or "\x00" in relative:
        raise EngineError("Unsafe relative source path")
    p = PurePosixPath(relative)
    if not relative or p.is_absolute() or any(x in {".", ".."} for x in relative.split("/")) or "//" in relative:
        raise EngineError("Unsafe relative source path")
    target = Path(root)
    _no_links(target)
    for part in p.parts:
        if not part or part.endswith((" ", ".")):
            raise EngineError("Unsafe source path component")
        target /= part
        _no_links(target)
    if not target.resolve().is_relative_to(Path(root).resolve()):
        raise EngineError("Source path leaves its root")
    return target


def _runtime():
    here = Path(__file__).parent
    return _digest({name: hashlib.sha256((here / name).read_bytes()).hexdigest()
                    for name in ("__init__.py", "__main__.py", "engine.py", "adapters.py", "claims.py")})


def _source_data(plan, base):
    blobs = {}
    total = 0
    for check in plan["checks"]:
        for relative in adapters.source_paths(check):
            if relative in blobs:
                continue
            path = _safe(base, relative)
            if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
                raise EngineError(f"Source missing or over 10 MiB: {relative}")
            data = path.read_bytes()
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise EngineError("Sources exceed 50 MiB per round")
            blobs[relative] = data
    return blobs


def _write_json(path, value):
    data = _canonical(value) + b"\n"
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    temp.replace(path)


def _snapshot(case, number, plan, blobs):
    folder = case / "rounds" / f"r{number:03d}"
    if folder.exists():
        raise EngineError("Round snapshot already exists")
    folder.mkdir(parents=True)
    sources = folder / "sources"
    sources.mkdir()
    _write_json(folder / "plan.json", plan)
    manifest = {}
    for name, data in sorted(blobs.items()):
        target = _safe(sources, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return {"round": number, "plan_sha256": _digest(plan), "sources": manifest, "runtime_sha256": _runtime()}


def _event(events, action, payload, timestamp=None):
    item = {"seq": len(events), "timestamp": time.time() if timestamp is None else timestamp, "action": action, "payload": payload,
            "previous": events[-1]["sha256"] if events else ZERO}
    if type(item["timestamp"]) not in {int, float} or not math.isfinite(item["timestamp"]) or item["timestamp"] < (events[-1]["timestamp"] if events else 0):
        raise EngineError("Clock moved backwards or produced an invalid time; journal was not changed")
    item["sha256"] = _digest(item)
    return item


def _append(case, events, action, payload, timestamp=None):
    events.append(_event(events, action, payload, timestamp))
    _write_json(case / "journal.json", events)


@contextmanager
def _locked(case):
    case = Path(case).absolute()
    if not case.is_dir():
        raise EngineError("Case directory does not exist")
    _no_links(case)
    lock = case / ".pse.lock"
    try:
        with lock.open("x", encoding="utf-8") as stream:
            import os
            stream.write(str(os.getpid()))
    except FileExistsError as exc:
        raise EngineError("Case is locked; do not run concurrent writers") from exc
    try:
        yield case
    finally:
        lock.unlink(missing_ok=True)


def _load(case):
    """Replay contracts at each event's time, then verify local snapshots."""
    case = Path(case).absolute()
    _no_links(case)
    events = read_json(_safe(case, "journal.json"))
    if not isinstance(events, list) or not events:
        raise EngineError("Empty or invalid journal")
    state = {"case": case, "events": [], "plans": [], "snapshots": {}, "attempts": {},
             "results": {}, "tips": [], "closures": [], "proposals": [], "reviews": [],
             "pending_tip_ids": [], "check_round": {}, "state": None, "created_at": None}
    previous, last_time, runtime = ZERO, 0, _runtime()
    for index, event in enumerate(events):
        _fields(event, {"seq", "timestamp", "action", "payload", "previous", "sha256"})
        clean = {k: v for k, v in event.items() if k != "sha256"}
        if type(event["seq"]) is not int or event["seq"] != index or event["previous"] != previous or event["sha256"] != _digest(clean):
            raise EngineError("Journal chain or contents changed")
        now = event["timestamp"]
        if type(now) not in {int, float} or not math.isfinite(now) or now < last_time:
            raise EngineError("Invalid event time")
        last_time, previous = now, event["sha256"]
        action, payload = event["action"], event["payload"]
        if not isinstance(action, str) or not isinstance(payload, dict):
            raise EngineError("Event action and payload have invalid types")
        if action in {"created", "revised"}:
            if (index == 0) != (action == "created"):
                raise EngineError("Invalid initial event")
            _fields(payload, {"snapshot", "engine_version"} if action == "created" else {"snapshot", "resolved_tip_ids"})
            if action == "created" and payload["engine_version"] != __version__:
                raise EngineError("Engine version differs from case")
            meta = payload["snapshot"]
            _fields(meta, {"round", "plan_sha256", "sources", "runtime_sha256"})
            number = len(state["plans"]) + 1
            if type(meta["round"]) is not int or meta["round"] != number or meta["runtime_sha256"] != runtime:
                raise EngineError("Runtime or round seal changed")
            folder = _safe(case, f"rounds/r{number:03d}")
            plan = validate_plan(read_json(_safe(folder, "plan.json")))
            if _digest(plan) != meta["plan_sha256"]:
                raise EngineError("Sealed plan changed")
            if action == "created":
                if any("revises" in c for c in plan["checks"]):
                    raise EngineError("Initial checks cannot revise earlier checks")
                state["created_at"] = now
            else:
                _revision_contract(plan, state, now)
                if payload["resolved_tip_ids"] != state["pending_tip_ids"]:
                    raise EngineError("Revision does not account for pending tips")
            expected_paths = {p for c in plan["checks"] for p in adapters.source_paths(c)}
            if not isinstance(meta["sources"], dict) or expected_paths != set(meta["sources"]):
                raise EngineError("Source inventory differs from plan")
            total_bytes = 0
            for relative, expected in meta["sources"].items():
                _fields(expected, {"sha256", "bytes"})
                _integer(expected["bytes"], "source bytes", minimum=0)
                total_bytes += expected["bytes"]
                if expected["bytes"] > MAX_SOURCE_BYTES or total_bytes > MAX_TOTAL_BYTES:
                    raise EngineError("Snapshot sources exceed size limit")
                source = _safe(folder / "sources", relative)
                if not source.is_file() or source.stat().st_size != expected["bytes"] or hashlib.sha256(source.read_bytes()).hexdigest() != expected["sha256"]:
                    raise EngineError(f"Sealed source changed: {relative}")
            state["plans"].append(plan)
            state["plan"] = plan
            state["snapshots"][number] = meta
            for check in plan["checks"]:
                state["check_round"].setdefault(check["id"], number)
            state["pending_tip_ids"] = []
            state["state"] = "READY"
        elif not state["plans"]:
            raise EngineError("Journal lacks creation event")
        elif action == "attempt_started":
            _fields(payload, {"check_id", "cost_units", "round"})
            known = {c["id"]: c for c in state["plan"]["checks"]}
            cid = payload["check_id"]
            if not isinstance(cid, str) or cid not in known or cid in state["attempts"]:
                raise EngineError("Invalid or repeated attempt")
            check = known[cid]
            _attempt_gate(state, check, now)
            if type(payload["cost_units"]) is not int or payload["cost_units"] != check["cost_units"] or type(payload["round"]) is not int or payload["round"] != state["check_round"][cid]:
                raise EngineError("Attempt cost or round differs from plan")
            state["attempts"][cid] = payload
            state["state"] = "RUNNING"
        elif action == "check_result":
            _fields(payload, {"check_id", "result"})
            _open_gate(state)
            cid = payload["check_id"]
            if not isinstance(cid, str) or cid not in state["attempts"] or cid in state["results"]:
                raise EngineError("Result has no unique attempt")
            check = next(c for c in state["plan"]["checks"] if c["id"] == cid)
            _result_contract(payload["result"], check)
            state["results"][cid] = payload["result"]
            state["state"] = "CHECKED" if len(state["results"]) == len(state["plan"]["checks"]) else "RUNNING"
        elif action == "budget_exhausted":
            _fields(payload, {"reason"})
            _open_gate(state)
            if payload["reason"] != "Global check, unit or wall-time limit reached":
                raise EngineError("Invalid budget exhaustion reason")
            pending = [c for c in state["plan"]["checks"] if c["id"] not in state["attempts"]]
            if not pending or _affordable(state, pending[0]["cost_units"], now, check=True):
                raise EngineError("Budget exhaustion not justified")
            state["state"] = "BUDGET_EXHAUSTED"
        elif action == "proposed":
            _fields(payload, {"proposal_id", "proposal_sha256", "context_sha256", "draft"})
            if payload != _proposal_payload(state, payload["draft"], now):
                raise EngineError("Proposal digest, context or sequence differs")
            state["proposals"].append(payload)
            state["state"] = "PROPOSED_DECLARED"
        elif action == "reviewed":
            if payload != _review_payload(state, payload, now):
                raise EngineError("Review differs from validated payload")
            state["reviews"].append(payload)
            state["state"] = "REVIEW_APPROVED_DECLARED" if payload["verdict"] == "approve" else "REVIEW_REJECTED_DECLARED"
        elif action == "closed":
            mode = payload.get("mode")
            keys = {"mode"} if mode == "results_only" else {"mode", "reason", "limitations"} if mode == "unresolved" else {"mode", "proposal_id"}
            decision = {k: payload[k] for k in keys if k in payload}
            if payload != _decision(decision, state, now):
                raise EngineError("Closure does not match the validated decision and evidence")
            state["closures"].append(deepcopy(payload))
            state["state"] = payload["state"]
        elif action == "tip":
            fields = {"type", "affected_check_ids", "reason", "decision_impact"}
            _fields(payload, fields | {"tip_id", "action"})
            if payload != _tip_payload(state, {k: payload[k] for k in fields}):
                raise EngineError("Invalid tip sequence or action")
            state["tips"].append(payload)
            if payload["action"] == "REVIEW_REQUIRED":
                state["pending_tip_ids"].append(payload["tip_id"])
                state["state"] = "REVIEW_REQUIRED"
                for closure in state["closures"]:
                    closure["superseded"] = True
            elif not state["state"].startswith("CLOSED") and state["state"] in {"PROPOSED_DECLARED", "REVIEW_APPROVED_DECLARED", "REVIEW_REJECTED_DECLARED"}:
                state["state"] = "CHECKED"
        else:
            raise EngineError(f"Unknown event type: {action}")
        state["events"].append(event)
    return state


def _result_contract(result, check=None):
    _fields(result, {"status", "kind", "summary", "details"})
    if not isinstance(result["status"], str) or not isinstance(result["kind"], str) or result["status"] not in {"pass", "fail", "inconclusive"} or result["kind"] not in {"computed", "documentary", "declared"}:
        raise EngineError("Invalid adapter result status/kind")
    if check is not None and result["kind"] != _failure_kind(check):
        raise EngineError("Adapter result kind differs from its method")
    _text(result["summary"], "result summary")
    if not isinstance(result["details"], dict):
        raise EngineError("Result details must be an object")
    _finite(result)
    if "elapsed_seconds" in result["details"]:
        elapsed = result["details"]["elapsed_seconds"]
        if type(elapsed) not in {int, float} or elapsed < 0:
            raise EngineError("Result duration must be a finite nonnegative number")
    if check is not None:
        try:
            claims.generated_results({"branches": [{"id": bid} for bid in check["branch_ids"]],
                                      "checks": [check]}, {check["id"]: result})
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise EngineError(f"Invalid typed result: {exc}") from exc


def _failure_kind(check):
    return "declared" if check["method"] == "manual_review" else "documentary" if check["method"] == "text_evidence" else "computed"


def _budget(state, now=None):
    used = sum(x["cost_units"] for x in state["attempts"].values())
    proposals, reviews = len(state["proposals"]), len(state["reviews"])
    elapsed = max(0, (time.time() if now is None else now) - state["created_at"])
    return {"checks_used": len(state["attempts"]), "units_used": used + proposals + reviews,
            "proposals_used": proposals, "reviews_used": reviews, "rounds_used": len(state["plans"]),
            "elapsed_seconds": elapsed, "limits": state["plan"]["budget"]}


def _status(state):
    return {"case_id": state["plan"]["case_id"], "state": state["state"], "round": len(state["plans"]),
            "budget": _budget(state), "results": state["results"], "pending_tip_ids": state["pending_tip_ids"],
            "proposals": state["proposals"], "reviews": state["reviews"],
            "closures": state["closures"], "exploratory_revision": len(state["plans"]) > 1,
            "integrity_verified": True}


def _open_gate(state):
    if state["state"].startswith("CLOSED") or state["pending_tip_ids"]:
        raise EngineError("Closed or review-required case cannot perform this operation")


def _affordable(state, units, now, check=False):
    b, limits = _budget(state, now), state["plan"]["budget"]
    return (b["units_used"] + units <= limits["max_units"] and
            b["checks_used"] + int(check) <= limits["max_checks"] and
            b["elapsed_seconds"] < limits["max_seconds"])


def _attempt_gate(state, check, now):
    _open_gate(state)
    if set(state["attempts"]) != set(state["results"]):
        raise EngineError("An unfinished attempt must be recovered before starting another")
    if not _affordable(state, check["cost_units"], now, check=True):
        raise EngineError("Attempt exceeds the original global budget")
    pending = [c["id"] for c in state["plan"]["checks"] if c["id"] not in state["attempts"]]
    if not pending or pending[0] != check["id"]:
        raise EngineError("Checks must run in the registered order")


def _completed_gate(state):
    _open_gate(state)
    if set(state["results"]) != {c["id"] for c in state["plan"]["checks"]}:
        raise EngineError("All planned checks must execute first")


def _selected_gate(state, selected):
    _completed_gate(state)
    for c in state["plan"]["checks"]:
        if (c["critical"] or selected in c["branch_ids"]) and state["results"][c["id"]]["status"] != "pass":
            raise EngineError(f"Critical or selected-branch check did not pass: {c['id']}")


def _context_digest(state):
    return _digest({"version": 2, "case_id": state["plan"]["case_id"],
                    "plans": state["plans"], "snapshots": state["snapshots"],
                    "check_round": state["check_round"], "attempts": state["attempts"],
                    "results": state["results"], "tips": state["tips"],
                    "pending_tip_ids": state["pending_tip_ids"]})


def _proposal_payload(state, draft, now):
    try:
        draft = claims.validate_draft(draft, state["plan"], state["results"])
    except (ValueError, KeyError, TypeError) as exc:
        raise EngineError(f"Invalid draft: {exc}") from exc
    _selected_gate(state, draft["selected_branch_id"])
    if len(state["proposals"]) >= 3 or not _affordable(state, 1, now):
        raise EngineError("Proposal limit or global budget exhausted")
    context = _context_digest(state)
    digest = _digest({"version": 2, "case_id": state["plan"]["case_id"], "context_sha256": context, "draft": draft})
    if any(p["proposal_sha256"] == digest for p in state["proposals"]):
        raise EngineError("Identical proposal already recorded in this context")
    return {"proposal_id": f"proposal_{len(state['proposals']) + 1}", "proposal_sha256": digest,
            "context_sha256": context, "draft": draft}


def _find_proposal(state, proposal_id):
    proposal = next((p for p in state["proposals"] if p["proposal_id"] == proposal_id), None)
    if proposal is None:
        raise EngineError("Unknown proposal")
    return proposal


def _current_proposal(state, proposal_id):
    proposal = _find_proposal(state, proposal_id)
    if proposal["context_sha256"] != _context_digest(state):
        raise EngineError("Proposal is stale; evidence or tips changed")
    return proposal


def _review_payload(state, review, now):
    _open_gate(state)
    if not isinstance(review, dict):
        raise EngineError("Review must be an object")
    proposal = _current_proposal(state, review.get("proposal_id"))
    _selected_gate(state, proposal["draft"]["selected_branch_id"])
    if any(r["proposal_id"] == proposal["proposal_id"] for r in state["reviews"]):
        raise EngineError("A proposal permits exactly one recorded review")
    if len(state["reviews"]) >= 3 or not _affordable(state, 1, now):
        raise EngineError("Review limit or global budget exhausted")
    try:
        return claims.validate_review(review, proposal, state["plan"])
    except (ValueError, KeyError, TypeError) as exc:
        raise EngineError(f"Invalid review: {exc}") from exc


def propose_case(case, draft):
    with _locked(case) as case:
        state, now = _load(case), time.time()
        payload = _proposal_payload(state, draft, now)
        _append(case, state["events"], "proposed", payload, now)
        return deepcopy(payload)


def review_packet(case, proposal_id):
    state = _load(case)
    proposal = _find_proposal(state, proposal_id)
    return {"case_id": state["plan"]["case_id"], **deepcopy(proposal),
            "context_current": proposal["context_sha256"] == _context_digest(state),
            "generated_results": claims.generated_results(state["plan"], state["results"]),
            "declared_case_inputs": {k: deepcopy(state["plan"][k]) for k in
                                     ("objective", "scope", "success_criteria", "limitations", "branches", "checks")},
            "budget": _budget(state), "pending_tip_ids": state["pending_tip_ids"],
            "review_limitations": ["Author and reviewer are declared identities, not authenticated identities.",
                                   "This packet does not approve claims or establish independent semantic verification.",
                                   "Review each claim, its scope and cited checks; address a critical challenge and an alternative explanation."]}


def review_case(case, review):
    with _locked(case) as case:
        state, now = _load(case), time.time()
        payload = _review_payload(state, review, now)
        _append(case, state["events"], "reviewed", payload, now)
        return deepcopy(payload)


def init_case(plan_path, out):
    plan_path, target = Path(plan_path).absolute(), Path(out).absolute()
    if target.exists():
        raise EngineError("Refusing to overwrite an existing case")
    _no_links(plan_path)
    plan = validate_plan(read_json(plan_path))
    if any("revises" in c for c in plan["checks"]):
        raise EngineError("Initial checks cannot revise earlier checks")
    blobs = _source_data(plan, plan_path.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    _no_links(target.parent)
    stage = Path(tempfile.mkdtemp(prefix=".pse-create-", dir=target.parent))
    try:
        meta = _snapshot(stage, 1, plan, blobs)
        events = [_event([], "created", {"snapshot": meta, "engine_version": __version__})]
        _write_json(stage / "journal.json", events)
        stage.rename(target)
    except BaseException:
        if stage.exists() and stage.resolve().parent == target.parent.resolve() and stage.name.startswith(".pse-create-"):
            shutil.rmtree(stage)
        raise
    return status(target)


def status(case):
    return _status(_load(case))


def verify_case(case):
    state = _load(case)
    return {"verified": True, "events": len(state["events"]), "rounds": len(state["plans"]),
            "case_id": state["plan"]["case_id"], "scope": "Local byte integrity and structural contracts; not scientific validity or external custody"}


def branch_view(case, branch_id):
    state = _load(case)
    if state["attempts"]:
        raise EngineError("Initial branch views are only available before checks run")
    plan = state["plan"]
    branch = next((b for b in plan["branches"] if b["id"] == branch_id), None)
    if branch is None:
        raise EngineError("Unknown branch")
    question = next(q for q in plan["questions"] if q["id"] == branch["question_id"])
    paths = set()
    for c in plan["checks"]:
        if branch_id in c["branch_ids"]:
            paths.update(adapters.source_paths(c))
    return {"objective": plan["objective"], "scope": plan["scope"], "success_criteria": plan["success_criteria"],
            "question": question, "branch": branch, "source_paths": sorted(paths), "limitations": plan["limitations"],
            "note": "Only this branch is exposed by this view; this is not access control or statistical independence."}


def run_case(case):
    with _locked(case) as case:
        state = _load(case)
        if state["state"].startswith("CLOSED") or state["pending_tip_ids"]:
            raise EngineError("Closed or review-required case cannot execute")
        events = state["events"]
        for cid in set(state["attempts"]) - set(state["results"]):
            interrupted_check = next(c for c in state["plan"]["checks"] if c["id"] == cid)
            _append(case, events, "check_result", {"check_id": cid, "result": {"status": "inconclusive", "kind": _failure_kind(interrupted_check),
                    "summary": "Previous attempt interrupted; budget consumed and no automatic retry.", "details": {"interrupted": True}}})
        state = _load(case)
        for check in state["plan"]["checks"]:
            cid = check["id"]
            if cid in state["attempts"]:
                continue
            budget, limits = _budget(state), state["plan"]["budget"]
            if budget["checks_used"] >= limits["max_checks"] or budget["units_used"] + check["cost_units"] > limits["max_units"] or budget["elapsed_seconds"] >= limits["max_seconds"]:
                if state["state"] != "BUDGET_EXHAUSTED":
                    _append(case, state["events"], "budget_exhausted", {"reason": "Global check, unit or wall-time limit reached"})
                break
            started = time.time()
            _attempt_gate(state, check, started)
            _append(case, state["events"], "attempt_started", {"check_id": cid, "cost_units": check["cost_units"], "round": state["check_round"][cid]}, started)
            root = case / "rounds" / f"r{state['check_round'][cid]:03d}" / "sources"
            try:
                result = adapters.execute(deepcopy(check), root)
                _result_contract(result, check)
            except Exception as exc:
                result = {"status": "inconclusive", "kind": _failure_kind(check), "summary": "Check execution failed; attempt and budget preserved.",
                          "details": {"exception": type(exc).__name__, "message": str(exc)}}
            result = deepcopy(result)
            result["details"]["elapsed_seconds"] = round(max(0, time.time() - started), 6)
            _append(case, state["events"], "check_result", {"check_id": cid, "result": result})
            state = _load(case)
        return status(case)


def _decision(decision, state, now=None):
    _finite(decision)
    if not isinstance(decision, dict):
        raise EngineError("Decision must be an object")
    if state["state"].startswith("CLOSED"):
        raise EngineError("Case already closed")
    mode = decision.get("mode")
    payload = deepcopy(decision)
    if mode == "results_only":
        _fields(decision, {"mode"})
        _completed_gate(state)
        if not _affordable(state, 0, now):
            raise EngineError("Budget exhausted; use unresolved closure")
        payload.update(state="CLOSED_RESULTS", generated_results=claims.generated_results(state["plan"], state["results"]))
    elif mode == "unresolved":
        _fields(decision, {"mode", "reason", "limitations"})
        _text(decision["reason"], "declared reason")
        _strings(decision["limitations"], "declared limitations")
        payload.update(state="CLOSED_UNRESOLVED", declaration_label="DECLARED_REASON_NOT_A_SUPPORTED_CONCLUSION")
    elif mode == "reviewed":
        _fields(decision, {"mode", "proposal_id"})
        proposal = _current_proposal(state, decision["proposal_id"])
        _selected_gate(state, proposal["draft"]["selected_branch_id"])
        review = next((r for r in state["reviews"] if r["proposal_id"] == proposal["proposal_id"]), None)
        if review is None or review["verdict"] != "approve":
            raise EngineError("A current approved proposal review is required")
        if not _affordable(state, 0, now):
            raise EngineError("Budget exhausted; use unresolved closure")
        payload.update(state="CLOSED_REVIEWED_DECLARED", proposal_sha256=proposal["proposal_sha256"],
                       context_sha256=proposal["context_sha256"], draft=deepcopy(proposal["draft"]), review=deepcopy(review),
                       assurance="REVIEW_DECLARED_NOT_SEMANTICALLY_VERIFIED",
                       generated_results=claims.generated_results(state["plan"], state["results"]))
    else:
        raise EngineError("Use mode results_only, unresolved or reviewed; legacy supported/conclusion decisions are not accepted")
    kinds = {r["kind"] for r in state["results"].values()}
    payload["result_evidence_mode"] = "DECLARED_REVIEW" if "declared" in kinds else "COMPUTED_AND_DOCUMENTARY" if "documentary" in kinds else "COMPUTED" if kinds else "NO_EXECUTED_CHECKS"
    payload["evidence_mode"] = "DECLARED_REVIEW" if mode == "reviewed" else payload["result_evidence_mode"]
    payload["superseded"] = False
    payload["exploratory_revision"] = len(state["plans"]) > 1
    return payload


def close_case(case, decision):
    with _locked(case) as case:
        state, now = _load(case), time.time()
        payload = _decision(decision, state, now)
        _append(case, state["events"], "closed", payload, now)
        return status(case)


def _tip_payload(state, tip):
    _fields(tip, {"type", "affected_check_ids", "reason", "decision_impact"})
    if not isinstance(tip["type"], str) or tip["type"] not in {"material_evidence", "presentation", "new_objective"}:
        raise EngineError("Unknown tip type")
    _text(tip["reason"], "tip reason")
    _text(tip["decision_impact"], "decision_impact")
    _strings(tip["affected_check_ids"], "affected_check_ids", nonempty=tip["type"] == "material_evidence")
    known = {c["id"] for c in state["plan"]["checks"]}
    if len(tip["affected_check_ids"]) != len(set(tip["affected_check_ids"])) or not set(tip["affected_check_ids"]) <= known:
        raise EngineError("Tip references unknown or duplicate checks")
    if any(all(t.get(k) == tip[k] for k in tip) for t in state["tips"]):
        raise EngineError("Identical tip already recorded; no new work justified")
    payload = deepcopy(tip)
    payload.update(tip_id=f"tip_{len(state['tips']) + 1}", action={"material_evidence": "REVIEW_REQUIRED", "presentation": "KEEP_SCOPE", "new_objective": "OUT_OF_SCOPE"}[tip["type"]])
    return payload


def add_tip(case, tip):
    with _locked(case) as case:
        state = _load(case)
        payload = _tip_payload(state, tip)
        _append(case, state["events"], "tip", payload)
        return {"tip": payload, "status": status(case)}


def _revision_contract(new, state, now):
    if not state["pending_tip_ids"]:
        raise EngineError("Revision needs a pending material tip")
    if state["state"].startswith("CLOSED"):
        raise EngineError("A new material tip is required to reopen this closure")
    old = state["plan"]
    for key in ("version", "case_id", "objective", "scope", "success_criteria", "budget", "limitations"):
        if new[key] != old[key]:
            raise EngineError(f"Revision cannot change original {key}")
    for key in ("questions", "branches", "checks"):
        if new[key][:len(old[key])] != old[key]:
            raise EngineError(f"Revision may append {key}, never change or erase previous entries")
    extra = new["checks"][len(old["checks"]):]
    if not extra:
        raise EngineError("Revision needs new checks")
    affected = set()
    for tip in state["tips"]:
        if tip["tip_id"] in state["pending_tip_ids"]:
            affected.update(tip["affected_check_ids"])
    covered, old_checks = set(), {c["id"]: c for c in old["checks"]}
    for check in extra:
        refs = set(check.get("revises", []))
        if not refs or not refs <= affected:
            raise EngineError("Every new check must address pending affected checks")
        covered.update(refs)
        for ref in refs:
            prior = old_checks[ref]
            if not set(prior["branch_ids"]) <= set(check["branch_ids"]):
                raise EngineError("New control must retain affected branch coverage")
            if prior["critical"] and not check["critical"] or prior["challenge"] and not check["challenge"]:
                raise EngineError("New control cannot weaken critical/challenge flags")
    if covered != affected:
        raise EngineError("Every pending affected check needs a new control")
    b, limits = _budget(state, now), old["budget"]
    pending = [c for c in new["checks"] if c["id"] not in state["attempts"]]
    if len(state["plans"]) >= limits["max_rounds"] or b["elapsed_seconds"] >= limits["max_seconds"] or b["checks_used"] + len(pending) > limits["max_checks"] or b["units_used"] + sum(c["cost_units"] for c in pending) > limits["max_units"]:
        raise EngineError("Revision does not fit the original global budget")


def revise_case(case, plan_path):
    with _locked(case) as case:
        state, now = _load(case), time.time()
        new = validate_plan(read_json(plan_path))
        _revision_contract(new, state, now)
        blobs = _source_data(new, Path(plan_path).absolute().parent)
        meta = _snapshot(case, len(state["plans"]) + 1, new, blobs)
        _append(case, state["events"], "revised", {"snapshot": meta, "resolved_tip_ids": state["pending_tip_ids"]}, now)
        return status(case)


def render_report(case):
    state = _load(case)
    plan, b = state["plan"], _budget(state)
    esc = claims.escape_markdown
    # Indented JSON keeps user-controlled content inside literal text; unlike
    # fences, embedded backticks cannot close this block and forge a heading.
    def literal(value):
        return ["    " + line for line in json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False).splitlines()]
    lines = ["# PSE General 2.0 - informe local", "", "Identificador aportado: " + esc(plan["case_id"]),
             "", "Estado del motor: **" + state["state"] + "**", "", "## Necesidad y alcance declarados", "",
             "Objetivo aportado: " + esc(plan["objective"]), "", "Alcance aportado: " + esc(plan["scope"]), "",
             "Criterio aportado: " + esc(plan["success_criteria"]), "", "## Resultados tipados del motor", "",
             "Cada resultado aplica un criterio del plan a entradas suministradas. No selecciona un ganador ni verifica una interpretación.",
             "Los campos declared_inputs contienen texto y etiquetas aportados, no hechos certificados por el motor.", ""]
    for result in claims.generated_results(plan, state["results"]):
        lines.extend(literal(result)); lines.append("")
    lines.extend(["## Propuestas y revisiones declaradas", "",
                  "Identidades, pertinencia de pruebas y juicios semánticos son declaraciones. No hay autenticación ni garantía de independencia.", ""])
    for proposal in state["proposals"]:
        lines.extend(literal({**proposal, "context_current": proposal["context_sha256"] == _context_digest(state)})); lines.append("")
    for review in state["reviews"]:
        lines.extend(literal(review)); lines.append("")
    lines.extend(["## Cierres", ""])
    for closure in state["closures"]:
        lines.append("Estado registrado: **" + closure["state"] + "**; superseded=" + str(closure["superseded"]) + ".")
        if closure["mode"] == "reviewed":
            lines.append("Interpretación declarada con revisión registrada; no verificada semánticamente por el motor.")
        elif closure["mode"] == "results_only":
            lines.append("Cierre de resultados: conserva pass, fail e inconclusive, sin conclusión libre respaldada.")
        else:
            lines.append("Cierre inconcluso: el motivo y los límites son declarados; ninguna rama queda respaldada.")
        lines.append(""); lines.extend(literal(closure)); lines.append("")
    if not state["closures"]:
        lines.extend(["No hay cierre registrado.", ""])
    lines.extend(["## Sugerencias declaradas", ""])
    for tip in state["tips"]:
        lines.extend(literal(tip)); lines.append("")
    lines.extend(["## Presupuesto global", "", *literal(b), "", "## Límites declarados del plan", ""])
    for limit in plan["limitations"]:
        lines.extend(["- " + esc(limit), ""])
    lines.extend(["## Límites del software", "",
                  "- Un pass comprueba el criterio registrado, no toda una teoría ni una conclusión arbitraria.",
                  "- Una revisión falsa puede aprobar una afirmación falsa: CLOSED_REVIEWED_DECLARED registra ese juicio, no lo convierte en verdad calculada.",
                  "- Integridad local significa coherencia de contratos y bytes, no custodia externa, identidad autenticada o defensa frente a reescritura total.",
                  "- Las revisiones conservan los fallos históricos y el presupuesto. No se ha demostrado superioridad científica del procedimiento.", ""])
    return "\n".join(lines)
