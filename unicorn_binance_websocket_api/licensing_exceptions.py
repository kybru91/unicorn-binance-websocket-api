#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ¯\_(ツ)_/¯
#
# File: lucit_licensing_python/licensing_exceptions.py
#
# Project website: https://www.lucit.tech/lucit-licensing-python.html
# Github: https://github.com/oliver-zehentleitner/lucit-licensing-python
# Documentation: https://lucit-licensing-python.docs.lucit.tech
# PyPI: https://pypi.org/project/lucit-licensing-python
#
# License: LSOSL - LUCIT Synergetic Open Source License
# https://github.com/oliver-zehentleitner/lucit-licensing-python/blob/master/LICENSE
#
# Author: Oliver Zehentleitner
#
# Copyright (c) 2023-2023, LUCIT Systems and Development (https://www.lucit.tech)
# All rights reserved.

# define Python user-defined exceptions
class NoValidatedLucitLicense(Exception):
    """
    No valid LUCIT license verification.
    """
    pass
