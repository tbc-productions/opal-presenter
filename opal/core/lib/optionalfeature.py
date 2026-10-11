"""Plugin support for features whose services start with the application."""


class RestartRequiredFeature:
    """Save activation changes for the next application session."""

    requires_restart = True

    def toggle_status(self, new_status):
        self.status = new_status
        self.settings.setValue(f'{self.name}/status', new_status)
