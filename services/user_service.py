from models import db
from models.user import User

class UserService:
    @staticmethod
    def get_by_id(user_id):
        return User.query.get(user_id)
