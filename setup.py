# let's do our part to encourage the use of distribute
import os

LONG_DESCRIPTION = ''
readme_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'README.rst'))
try:
    readme_file = open(readme_path, 'r')
    try:
        LONG_DESCRIPTION = readme_file.read()
    finally:
        readme_file.close()
except: # couldn't find readme?
    pass 

# To install, do the following...
# python setup.py install
from setuptools import setup, find_packages

setup(
    name = "bugger",
    version = "0.2",
    packages = find_packages(),
    
    package_data = {
        '': ['*.txt',],
    },
    
    author = "Paul Osborne",
    author_email = "osbpau@gmail.com",
    description = "Easily embed accessible python interactive console into your application",
    license = "MIT",
    keywords = "bugger interactive InteractiveConsole interpreter console code InteractiveInterpreter",
    url = "http://github.com/posborne/bugger",
    long_description = LONG_DESCRIPTION,
)

# Note to self...
# ... first, build the documentation for this release and run tests
# python setup.py release sdist bdist_egg register upload
# python setup.py upload_docs --upload-dir=docs/_build/html
