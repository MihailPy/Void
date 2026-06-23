import re
import tomllib

from void.__version__ import __version__


def test_pyproject_version_and_python_match_readme():
    pyproject = tomllib.loads(open("pyproject.toml", encoding="utf-8").read())
    readme = open("README.md", encoding="utf-8").read()

    assert pyproject["project"]["version"] == __version__
    assert pyproject["project"]["requires-python"] == ">=3.11"
    assert "Python 3.11+" in readme
    assert f"Void v{__version__}" in readme
    assert not re.search(r"Add your description here", pyproject["project"]["description"])
