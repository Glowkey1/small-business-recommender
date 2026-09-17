import re
import numpy as np
import pandas as pd

def parse_experience_score(user_exp, req_exp):
    levels = {"beginner": 1, "intermediate": 2, "experienced": 3}
    u = levels.get(str(user_exp).lower(), 1)
    r = levels.get(str(req_exp).lower(), 1)
    return 1.0 if u >= r else 0.5

def parse_setup_score(user_setups, biz_setup):
    if not biz_setup or not user_setups:
        return 0.8
    bs = str(biz_setup).lower()
    for us in user_setups:
        if str(us).lower() in bs:
            return 1.0
    return 0.4
