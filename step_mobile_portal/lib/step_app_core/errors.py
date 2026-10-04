"""Errores de la API con código estable (el cliente decide por `code`, nunca por el texto)."""


class ApiError(Exception):
    def __init__(self, code: str, status: int = 400, message: str = ''):
        super().__init__(code)
        self.code, self.status, self.message = code, status, message or code
        # Un error es «terminal» si reintentar la misma operación no cambiará el resultado.
        self.terminal = status in (400, 404, 409, 410, 422)

    def payload(self) -> dict:
        return {'ok': False, 'error': self.code, 'message': self.message, 'terminal': self.terminal}
