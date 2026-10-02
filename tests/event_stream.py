"""A client of the UI server's event stream (GET /api/events) for tests: reads it in a thread
and hands over its events one by one, each with a deadline."""

import json
import queue
import threading
import time
from dataclasses import dataclass

import httpx


@dataclass
class Event:
    event: str  # change | reset | comment (a keep-alive line)
    id: int | None  # None for an event without an `id:` line
    data: dict | None


class EventStream:
    """The events of one connection, in order. `closed` once the server ended it."""

    def __init__(self, url: str, token: str, after: int | None = None, last_id: int | None = None):
        headers = {"Authorization": f"Bearer {token}"}
        if last_id is not None:
            headers["Last-Event-ID"] = str(last_id)
        params = {} if after is None else {"after": str(after)}
        self._client = httpx.Client(timeout=httpx.Timeout(10, read=None))
        self._response = self._client.send(
            self._client.build_request("GET", url, headers=headers, params=params), stream=True
        )
        self.status = self._response.status_code
        self.closed = threading.Event()
        self._events: queue.Queue[Event] = queue.Queue()
        self.detail = ""  # the server's reason, when it refused the stream
        if self.status == 200:
            threading.Thread(target=self._read, daemon=True).start()
        else:
            self.detail = self._response.read().decode()

    def _read(self) -> None:
        fields: dict[str, str] = {}
        try:
            for line in self._response.iter_lines():
                if line.startswith(":"):
                    self._events.put(Event("comment", None, None))
                elif line:
                    name, _, value = line.partition(":")
                    fields[name] = value.removeprefix(" ")
                elif fields:
                    data = fields.get("data")
                    self._events.put(
                        Event(
                            fields.get("event", "message"),
                            int(fields["id"]) if "id" in fields else None,
                            json.loads(data) if data else None,
                        )
                    )
                    fields = {}
        except httpx.HTTPError:
            pass
        finally:
            self.closed.set()

    def next(self, timeout: float = 10, comments: bool = False) -> Event:
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            try:
                event = self._events.get(timeout=max(left, 0.01))
            except queue.Empty:
                raise AssertionError(f"no event in {timeout} s") from None
            if comments or event.event != "comment":
                return event

    def until(self, wanted, timeout: float = 10) -> list[Event]:
        """The events up to and with the first one `wanted(event)` is true for."""
        deadline = time.monotonic() + timeout
        seen: list[Event] = []
        while True:
            left = deadline - time.monotonic()
            try:
                event = self.next(timeout=max(left, 0.01))
            except AssertionError:
                raise AssertionError(f"no wanted event in {timeout} s; got {seen}") from None
            seen.append(event)
            if wanted(event):
                return seen

    def quiet(self, timeout: float) -> list[Event]:
        """The events that come within `timeout` seconds."""
        seen = []
        deadline = time.monotonic() + timeout
        while (left := deadline - time.monotonic()) > 0:
            try:
                seen.append(self.next(timeout=left))
            except AssertionError:
                break
        return seen

    def close(self) -> None:
        self._response.close()
        self._client.close()
