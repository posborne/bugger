# let's do our part to encourage the use of distribute
from distribute_setup import use_setuptools
use_setuptools()

# To install, do the following...
# python setup.py install
from setuptools import setup, find_packages

setup(
    name = "Bugger",
    version = "0.1",
    packages = find_packages(),
    
    package_data = {
        '': ['*.txt',],
    },
    
    author = "Paul Osborne",
    author_email = "osbpau@gmail.com",
    description = "Easily embed accessible python interactive console into your application",
    license = "MIT",
    keywords = "bugger interactive InteractiveConsole interpreter console code InteractiveInterpreter",
)

# Note to self...
# ... first, build the documentation for this release and run tests
# python setup.py release sdist bdist_egg register upload
# python setup.py upload_docs --upload-dir=docs/_build/html
