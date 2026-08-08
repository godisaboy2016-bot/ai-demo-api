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
