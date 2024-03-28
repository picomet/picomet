class ActionRedirect(Exception):
    """A redirection from action."""

    def __init__(self, redirect_to: str, update: bool = True):
        super().__init__(redirect_to, update)
