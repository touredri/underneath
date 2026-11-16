import requests

from .repo import Mailer, UserRepo


class Signup:
    def __init__(self, repo: UserRepo):
        self.repo = repo
        self.mailer = Mailer()

    def register(self, email, settings: dict):
        user = self.repo.save({"id": email, "email": email})
        self.mailer.send(email, "Welcome")
        return user, settings.get("plan")


def check(user_id, repo: UserRepo, http: requests.Session):
    found = repo.find(user_id)
    http.get("https://example.invalid/ping")
    return found
