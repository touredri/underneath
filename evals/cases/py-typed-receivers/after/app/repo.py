class BaseRepo:
    def save(self, item):
        self.items = getattr(self, "items", []) + [item]
        return item


class UserRepo(BaseRepo):
    def find(self, user_id):
        return next((u for u in getattr(self, "items", []) if u["id"] == user_id), None)


class Mailer:
    def send(self, to, text):
        return {"to": to, "text": text}

    def get(self, key):
        return key
