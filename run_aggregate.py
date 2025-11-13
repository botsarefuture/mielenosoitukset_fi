import os
import sys
import signal
import time
from typing import List, Optional

from mielenosoitukset_fi.app import create_app
from mielenosoitukset_fi.utils.aggregate_analytics import rollup_events

app = create_app()


def _run_once() -> None:
    """
    Run the analytics rollup once inside the Flask application context.

    Returns
    -------
    None
    """
    with app.app_context():
        try:
            # run a single iteration and return
            rollup_events(run_once=True)
        except Exception as exc:  # pragma: no cover - logging on error
            app.logger.error(f"Error running rollup_events: {exc}")
            raise


def _run_loop(interval_s: int, stop_event) -> None:
    """
    Run the analytics rollup periodically until stopped.

    Parameters
    ----------
    interval_s : int
        Number of seconds to wait between rollups.
    stop_event : threading.Event
        Event used to signal shutdown.

    Returns
    -------
    None
    """
    app.logger.info("Starting rollup service loop (interval_s=%s)", interval_s)
    while not stop_event.is_set():
        try:
            # run one iteration per loop so stop_event checks work correctly
            with app.app_context():
                rollup_events(run_once=True)
        except Exception as exc:  # pragma: no cover - logging on error
            app.logger.exception("Error during periodic rollup: %s", exc)
        # Wait with early exit support
        stop_event.wait(interval_s)
    app.logger.info("Stopping rollup service loop")


def _run_in_thread(interval_s: int):
    """
    Run the analytics rollup loop in a background daemon thread.

    Parameters
    ----------
    interval_s : int
        Number of seconds to wait between rollups.

    Returns
    -------
    threading.Thread
        The thread object that was started.
    """
    import threading

    stop_event = threading.Event()

    def _signal_handler(signum, frame):
        stop_event.set()

    # Hook signals for the spawned thread as well (best-effort)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    thread = threading.Thread(target=_run_loop, args=(interval_s, stop_event), daemon=True)
    thread.start()
    return thread, stop_event


def main(argv: Optional[List[str]] = None) -> int:
    """
    Entry point for running analytics aggregation suitable for systemd.

    Behaviour modes
    - If first arg is "once": run rollup once and exit.
    - If first arg is "thread": run loop in a daemon thread and exit immediately (keeps background thread).
    - Default (no args): run as a long-running service loop until SIGTERM/SIGINT.

    The interval between rollups is controlled by the environment variable
    ROLLUP_INTERVAL_S (default 300 seconds).

    Parameters
    ----------
    argv : list or None
        Command line arguments.

    Returns
    -------
    int
        Exit code (0 on success, non-zero on failure).
    """
    import threading

    argv = argv or sys.argv[1:]
    interval_s = int(os.getenv("ROLLUP_INTERVAL_S", "300"))

    try:
        if len(argv) > 0 and argv[0] == "once":
            _run_once()
            return 0

        if len(argv) > 0 and argv[0] == "thread":
            # start background thread and exit; thread will run as daemon
            _run_in_thread(interval_s)
            return 0

        # Default: run as a long-running service suitable for systemd (Type=simple)
        stop_event = threading.Event()

        def _handle_signal(signum, frame):
            app.logger.info("Received signal %s, shutting down", signum)
            stop_event.set()

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        # Run loop in the main thread so systemd can track the process
        _run_loop(interval_s, stop_event)
        return 0
    except Exception:
        app.logger.exception("Fatal error in run_aggregate")
        return 1


if __name__ == "__main__":
    
    raise SystemExit(main())