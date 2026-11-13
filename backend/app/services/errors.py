class NotFound(Exception):
    def __init__(self, what: str, ident: object):
        super().__init__(f"{what} bulunamadı: {ident}")


class BadRequest(Exception):
    pass
