from enum import Enum


class ResponseCode(Enum):
    OK = 1
    FAILURE = 2
    INVALID_DATA = 3


class Response:
    def __init__(self, result, code, comment=None):
        if comment is None:
            comment = ''
        self.result = result
        self.code = code
        self.comment = comment

    def __str__(self):
        return f'{{result: {self.result}; code: {self.code}; comment: {self.comment}}}'
