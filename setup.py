#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools

requirements = [
    "prompt_toolkit",
    "pygments",
    "SQLAlchemy",
    "flask_sqlalchemy",
    "paramiko",
    "pillow",
]

test_requirements = [

]

setuptools.setup(
    name="chitin",
    version="0.0.1",
    url="https://github.com/samstudio8/chitin",

    description="",
    long_description="",

    author="Sam Nicholls",
    author_email="sam@samnicholls.net",

    maintainer="Sam Nicholls",
    maintainer_email="sam@samnicholls.net",

    packages=setuptools.find_packages(),
    include_package_data=True,

    package_data={
        "chitin": [
            "web/templates/*html",
        ]
    },

    install_requires=requirements,

    entry_points = {
        'console_scripts': [
            'chitin = chitin:shell',
            'chitin-web = chitin:make_web',
        ]
    },

    classifiers = [
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'License :: OSI Approved :: MIT License',
    ],

    test_suite="tests",
    tests_require=test_requirements,

    zip_safe=False, #https://github.com/pallets/flask/issues/1562
)
