import requests


class TelegramAPI:
    URL = 'https://api.telegram.org/bot'

    class Method:
        def __init__(self, token, method):
            self.token = token
            self.method = method

        def __call__(self, **kwargs):
            return requests.get(f'{TelegramAPI.URL}{self.token}/{self.method}', data=kwargs).json()

    def __init__(self, token):
        self.token = token

    def __getattr__(self, item):
        return TelegramAPI.Method(self.token, item)


def main():
    token = None
    with open('token.txt', 'r') as file:
        token = file.read()
    api = TelegramAPI(token)
    print(api.getUpdates(offset=0, timeout=0, allowed_updates=['message']))


if __name__ == "__main__":
    main()
