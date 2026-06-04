from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.core.db.session import reset_session_context, session, set_session_context


def standalone_session[**P, T](
    func: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    """Decorator for non-HTTP entry points (CLI scripts, background workers).

    Establishes a fresh session scope for the duration of `func`, rolls back on
    failure, and tears down the scoped session afterwards.
    """

    async def _standalone_session(*args: P.args, **kwargs: P.kwargs) -> T:
        session_id = str(uuid4())
        context = set_session_context(session_id=session_id)
        try:
            return await func(*args, **kwargs)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.remove()
            reset_session_context(context=context)

    return _standalone_session
