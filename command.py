class Command:
    def __init__(self, names):
        if isinstance(names, str):
            self.names = [names]
        else:
            self.names = names
