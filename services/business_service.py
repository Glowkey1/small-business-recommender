from models.business import Business

class BusinessService:
    @staticmethod
    def get_all():
        return Business.query.all()

    @staticmethod
    def get_by_name(b_type):
        return Business.query.filter_by(business_type=b_type).first()
