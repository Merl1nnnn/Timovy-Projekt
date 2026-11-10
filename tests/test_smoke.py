import importlib


def test_packages_importable() -> None:
    for name in ["mock_sites", "scraper", "parser", "storage", "app"]:
        importlib.import_module(name)
