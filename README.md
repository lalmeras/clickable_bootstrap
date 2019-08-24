# Usage

TODO

# Tests

Tests are launched for python 2.7, 3.4, 3.5, 3.6 and 3.7.

Tests use conda to provide python runtimes, and tox for management.

To install conda command :

``` bash
curl -slJ https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh | bash -s -p ~/.miniconda2
```

To install and prepare python runtimes

``` bash
./dev-setup.sh
```

To launch tox tests

``` bash
.conda/main/bin/tox
```

