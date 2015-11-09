# coding=utf-8
from setuptools import setup, find_packages
import os

setup(
    name='django-surround',
    packages=find_packages(),
    version='1.0.0',
    license='MIT',
    description='Library of useful utilities surrounding Django',
    author='Piotr Śniegowski',
    author_email='piotr.sniegowski@gmail.com',
    url='https://github.com/sniegu/django-surround',
    keywords=['django', 'utilities'],
    requires=['Django'],
    install_requires=['Django>=1.7'],
    classifiers=["Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 2.7"],
    package_data={ "": ["LICENSE.txt", "README.md"] },
)
