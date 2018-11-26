#!/usr/bin/env python3
import unittest
from setuptools import setup, find_packages


def test_suite():
    test_loader = unittest.TestLoader()
    return test_loader.discover('tests', pattern='*_test.py')


setup(name='prometheus-distributed-client',
      version='0.2.0',
      description='',
      classifiers=[
          "Programming Language :: Python :: 3",
          "License :: OSI Approved :: GNU General Public License v3 (GPLv3)"],
      license="GPLv3",
      author="François Schmidts",
      author_email="francois@schmidts.fr",
      maintainer="François Schmidts",
      maintainer_email="francois@schmidts.fr",
      packages=find_packages(),
      url='https://github.com/dolead/prometheus-distributed-client/',
      install_requires=['prometheus-client>=0.0.21', 'redis>=2.10.5'],
      tests_require=['mock'],
      test_suite='setup.test_suite',
      )
