#! /bin/bash

# use python 2.6 compatible releases
.conda/py26/bin/pip install pytest==3.2.5 py==1.4.34 ordereddict==1.1
.conda/py26/bin/pytest
