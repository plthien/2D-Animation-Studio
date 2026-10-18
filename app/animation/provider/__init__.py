"""Animation-owned errors for extracted G-Labs donor client; no legacy domain imports."""
class AppError(Exception):
    def __init__(self, code, message, status=502, *, retryable=False, details=None):
        super().__init__(message)
        self.code,self.message,self.status,self.retryable,self.details=code,message,status,retryable,details or {}
