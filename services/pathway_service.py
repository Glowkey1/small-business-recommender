from ml.pathway_generator import BusinessPathwayGenerator

class PathwayService:
    @staticmethod
    def create_pathway(business_data, user_profile):
        return BusinessPathwayGenerator.generate(business_data, user_profile)
