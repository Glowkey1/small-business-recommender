import os

def test_raw_dataset_dirs():
    assert os.path.exists("data/raw/dataset_1")
    assert os.path.exists("data/raw/dataset_2")
