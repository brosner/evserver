from setuptools import setup, find_packages
from setuptools.dist import Distribution
import os
import subprocess
import re

version = "0.01"

try:
    proc = subprocess.Popen(["svn", "info"], stdout=subprocess.PIPE)
    svn = proc.stdout.read()

    rev = int(re.compile(r"Revision: ([0-9]*)").findall(svn)[0])
    version = "%s-r%s" % (version, rev)
except Exception:
    pass


class MyDist(Distribution):
     def has_ext_modules(self):
         return True

setup(
    name="evserver",
    description = "EvServer - Asynchronous WSGI http server",
    version = version,
    keywords = "wsgi awsgi django asynchronous libevent",
    author = "Marek Majkowski",
    url = "http://code.google.com/p/evserver/wiki/Documentation",
    license = "BSD",
    package_data = {'': ['*.so']},
    packages = ['evserver', 'evserver.management', 'evserver.management.commands'],
    package_dir = {'':"."},

    entry_points = {
        'console_scripts': ['evserver = evserver.evserver:egg_entry_point'],
    },
    distclass = MyDist,
)

