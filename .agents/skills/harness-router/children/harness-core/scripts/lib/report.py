"""Step reporting for CLI and skills."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Step:
    name: str
    ok: int = 0
    warn: int = 0
    started: float = field(default_factory=time.time)

    def finish(self) -> str:
        seconds = round(time.time() - self.started, 1)
        status = "WARN" if self.warn else "OK"
        return f"[{self.name}] {status}, ok={self.ok}, warn={self.warn}, {seconds}s"


class Reporter:
    def __init__(self) -> None:
        self.rows: list[Step] = []
        self.current: Step | None = None

    def step(self, name: str) -> None:
        self.finish()
        self.current = Step(name)
        print(f"==> {name}")

    def ok(self, message: str) -> None:
        if self.current:
            self.current.ok += 1
        print(f"    OK: {message}")

    def warn(self, message: str) -> None:
        if self.current:
            self.current.warn += 1
        print(f"    WARN: {message}")

    def finish(self) -> None:
        if self.current is None:
            return
        row = self.current
        self.rows.append(row)
        print(row.finish())
        self.current = None

    def summary(self) -> None:
        self.finish()
        if not self.rows:
            return
        print("\nSummary:")
        for row in self.rows:
            print("  " + row.finish())
