"""
tuia.sync - Thread-safe UI synchronization decorators.
"""

import functools
import inspect
import threading


def _get_app(instance, signature, args, kwargs):
    """
    Resolve the TUIApp associated with an object.

    Normally this is instance.app.

    During __init__, instance.app may not exist yet, so we also
    look for a `parent` argument and use parent.app.
    """
    app = getattr(instance, "app", None)

    if app is not None:
        return app

    # Try to resolve `parent` from the function arguments.
    try:
        bound = signature.bind(instance, *args, **kwargs)
        parent = bound.arguments.get("parent")
    except TypeError:
        parent = None

    if parent is not None:
        return getattr(parent, "app", None)

    return None


def sync(func):
    """
    Execute a function on the TUI thread.

    If called from the TUI thread, the function executes immediately.

    If called from another thread, the function is queued and this
    function returns immediately.

    The return value from a queued call is intentionally discarded.
    Use @sync_wait when the caller needs the result.
    """
    signature = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(instance, *args, **kwargs):
        app = _get_app(instance, signature, args, kwargs)

        # No app yet, or the TUI hasn't started.
        #
        # This is important for root widget construction:
        #
        #     root = Frame()
        #     app.set_root(root)
        #
        if app is None or not app.running:
            return func(instance, *args, **kwargs)

        # Already on the UI thread.
        if app.is_ui_thread():
            return func(instance, *args, **kwargs)

        # Worker thread -> queue the operation.
        app._ui_queue.put(
            lambda: func(instance, *args, **kwargs)
        )

        # Wake the UI thread if it is waiting for the next frame.
        app._ui_wakeup.set()

        # @sync is intentionally fire-and-forget.
        return None

    wrapper._ui_sync_wrapped = True

    return wrapper


def sync_wait(func):
    """
    Execute a function on the TUI thread.

    If called from the TUI thread, the function executes immediately.

    If called from another thread, the function is queued and this
    function blocks until execution has completed.

    Return values and exceptions are propagated back to the caller.
    """
    signature = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(instance, *args, **kwargs):
        app = _get_app(instance, signature, args, kwargs)

        # No app yet, or the TUI hasn't started.
        if app is None or not app.running:
            return func(instance, *args, **kwargs)

        # Already on the UI thread.
        if app.is_ui_thread():
            return func(instance, *args, **kwargs)

        done = threading.Event()

        result = []
        exception = []

        def call():
            try:
                result.append(
                    func(instance, *args, **kwargs)
                )
            except BaseException as exc:
                exception.append(exc)
            finally:
                done.set()

        app._ui_queue.put(call)

        # Wake the UI thread immediately.
        app._ui_wakeup.set()

        # Wait until the UI thread has executed the function.
        done.wait()

        # Re-raise the exception on the calling thread.
        if exception:
            raise exception[0]

        return result[0] if result else None

    wrapper._ui_sync_wrapped = True

    return wrapper