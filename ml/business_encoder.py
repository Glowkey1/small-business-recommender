import pandas as pd

def encode_business_categories(df):
    if "category" in df.columns:
        return pd.get_dummies(df, columns=["category"], drop_first=True)
    return df
