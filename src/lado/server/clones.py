"""The New session window's clone from a URL (docs/design/ui.md, Launch and session
control): the remote's branches, the target folder, and clone jobs. A job is a thread of
this server running lado.clone.clone, held in memory only; the window asks for it every
half second, and a job no one asked about for clone.ABANDONED seconds is cancelled, as its
window went away. The decisions stay in the core (lado.clone); this module only keeps the
jobs."""

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from lado import clone, runtime
from lado.server import launch, models

SWEEP = 1.0  # seconds between two looks for abandoned and old jobs
CLOSE_WAIT = 3.0  # seconds the server's shutdown waits for its jobs' clones to end


class Busy(runtime.LadoError):
    """A clone into a folder another running job clones into."""


def refused(error: runtime.LadoError) -> models.CloneRefused:
    hint = getattr(error, "hint", None)
    return models.CloneRefused(
        message=str(error),
        kind=getattr(error, "kind", "refused"),
        hint=models.HintInfo(text=hint.text, command=hint.command) if hint else None,
    )


def _url(given: str) -> str:
    if not clone.is_url(given):
        raise clone.CloneError("not_url", f"{given} is not a git URL")
    return given


def remote_info(url: str) -> models.RemoteInfo:
    remote = clone.list_branches(_url(url))
    return models.RemoteInfo(
        url=runtime.public_remote(url), branches=remote.branches, default=remote.default
    )


def _folder(url: str, path: str | None) -> str:
    return runtime.full_path(path) if path else str(clone.default_folder(url))


def target_info(url: str, path: str | None, has_db: bool) -> models.CloneTarget:
    folder = _folder(_url(url), path)
    target = clone.check_target(url, folder)
    name = runtime.slug(Path(folder).name)
    return models.CloneTarget(
        path=folder,
        state=target.state,
        text=target.text,
        origin=target.origin,
        branch=target.branch,
        suggestion=target.suggestion,
        default_name=name,
        name_state=launch.name_state(name, os.path.realpath(folder), has_db),
        provider=launch.provider_suggestion(None),  # a new folder has no last session
    )


@dataclass
class Job:
    id: str
    url: str
    path: str
    branch: str | None
    started: float  # time.monotonic()
    seen: float  # when a request last asked about it
    state: Literal["running", "done", "failed", "cancelled"] = "running"
    progress: clone.Progress | None = None
    error: runtime.LadoError | None = None
    ended: float | None = None
    cancelled: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None

    def info(self) -> models.CloneJob:
        progress = self.progress
        return models.CloneJob(
            id=self.id,
            url=runtime.public_remote(self.url),
            path=self.path,
            branch=self.branch,
            state=self.state,
            progress=models.CloneProgress(
                phase=progress.phase, percent=progress.percent, detail=progress.detail
            )
            if progress
            else None,
            error=refused(self.error) if self.error else None,
            seconds=round((self.ended or time.monotonic()) - self.started, 1),
        )


class Jobs:
    """The server's clone jobs, by id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._sweeper: threading.Thread | None = None

    def start(self, url: str, path: str | None, branch: str | None) -> Job:
        """A job cloning `branch` of `url` into `path`; refused (CloneError) when the folder
        may not take a clone, Busy when another running job clones into it."""
        folder = _folder(_url(url), path)
        target = clone.check_target(url, folder)
        if target.state not in clone.CAN_CLONE:
            raise clone.CloneError(target.state, target.text)
        real = os.path.realpath(folder)
        now = time.monotonic()
        with self._lock:
            if any(
                job.state == "running" and os.path.realpath(job.path) == real
                for job in self._jobs.values()
            ):
                raise Busy(f"a clone into {folder} runs already")
            job = Job(uuid.uuid4().hex, url, folder, branch, now, now)
            job.thread = threading.Thread(target=self._run, args=(job,), daemon=True)
            self._jobs[job.id] = job
            job.thread.start()
            if self._sweeper is None:
                self._sweeper = threading.Thread(target=self._sweep_while_any, daemon=True)
                self._sweeper.start()
        return job

    def _run(self, job: Job) -> None:
        def on_progress(progress: clone.Progress) -> None:
            job.progress = progress

        try:
            clone.clone(job.url, job.path, job.branch, on_progress, job.cancelled)
            outcome, error = "done", None
        except clone.CloneError as exc:
            cancelled = exc.kind == "cancelled"
            outcome, error = ("cancelled", None) if cancelled else ("failed", exc)
        except Exception as exc:  # told to the window, never lost in a thread
            outcome = "failed"
            error = clone.CloneError(
                clone.GIT_FAILED, f"cannot clone {runtime.public_remote(job.url)}: {exc}"
            )
        with self._lock:
            job.state, job.error, job.ended = outcome, error, time.monotonic()

    def get(self, id: str, seen: bool = True) -> Job | None:
        """The job; a request that asks about it keeps it alive (`seen`)."""
        with self._lock:
            job = self._jobs.get(id)
            if job and seen:
                job.seen = time.monotonic()
            return job

    def cancel(self, id: str) -> Job | None:
        """Cancel the job and wait for its clone to end; None for an unknown one."""
        job = self.get(id)
        if job is not None:
            job.cancelled.set()
            if job.thread is not None:
                job.thread.join(clone.STOP_WAIT + 1)
        return job

    def sweep(self) -> None:
        """Cancel the running jobs no one asked about for clone.ABANDONED seconds, drop the
        finished ones older than clone.KEPT seconds."""
        now = time.monotonic()
        with self._lock:
            for job in list(self._jobs.values()):
                if job.state == "running" and now - job.seen > clone.ABANDONED:
                    job.cancelled.set()
                elif job.ended is not None and now - job.ended > clone.KEPT:
                    del self._jobs[job.id]

    def _sweep_while_any(self) -> None:
        while True:
            time.sleep(SWEEP)
            self.sweep()
            with self._lock:
                if not self._jobs:
                    self._sweeper = None
                    return

    def close(self) -> None:
        """Cancel every running job and wait, CLOSE_WAIT seconds at most, for their clones
        to end: the server stops."""
        with self._lock:
            running = [job for job in self._jobs.values() if job.state == "running"]
        for job in running:
            job.cancelled.set()
        deadline = time.monotonic() + CLOSE_WAIT
        for job in running:
            if job.thread is not None:
                job.thread.join(max(0.0, deadline - time.monotonic()))
