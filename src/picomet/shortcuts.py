class Redirect(Exception):
    def __init__(self, redirect_to: str, update: bool = True):
        super().__init__(redirect_to, update)
