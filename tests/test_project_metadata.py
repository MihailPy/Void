import tomllib

from void.__version__ import __version__


def test_version_is_centralized_in_package_module():
    pyproject = tomllib.loads(open("pyproject.toml", encoding="utf-8").read())
    readme = open("README.md", encoding="utf-8").read()

    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "void.__version__.__version__"
    }
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == ["void*"]
    assert __version__ == "1.11.0"
    assert pyproject["project"]["requires-python"] == ">=3.11"
    assert "Python 3.11+" in readme
    assert "void/__version__.py" in readme
    assert "Add your description here" not in pyproject["project"]["description"]
