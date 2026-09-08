"""SQLite persistence for design revisions, history and analysis results.

Local-first and single-user, but with the two properties the brief insists on:
state survives a backend restart, and concurrent edits cannot silently clobber
one another.

Revisions are append-only. An edit writes a *new* row rather than mutating the
current one, and restoring an old revision records a further new revision on
top -- so history is never rewritten, only extended.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import AnalysisResult, DesignState, HistoryEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS designs (
    design_id        TEXT PRIMARY KEY,
    current_revision INTEGER NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
    design_id  TEXT NOT NULL,
    revision   INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (design_id, revision)
);
CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    design_id       TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    seq             INTEGER NOT NULL,
    payload_json    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analyses (
    job_id          TEXT PRIMARY KEY,
    design_id       TEXT NOT NULL,
    design_revision INTEGER NOT NULL,
    created_at      TEXT NOT NULL,
    status          TEXT NOT NULL,
    result_json     TEXT
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id   TEXT PRIMARY KEY,
    design_id     TEXT NOT NULL,
    base_revision INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    status        TEXT NOT NULL,
    payload_json  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_design ON events (design_id, seq);
CREATE INDEX IF NOT EXISTS idx_analyses_design ON analyses (design_id, design_revision);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RevisionConflict(Exception):
    """Raised when an edit is based on a revision that is no longer current."""

    def __init__(self, expected: int, actual: int):
        super().__init__(
            f"edit is based on revision {expected} but the design is at {actual}"
        )
        self.expected = expected
        self.actual = actual


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- designs and revisions ------------------------------------------------

    def has_design(self, design_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM designs WHERE design_id = ?", (design_id,)
        ).fetchone()
        return row is not None

    def create_design(self, state: DesignState) -> DesignState:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO designs VALUES (?, ?, ?)",
                (state.design_id, state.revision, _now()),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO revisions VALUES (?, ?, ?, ?)",
                (state.design_id, state.revision, state.model_dump_json(), _now()),
            )
        return state

    def current_revision(self, design_id: str) -> int:
        row = self._conn.execute(
            "SELECT current_revision FROM designs WHERE design_id = ?", (design_id,)
        ).fetchone()
        if row is None:
            raise KeyError(design_id)
        return int(row["current_revision"])

    def get_design(self, design_id: str, revision: int | None = None) -> DesignState:
        if revision is None:
            revision = self.current_revision(design_id)
        row = self._conn.execute(
            "SELECT state_json FROM revisions WHERE design_id = ? AND revision = ?",
            (design_id, revision),
        ).fetchone()
        if row is None:
            raise KeyError(f"{design_id}@{revision}")
        return DesignState.model_validate_json(row["state_json"])

    def list_revisions(self, design_id: str) -> list[int]:
        rows = self._conn.execute(
            "SELECT revision FROM revisions WHERE design_id = ? ORDER BY revision",
            (design_id,),
        ).fetchall()
        return [int(r["revision"]) for r in rows]

    def commit_revision(
        self,
        state: DesignState,
        *,
        base_revision: int,
        actor: str,
        source: str,
        summary: str = "",
        user_request: str = "",
        explanation: str = "",
        changes: list[dict[str, Any]] | None = None,
        component_refs: list[str] | None = None,
    ) -> tuple[DesignState, HistoryEvent]:
        """Append a new revision, guarded against a stale base.

        The revision check is what prevents a lost update: two edits derived
        from the same base cannot both land, so the second caller is told to
        re-read rather than silently overwriting the first.
        """
        current = self.current_revision(state.design_id)
        if base_revision != current:
            raise RevisionConflict(base_revision, current)

        new_revision = current + 1
        state = state.model_copy(update={"revision": new_revision})

        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS s FROM events WHERE design_id = ?",
            (state.design_id,),
        ).fetchone()
        seq = int(row["s"]) + 1

        event = HistoryEvent(
            event_id=uuid.uuid4().hex,
            design_id=state.design_id,
            timestamp=_now(),
            actor=actor,
            source=source,
            base_revision=base_revision,
            result_revision=new_revision,
            summary=summary,
            user_request=user_request,
            explanation=explanation,
            changes=changes or [],
            component_refs=component_refs or [],
        )

        with self._conn:
            self._conn.execute(
                "INSERT INTO revisions VALUES (?, ?, ?, ?)",
                (state.design_id, new_revision, state.model_dump_json(), _now()),
            )
            self._conn.execute(
                "UPDATE designs SET current_revision = ?, updated_at = ? "
                "WHERE design_id = ?",
                (new_revision, _now(), state.design_id),
            )
            self._conn.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.design_id,
                    event.timestamp,
                    seq,
                    event.model_dump_json(),
                ),
            )
        return state, event

    # -- history --------------------------------------------------------------

    def history(self, design_id: str) -> list[HistoryEvent]:
        rows = self._conn.execute(
            "SELECT payload_json FROM events WHERE design_id = ? ORDER BY seq",
            (design_id,),
        ).fetchall()
        return [HistoryEvent.model_validate_json(r["payload_json"]) for r in rows]

    def attach_analysis(self, event_id: str, job_id: str) -> None:
        row = self._conn.execute(
            "SELECT payload_json FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            return
        event = HistoryEvent.model_validate_json(row["payload_json"])
        event.analysis_job_id = job_id
        with self._conn:
            self._conn.execute(
                "UPDATE events SET payload_json = ? WHERE event_id = ?",
                (event.model_dump_json(), event_id),
            )

    # -- analysis jobs --------------------------------------------------------

    def start_job(self, design_id: str, revision: int) -> str:
        job_id = uuid.uuid4().hex
        with self._conn:
            self._conn.execute(
                "INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, design_id, revision, _now(), "running", None),
            )
        return job_id

    def finish_job(self, job_id: str, result: AnalysisResult) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE analyses SET status = ?, result_json = ? WHERE job_id = ?",
                ("done", result.model_dump_json(), job_id),
            )

    def fail_job(self, job_id: str, message: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE analyses SET status = ?, result_json = ? WHERE job_id = ?",
                ("error", json.dumps({"error": message}), job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM analyses WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None

    def latest_analysis(self, design_id: str) -> AnalysisResult | None:
        """Most recent completed analysis, whichever revision it ran against.

        Returning the revision alongside is what lets the UI mark a result
        stale rather than pretending it describes the current design.
        """
        row = self._conn.execute(
            "SELECT result_json FROM analyses WHERE design_id = ? AND status = 'done' "
            "ORDER BY design_revision DESC, created_at DESC LIMIT 1",
            (design_id,),
        ).fetchone()
        if row is None or not row["result_json"]:
            return None
        return AnalysisResult.model_validate_json(row["result_json"])

    def analysis_for_revision(
        self, design_id: str, revision: int
    ) -> AnalysisResult | None:
        row = self._conn.execute(
            "SELECT result_json FROM analyses WHERE design_id = ? AND design_revision = ? "
            "AND status = 'done' ORDER BY created_at DESC LIMIT 1",
            (design_id, revision),
        ).fetchone()
        if row is None or not row["result_json"]:
            return None
        return AnalysisResult.model_validate_json(row["result_json"])

    # -- chat proposals -------------------------------------------------------

    def save_proposal(self, proposal: dict[str, Any]) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO proposals VALUES (?, ?, ?, ?, ?, ?)",
                (
                    proposal["proposal_id"],
                    proposal["design_id"],
                    proposal["base_revision"],
                    _now(),
                    proposal.get("status", "pending"),
                    json.dumps(proposal),
                ),
            )

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload_json, status FROM proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        payload["status"] = row["status"]
        return payload

    def set_proposal_status(self, proposal_id: str, status: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE proposals SET status = ? WHERE proposal_id = ?",
                (status, proposal_id),
            )
