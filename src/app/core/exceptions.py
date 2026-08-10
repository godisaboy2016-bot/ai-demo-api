class AppException(Exception):
    """
    Base application exception.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "internal_error",
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

        super().__init__(message)


class DeepSeekError(AppException):
    """
    Raised when DeepSeek API call fails.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 502,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status_code,
            error_code="deepseek_error",
        )


class AuthError(AppException):
    """
    Raised when authentication fails.
    """

    def __init__(
        self,
        message: str = "Invalid credentials.",
        error_code: str = "invalid_credentials",
    ) -> None:
        super().__init__(
            message=message,
            status_code=401,
            error_code=error_code,
        )


class ConflictError(AppException):
    """
    Raised when a resource conflicts with an existing one.
    """

    def __init__(
        self,
        message: str = "Resource already exists.",
        error_code: str = "user_already_exists",
    ) -> None:
        super().__init__(
            message=message,
            status_code=409,
            error_code=error_code,
        )
