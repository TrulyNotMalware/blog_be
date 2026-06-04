from collections.abc import Awaitable, Callable
from functools import wraps

from app.core.db.session import session


class Transactional:
    """Decorator: run the wrapped coroutine inside a session transaction.

    If a transaction is already active on the scoped session (e.g. an outer
    `@Transactional()` already opened one), the call joins it. Otherwise a new
    transaction is started and committed on success / rolled back on error.
    """

    def __call__[**P, T](
            self,
            func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def _transactional(*args: P.args, **kwargs: P.kwargs) -> T:
            # `async_scoped_session` does not proxy `in_transaction`; fetch the
            # underlying AsyncSession via `__call__` and ask it directly.
            if session().in_transaction():
                return await func(*args, **kwargs)
            async with session.begin():
                return await func(*args, **kwargs)

        return _transactional
