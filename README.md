# Usage

TODO

# Tests

Tests are launched for python 2.6, 2.7, 3.4, 3.5, 3.6 and 3.7.

Tests use conda to provide python runtimes, and tox for management. pytest is
directly used for python 2.6 (tox does not support python 2.6).

To install conda command :

``` bash
curl -O https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -u -b -p ~/.miniconda2
```

To install and prepare python runtimes

``` bash
./dev-setup.sh
```

To launch tox tests

``` bash
# To launch python 2.7 - 3.7 tests
.conda/main/bin/tox
# To launch python 2.6 tests
./dev-test-python-2.6.sh
```

