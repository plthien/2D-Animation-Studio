"""C3 external authoring: source-bound reservations and immutable JSON revisions."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from app.animation import service as s

KINDS = {"topic-ideas": "topic_ideas.v1", "script": "script.v1",
         "script-analysis": "script_analysis.v1", "shot-plan": "shot_plan.v1"}
BASE = Path(__file__).resolve().parents[2] / "contracts/animation/schemas"
SCHEMAS = {key: json.loads((BASE / (kind + ".schema.json")).read_text(encoding="utf-8"))
           for key, kind in KINDS.items()}
VALIDATORS = {key: Draft202012Validator(doc, format_checker=FormatChecker())
              for key, doc in SCHEMAS.items()}


def project(con, pid: str) -> dict:
    p = s.project_row(con, pid)
    if p["status"] != "active":
        s.error("OWNERSHIP_CONFLICT", "Archived project")
    return p


def latest(con, pid: str, kind: str):
    return con.execute(
        """SELECT * FROM artifacts WHERE project_id=? AND kind=?
           AND approval_status='approved' ORDER BY revision DESC LIMIT 1""",
        (pid, KINDS[kind])).fetchone()


def verified_doc(row) -> dict:
    path = s.bounded_path(row["relative_path"])
    if not path.is_file() or s.filehash(path) != (row["sha256"], row["byte_size"]):
        s.error("LINEAGE_MISMATCH", "Stored artifact is missing or corrupted", 422)
    return json.loads(path.read_text(encoding="utf-8"))


def source(con, pid: str, kind: str):
    pr = project(con, pid)
    ch = s.active_channel(con, pr["channel_id"])
    if not ch["current_dna_artifact_id"]:
        s.error("UNAPPROVED_DEPENDENCY", "Approve ChannelDNA first", 422)
    dna = con.execute("SELECT * FROM artifacts WHERE artifact_id=?",
                      (ch["current_dna_artifact_id"],)).fetchone()
    previous = None
    if kind == "script":
        previous = latest(con, pid, "topic-ideas")
    elif kind in ("script-analysis", "shot-plan"):
        previous = latest(con, pid, "script")
    if kind != "topic-ideas" and previous is None:
        s.error("UNAPPROVED_DEPENDENCY", "Required approved authoring source missing", 422)
    # Visual style edits do not invalidate the approved authoring script.
    inputs = {"kind": kind, "project_id": pid,
              "source_id": previous["artifact_id"] if previous else dna["artifact_id"],
              "source_sha256": previous["sha256"] if previous else dna["sha256"]}
    if kind == "shot-plan":
        analysis = latest(con, pid, "script-analysis")
        if analysis and json.loads(analysis["metadata_json"]).get("source_artifact_id") == previous["artifact_id"]:
            inputs["analysis_id"] = analysis["artifact_id"]
            inputs["analysis_sha256"] = analysis["sha256"]
    return pr, ch, previous, s.sha(inputs), inputs


def _validate_semantics(kind: str, doc: dict, prior, ch: dict) -> list[dict]:
    issues: list[dict] = []
    def invalid(path: str, why: str):
        issues.append({"path": path, "message": why})
    if kind == "topic-ideas":
        if doc.get("channel_dna_artifact_id") != ch["current_dna_artifact_id"]:
            invalid("channel_dna_artifact_id", "Not the approved ChannelDNA")
        with s.reader() as con:
            dna = con.execute("SELECT sha256 FROM artifacts WHERE artifact_id=?",
                              (ch["current_dna_artifact_id"],)).fetchone()
        if dna is None or doc.get("channel_dna_hash") != dna["sha256"]:
            invalid("channel_dna_hash", "DNA content SHA differs")
        ids = [x["idea_id"] for x in doc.get("ideas", []) if isinstance(x, dict) and "idea_id" in x]
        if len(set(ids)) != len(ids):
            invalid("ideas", "Duplicate idea_id")
    if kind == "script" and prior:
        ideas = verified_doc(prior).get("ideas", [])
        if doc.get("topic_ideas_artifact_id") != prior["artifact_id"]:
            invalid("topic_ideas_artifact_id", "Must reference approved Topic Ideas")
        if doc.get("selected_idea_id") not in {i["idea_id"] for i in ideas}:
            invalid("selected_idea_id", "Selected idea does not exist")
        text = doc.get("full_text", "")
        end = 0
        ids = set()
        for i, sec in enumerate(doc.get("sections", [])):
            start, stop = sec.get("start_char"), sec.get("end_char")
            if sec.get("section_id") in ids:
                invalid(f"sections/{i}", "Duplicate section ID")
            ids.add(sec.get("section_id"))
            if not isinstance(start, int) or not isinstance(stop, int) or start != end or stop <= start or text[start:stop] != sec.get("text"):
                invalid(f"sections/{i}", "Sections must cover full_text in order with exact half-open offsets")
            if isinstance(stop, int):
                end = stop
        if end != len(text):
            invalid("sections", "Sections must cover the entire script")
    if kind in ("script-analysis", "shot-plan") and prior:
        if doc.get("script_artifact_id") != prior["artifact_id"]:
            invalid("script_artifact_id", "Script source is not current approved revision")
        if kind == "script-analysis":
            ids = [x["entity_id"] for x in doc.get("entities", [])]
            if len(set(ids)) != len(ids):
                invalid("entities", "Duplicate entity identity")
    if kind == "shot-plan" and prior:
        if doc.get("script_sha256") != prior["sha256"]:
            invalid("script_sha256", "Script bytes hash mismatch")
        text = verified_doc(prior)["full_text"]
        actor = set(doc.get("actor_ids", []))
        props = set(doc.get("prop_ids", []))
        locs = set(doc.get("location_ids", []))
        shots = doc.get("shots", [])
        ids = [sh["shot_id"] for sh in shots]
        if len(set(ids)) != len(ids):
            invalid("shots", "Shot IDs must be unique")
        previous = None
        for i, shot in enumerate(shots):
            prefix = f"shots/{i}"
            if not set(shot.get("actor_ids", [])).issubset(actor) or not set(shot.get("prop_ids", [])).issubset(props):
                invalid(prefix, "Shot uses undeclared actor/prop")
            if shot.get("location_id") not in locs:
                invalid(prefix + "/location_id", "Undeclared location")
            anchors = [a.get("anchor_id") for a in shot.get("spatial_anchors", [])]
            if len(set(anchors)) != len(anchors):
                invalid(prefix + "/spatial_anchors", "Duplicate spatial anchor")
            for end_name in ("initial_world_state", "final_world_state"):
                world = shot[end_name]
                for member, allowed, field in (("actors", set(shot["actor_ids"]), "actor_id"),
                                               ("props", set(shot["prop_ids"]), "prop_id")):
                    keys = [x[field] for x in world[member]]
                    if len(set(keys)) != len(keys) or set(keys) != allowed:
                        invalid(prefix + "/" + end_name, "World state membership must match shot participants")
                for p in world["props"]:
                    held = p["held_by"]
                    if held is not None:
                        bits = held.split(":")
                        if len(bits) != 2 or bits[0] not in shot["actor_ids"] or bits[1] not in ("left", "right"):
                            invalid(prefix + "/" + end_name, "held_by must name a shot actor and left/right hand")
            utterance = shot.get("utterance")
            if utterance is not None:
                start, stop = utterance["script_start"], utterance["script_end"]
                if stop <= start or text[start:stop] != utterance["text"]:
                    invalid(prefix + "/utterance", "Utterance must exactly quote approved script")
            if previous:
                for member, field in (("actors", "actor_id"), ("props", "prop_id")):
                    old = {e[field]: e for e in previous["final_world_state"][member]}
                    for e in shot["initial_world_state"][member]:
                        if e[field] in old and e != old[e[field]]:
                            invalid(prefix + "/initial_world_state", "Unexplained world-state jump")
            previous = shot
    return issues


def validate(pid: str, kind: str, reservation_id: str, document: dict) -> dict:
    if kind not in KINDS:
        s.error("VALIDATION_FAILED", "Unknown artifact kind", 422)
    if not isinstance(document, dict):
        s.error("VALIDATION_FAILED", "Expected a JSON object", 422)
    with s.reader() as con:
        pr, ch, previous, fingerprint, _ = source(con, pid, kind)
        res = con.execute("SELECT * FROM authoring_reservations WHERE reservation_id=? AND project_id=? AND kind=?",
                          (reservation_id, pid, KINDS[kind])).fetchone()
        if res is None:
            s.error("NOT_FOUND", "Reservation not found", 404)
        if res["status"] != "open" or res["expires_at"] < s.now():
            s.error("STALE_HEAD", "Reservation has expired or been consumed")
        if res["source_fingerprint"] != fingerprint:
            s.error("STALE_HEAD", "Authoring source changed", current_fingerprint=fingerprint)
        assigned = {"artifact_id": res["reserved_artifact_id"], "channel_id": pr["channel_id"],
                    "project_id": pid, "schema_version": KINDS[kind]}
        issues = [{"path": key, "message": "Does not match reserved identity"} for key, val in assigned.items()
                  if document.get(key) != val]
        issues += [{"path": "/".join(map(str, e.absolute_path)), "message": e.message}
                   for e in sorted(VALIDATORS[kind].iter_errors(document),
                                   key=lambda e: list(map(str, e.absolute_path)))[:25]]
        if not issues:
            issues.extend(_validate_semantics(kind, document, previous, ch))
        if document.get("revision") != res_revision(con, pid, kind):
            issues.append({"path": "revision", "message": "Expected next immutable revision"})
        return {"valid": not issues, "issues": issues, "source_fingerprint": fingerprint}


def res_revision(con, pid: str, kind: str) -> int:
    return con.execute("SELECT COALESCE(MAX(revision),0)+1 FROM artifacts WHERE project_id=? AND kind=?",
                       (pid, KINDS[kind])).fetchone()[0]


def prompt(pid: str, kind: str) -> dict:
    if kind not in KINDS:
        s.error("VALIDATION_FAILED", "Unknown authoring kind", 422)
    with s.writer() as con:
        pr, ch, prior, fingerprint, inputs = source(con, pid, kind)
        reserved = s.uid("ar")
        res_id = s.uid("rs")
        revision = res_revision(con, pid, kind)
        expiry = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="microseconds")
        t = s.now()
        con.execute("""INSERT INTO authoring_reservations
            (reservation_id,project_id,channel_id,kind,schema_version,source_head_artifact_id,
             source_fingerprint,reserved_artifact_id,status,expires_at,consumed_artifact_id,
             created_at,updated_at) VALUES (?,?,?,?,?,?,?,?, 'open',?,NULL,?,?)""",
            (res_id, pid, pr["channel_id"], KINDS[kind], KINDS[kind],
             prior["artifact_id"] if prior else None, fingerprint, reserved, expiry, t, t))
        dna = con.execute("SELECT * FROM artifacts WHERE artifact_id=?", (ch["current_dna_artifact_id"],)).fetchone()
        # Large source JSON loaded outside the write transaction by caller after commit.
        source_ref = s.artifact_view(prior) if prior else None
        dna_ref = s.artifact_view(dna)
    prior_json = verified_doc(prior) if prior else None
    dna_json = verified_doc(dna)
    analysis_ref = None
    analysis_doc = None
    if kind == "shot-plan" and inputs.get("analysis_id"):
        with s.reader() as con:
            analysis = con.execute(
                """SELECT * FROM artifacts WHERE artifact_id=? AND project_id=?
                   AND kind='script_analysis.v1' AND approval_status='approved'""",
                (inputs["analysis_id"], pid),
            ).fetchone()
            if analysis and analysis["sha256"] == inputs["analysis_sha256"]:
                analysis_ref = s.artifact_view(analysis)
                analysis_doc = verified_doc(analysis)
    reserved_fields = {"schema_version": KINDS[kind], "artifact_id": reserved,
                       "project_id": pid, "channel_id": pr["channel_id"],
                       "revision": revision, "created_at": t}
    package = {
        "reservation_id": res_id,
        "source_fingerprint": fingerprint,
        "reserved_fields": reserved_fields,
        "source_inputs": inputs,
        "source_metadata": source_ref,
        "dna_metadata": dna_ref,
        "source": prior_json,
        "channel_dna": dna_json,
        "analysis_metadata": analysis_ref,
        "analysis": analysis_doc,
        "schema": SCHEMAS[kind],
    }
    guidance = {
        "topic-ideas": "Include channel_dna_artifact_id and channel_dna_hash exactly as supplied in dna_metadata.artifact_id and dna_metadata.sha256.",
        "script": "Choose a selected_idea_id present in approved source. Set topic_ideas_artifact_id to source_metadata.artifact_id; preserve IDs.",
        "script-analysis": "Reference source_metadata.artifact_id as script_artifact_id. Identify actors, props, locations and continuity without inventing source identity.",
        "shot-plan": ("Set script_artifact_id and script_sha256 from source_metadata.artifact_id/sha256. "
                      "Every utterance must match exact half-open character spans in source.full_text; silent shots use null utterance. "
                      "Use 1..30 shots, 24..720 frames each, no more than 2 actors and 3 props per shot. "
                      "Declare actor/prop/location IDs, consistent participant world states and spatial anchors. "
                      "Preserve world-state continuity and source/analysis identity; do not invent source SHA values."),
    }
    instructions = (
        "Return ONLY valid JSON conforming to schema, with reserved_fields copied exactly. "
        "Do not recalculate any ID, SHA, timestamp, reservation identity, source reference or revision. "
        "These are authoritative backend data, not suggestions. External authoring only; no hidden LLM calls. "
        + guidance[kind]
    )
    prompt_text = (instructions + "\n\n=== BEGIN AUTHORING PACKAGE JSON ===\n"
                   + json.dumps(package, sort_keys=True, ensure_ascii=False, indent=2)
                   + "\n=== END AUTHORING PACKAGE JSON ===")
    return {
        "reservation_id": res_id, "reserved_artifact_id": reserved,
        "revision": revision, "expires_at": expiry, "source_fingerprint": fingerprint,
        "instructions": instructions, "prompt_text": prompt_text,
        "reserved_fields": reserved_fields, "source_metadata": source_ref,
        "dna_metadata": dna_ref, "source_inputs": inputs,
        "source": prior_json, "channel_dna": dna_json,
        "analysis_metadata": analysis_ref, "analysis": analysis_doc,
        "schema": SCHEMAS[kind],
    }


def import_revision(pid: str, kind: str, reservation_id: str, document: dict) -> dict:
    report = validate(pid, kind, reservation_id, document)
    if not report["valid"]:
        s.error("VALIDATION_FAILED", "External authoring JSON rejected", 422, issues=report["issues"])
    aid = document["artifact_id"]
    rel = f"projects/{pid}/authoring/{kind}/{aid}.json"
    def tx(con, digest, size):
        pr, _, prev, fresh, _ = source(con, pid, kind)
        res = con.execute("SELECT * FROM authoring_reservations WHERE reservation_id=? AND project_id=?",
                          (reservation_id, pid)).fetchone()
        if not res or res["status"] != "open" or res["source_fingerprint"] != fresh or fresh != report["source_fingerprint"]:
            s.error("STALE_HEAD", "Source/reservation changed during import")
        if res_revision(con, pid, kind) != document["revision"]:
            s.error("STALE_HEAD", "Artifact revision changed")
        s.add_artifact(con, aid=aid, channel_id=pr["channel_id"], project_id=pid,
                       kind=KINDS[kind], schema=KINDS[kind], logical=KINDS[kind],
                       revision=document["revision"], status="draft", checksum=digest,
                       size=size, relative=rel,
                       metadata={"reservation_id": reservation_id, "source_fingerprint": fresh,
                                 "source_artifact_id": prev["artifact_id"] if prev else None})
        con.execute("""UPDATE artifacts SET parents_json=?,source_fingerprints_json=?
                       WHERE artifact_id=?""",
                    (s.canon([prev["artifact_id"]] if prev else []).decode(),
                     s.canon({"source": fresh}).decode(), aid))
        con.execute("""UPDATE authoring_reservations
                       SET status='consumed',consumed_artifact_id=?,updated_at=?
                       WHERE reservation_id=? AND status='open'""", (aid, s.now(), reservation_id))
        return s.artifact_view(con.execute("SELECT * FROM artifacts WHERE artifact_id=?", (aid,)).fetchone())
    return s.document_publish(document, rel, tx)


def approve(pid: str, kind: str, aid: str, expected_revision: int, expected_sha256: str) -> dict:
    if kind not in KINDS:
        s.error("VALIDATION_FAILED", "Unknown authoring kind", 422)
    with s.writer() as con:
        pr, _, _, fresh, _ = source(con, pid, kind)
        row = con.execute("SELECT * FROM artifacts WHERE artifact_id=? AND project_id=? AND kind=?",
                          (aid, pid, KINDS[kind])).fetchone()
        if not row:
            s.error("NOT_FOUND", "Authoring revision not found", 404)
        if row["sha256"] != expected_sha256:
            s.error("LINEAGE_MISMATCH", "Revision SHA differs", 422)
        verified_doc(row)
        if json.loads(row["metadata_json"]).get("source_fingerprint") != fresh:
            s.error("STALE_HEAD", "Approval source changed")
        head = con.execute("SELECT * FROM project_stage_heads WHERE project_id=? AND stage_key='authoring'",
                           (pid,)).fetchone()
        if head["revision"] != expected_revision:
            s.error("STALE_HEAD", "Authoring head changed", current_head_revision=head["revision"])
        if row["approval_status"] != "draft":
            s.error("VALIDATION_FAILED", "Only draft revisions can be approved", 422)
        if row["revision"] < (latest(con, pid, kind) or {"revision": 0})["revision"]:
            s.error("STALE_HEAD", "Cannot move approved source backwards")
        con.execute("UPDATE artifacts SET approval_status='approved',reviewed_by='local-user',reviewed_at=? WHERE artifact_id=?",
                    (s.now(), aid))
        fp = s.sha({"kind": kind, "source_fingerprint": fresh})
        changed = con.execute("""UPDATE project_stage_heads
            SET artifact_id=?,approval_status='approved',dependency_fingerprint=?,revision=revision+1,updated_at=?
            WHERE project_id=? AND stage_key='authoring' AND revision=?""",
            (aid, fp, s.now(), pid, expected_revision))
        if changed.rowcount != 1:
            s.error("STALE_HEAD", "Authoring approval CAS lost")
        return {"artifact_id": aid, "revision": expected_revision + 1, "sha256": row["sha256"],
                "kind": KINDS[kind], "dependency_fingerprint": fp}


def history(pid: str, kind: str, limit: int = 50, cursor: int | None = None) -> dict:
    if kind not in KINDS:
        s.error("VALIDATION_FAILED", "Unknown authoring kind", 422)
    with s.reader() as con:
        project(con, pid)
        rows = con.execute("""SELECT * FROM artifacts WHERE project_id=? AND kind=? AND revision<?
                              ORDER BY revision DESC LIMIT ?""",
                           (pid, KINDS[kind], cursor or 2147483647, limit + 1)).fetchall()
        return {"items": [s.artifact_view(r) for r in rows[:limit]],
                "next_cursor": rows[limit-1]["revision"] if len(rows) > limit else None}


def document(pid: str, aid: str) -> dict:
    with s.reader() as con:
        project(con, pid)
        row = con.execute("SELECT * FROM artifacts WHERE artifact_id=? AND project_id=?",
                          (aid, pid)).fetchone()
        if row is None or row["kind"] not in KINDS.values():
            s.error("NOT_FOUND", "Authoring artifact not found", 404)
        return {"artifact": s.artifact_view(row), "document": verified_doc(row)}
