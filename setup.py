from setuptools import setup, find_packages
import os
print find_packages(".")
setup(
    name="evserver",
    description = "EvServer - Asynchronous WSGI http server",
    version = "0.01",
    keywords = "wsgi awsgi django asynchronous libevent",
    author = "Marek Majkowski",
    url = "",
    license = "GPL",
    package_data = {'': ['*.so']},
    packages = ['evserver', 'evserver.management', 'evserver.management.commands'],
    package_dir = {'':"."},

    entry_points = {
        'console_scripts': ['evserver = evserver.evserver:egg_entry_point'],
    },
)

