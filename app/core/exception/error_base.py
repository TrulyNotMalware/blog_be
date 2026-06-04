from app.core.exception.codes import ErrorCode


class CustomException(Exception):
    def __init__(self, code: ErrorCode, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class PostNotFound(CustomException):
    def __init__(self, post_id: str) -> None:
        super().__init__(ErrorCode.POST_NOT_FOUND, f"Post not found: {post_id}", 404)


class TagNotFound(CustomException):
    def __init__(self, name: str) -> None:
        super().__init__(ErrorCode.TAG_NOT_FOUND, f"Tag not found: {name}", 404)


class SlugConflict(CustomException):
    def __init__(self, slug: str) -> None:
        super().__init__(ErrorCode.SLUG_CONFLICT, f"Slug already exists: {slug}", 409)


class Unauthorized(CustomException):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(ErrorCode.UNAUTHORIZED, message, 401)


class Forbidden(CustomException):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(ErrorCode.FORBIDDEN, message, 403)
