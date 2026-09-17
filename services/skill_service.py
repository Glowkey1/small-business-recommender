from models.skill import Skill

class SkillService:
    @staticmethod
    def get_all():
        return Skill.query.order_by(Skill.name).all()
