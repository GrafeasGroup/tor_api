#!/usr/bin/env python

import os
import sys
import codecs
import re
from setuptools import (
    setup,
    find_packages,
)
from setuptools.command.test import test as TestCommand

from tor_api import __version__


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to pytest")]

    # noinspection PyAttributeOutsideInit
    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ''

    def run_tests(self):
        import shlex
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


def long_description():
    if not (os.path.isfile('README.rst') and os.access('README.rst', os.R_OK)):
        return ''

    with codecs.open('README.rst', encoding='utf8') as f:
        return f.read()


testing_deps = [
    'pytest',
    'pytest-cov',
]
dev_helper_deps = [
    'better-exceptions',
]

requires = []
dep_links = []
# parse requirements file
with open('requirements/base.txt') as f:
    comment = re.compile('(^#.*$|\s+#.*$)')
    for line in f.readlines():
        line = line.strip()
        line = comment.sub('', line)
        if line:
            if line.startswith('git+'):
                dep_links.append(line)
                if '#egg=' in line:
                    requires.append(
                        line.split('#egg=', 1)[1].replace('-', '==')
                    )
            else:
                requires.append(line)

print(requires)
print(dep_links)

setup(
    name='tor-api',
    version=__version__,
    description='Web API server for handling statistics for r/TranscribersOfReddit',
    long_description=long_description(),
    url='https://github.com/GrafeasGroup/tor-api',
    author='Joe Kaufeld',
    author_email='joe.kaufeld@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 1 - Planning',

        'Intended Audience :: End Users/Desktop',
        'Topic :: Communications :: BBS',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='',
    packages=find_packages(exclude=['test', 'test.*', '*.test', '*.test.*']),
    zip_safe=True,
    cmdclass={'test': PyTest},
    test_suite='test',
    # entry_points={
    #     'console_scripts': [
    #         'tor-api=tor-api:main',
    #     ],
    # },
    extras_require={
        'dev': testing_deps + dev_helper_deps,
    },
    setup_requires=["pytest-runner"],
    tests_require=testing_deps,
    install_requires=requires,
    dependency_links=dep_links,
)
