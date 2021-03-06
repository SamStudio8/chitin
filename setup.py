#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools

requirements = [
    #"prompt_toolkit",
    "pygments",
    "paramiko",
    "pillow",
    "requests",
    "whichcraft",
]

test_requirements = [

]

setuptools.setup(
    name="chitin",
    version="0.2.0",
    url="https://github.com/samstudio8/chitin",

    description="",
    long_description="",

    author="Sam Nicholls",
    author_email="sam@samnicholls.net",

    maintainer="Sam Nicholls",
    maintainer_email="sam@samnicholls.net",

    packages=setuptools.find_packages(),
    install_requires=requirements,

    entry_points = {
        'console_scripts': [
            'chitin-script = chitin.client:exec_script',
            'chitin-tag = chitin.client:tag',
            'chitin-notice = chitin.client:notice',
            'chitin-group = chitin.client:group',
            'chitin = chitin.client:cli',
            #'chitin = chitin:shell',
            #'chitin-daemon = chitin.daemon:daemonize',
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

)
