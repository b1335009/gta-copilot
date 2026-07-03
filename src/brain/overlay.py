"""Transparent always-on-top chat overlay for GTA Copilot.

Two layers:
- ``ChatBuffer``: pure logic — color-tagged line ring-buffer, unit-testable
  without a display.
- ``OverlayWindow``: tkinter panel — translucent, no focus stealing, fed by
  a thread-safe ``queue.Queue`` polled with ``after()``.

Architecture decision (PROJECT_STATE.md Phase 4):
  The overlay is NOT an in-game DirectX overlay — it is a separate always-on-top
  tkinter window (stdlib, zero new deps).  GTA must run in Borderless mode so
  this window sits visibly on top.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Line tag (determines colour in the overlay)
# ---------------------------------------------------------------------------

class LineTag(str, Enum):
    """Semantic tag for every chat line — maps to a colour."""
    PLAYER = "player"
    COPILOT = "copilot"
    REACTION = "reaction"
    STATUS = "status"


# Hex colours for each tag (dark-mode palette)
TAG_COLOURS: dict[LineTag, str] = {
    LineTag.PLAYER: "#5bc0eb",     # bright cyan — player transcript
    LineTag.COPILOT: "#9eef73",    # green — copilot reply
    LineTag.REACTION: "#fde74c",   # yellow — wanted-level reaction
    LineTag.STATUS: "#888888",     # grey — connect / disconnect / info
}


# ---------------------------------------------------------------------------
# ChatBuffer — pure logic, no Tk
# ---------------------------------------------------------------------------

@dataclass
class ChatLine:
    tag: LineTag
    text: str


class ChatBuffer:
    """Fixed-capacity ring buffer of colour-tagged chat lines.

    Thread-safe: ``append()`` can be called from any thread; ``lines()``
    returns a snapshot.
    """

    def __init__(self, capacity: int = 8):
        if capacity < 1:
            raise ValueError("capacity must be ≥ 1")
        self._capacity = capacity
        self._lines: list[ChatLine] = []
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def append(self, tag: LineTag, text: str) -> None:
        """Add a line, evicting the oldest if at capacity."""
        with self._lock:
            self._lines.append(ChatLine(tag=tag, text=text))
            if len(self._lines) > self._capacity:
                self._lines = self._lines[-self._capacity:]

    def lines(self) -> list[ChatLine]:
        """Return a snapshot (copy) of the current lines."""
        with self._lock:
            return list(self._lines)

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._lines)


# ---------------------------------------------------------------------------
# OverlayWindow — tkinter always-on-top translucent panel
# ---------------------------------------------------------------------------

# Queue message from worker threads → Tk mainloop
@dataclass
class OverlayMessage:
    tag: LineTag
    text: str


class OverlayWindow:
    """Translucent always-on-top chat overlay driven by a thread-safe queue.

    Must be created and ``run()``'d on the **main thread** (Tk requirement).
    Worker threads push ``OverlayMessage`` instances into ``message_queue``;
    the window polls the queue with ``after()`` and updates the display.

    Parameters
    ----------
    message_queue : queue.Queue[OverlayMessage]
        Thread-safe queue that worker threads write to.
    capacity : int
        Max visible lines before old ones scroll off.
    poll_ms : int
        How often (ms) the Tk event loop checks the queue.
    alpha : float
        Window transparency (0.0 = invisible, 1.0 = opaque).
    width, height : int
        Initial window size in pixels.
    x, y : int
        Initial position (top-left corner).
    """

    def __init__(
        self,
        message_queue: queue.Queue,
        *,
        capacity: int = 8,
        poll_ms: int = 100,
        alpha: float = 0.85,
        width: int = 480,
        height: int = 260,
        x: int = 20,
        y: int = 40,
    ):
        self._queue = message_queue
        self._buffer = ChatBuffer(capacity=capacity)
        self._poll_ms = poll_ms

        # Lazy import so the module can be imported without Tk (tests)
        import tkinter as tk
        import tkinter.font as tkfont

        self._tk = tk
        self._root = tk.Tk()
        self._root.title("GTA Copilot")
        self._root.geometry(f"{width}x{height}+{x}+{y}")
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", alpha)
        self._root.configure(bg="#1a1a2e")
        self._root.overrideredirect(True)  # no window chrome

        # Allow dragging the borderless window
        self._drag_data = {"x": 0, "y": 0}
        self._root.bind("<ButtonPress-1>", self._on_drag_start)
        self._root.bind("<B1-Motion>", self._on_drag_motion)

        # Chat text widget (read-only)
        try:
            self._font = tkfont.Font(family="Consolas", size=11)
        except Exception:
            self._font = tkfont.Font(family="TkFixedFont", size=11)

        self._text = tk.Text(
            self._root,
            bg="#1a1a2e",
            fg="#cccccc",
            font=self._font,
            wrap=tk.WORD,
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=8,
            state=tk.DISABLED,
            cursor="arrow",
        )
        self._text.pack(fill=tk.BOTH, expand=True)

        # Configure colour tags
        for tag, colour in TAG_COLOURS.items():
            self._text.tag_configure(tag.value, foreground=colour)

        # Start polling
        self._root.after(self._poll_ms, self._poll_queue)

    # -- dragging support --------------------------------------------------

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        x = self._root.winfo_x() + dx
        y = self._root.winfo_y() + dy
        self._root.geometry(f"+{x}+{y}")

    # -- queue polling & redraw --------------------------------------------

    def _poll_queue(self) -> None:
        """Drain all pending messages and refresh the display."""
        changed = False
        try:
            while True:
                msg: OverlayMessage = self._queue.get_nowait()
                self._buffer.append(msg.tag, msg.text)
                changed = True
        except queue.Empty:
            pass

        if changed:
            self._redraw()

        self._root.after(self._poll_ms, self._poll_queue)

    def _redraw(self) -> None:
        """Rewrite the text widget from the buffer snapshot."""
        tk = self._tk
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        for line in self._buffer.lines():
            prefix = _tag_prefix(line.tag)
            self._text.insert(tk.END, f"{prefix}{line.text}\n", line.tag.value)
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)

    # -- public API --------------------------------------------------------

    def run(self) -> None:
        """Enter the Tk mainloop (blocking, must be main thread)."""
        self._root.mainloop()

    def shutdown(self) -> None:
        """Destroy the window from any thread."""
        try:
            self._root.after(0, self._root.destroy)
        except Exception:
            pass


def _tag_prefix(tag: LineTag) -> str:
    """Short coloured prefix for each line type."""
    return {
        LineTag.PLAYER: "YOU: ",
        LineTag.COPILOT: "COPILOT: ",
        LineTag.REACTION: "⚠ ",
        LineTag.STATUS: "• ",
    }.get(tag, "")
