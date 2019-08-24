#! /bin/bash
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab ai

set -e

conda_prefix=.conda

# default values for MINICONDA_LOCATION and CONDA_ENV
: ${MINICONDA_LOCATION:=~/.miniconda}
: ${MINICONDA_URL:=https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh}
: ${CONDA_ENV:=main}

echo "Detect conda"
# load conda activation script if not loaded
if ! [ type conda &> /dev/null || which conda &> /dev/null ]; then
    if ! [ -f "${MINICONDA_LOCATION}/bin/activate" ]; then
        echo "Conda not detected, installing in ${MINICONDA_LOCATION}"
        curl -O "${MINICONDA_URL}"
        bash "$( basename "${MINICONDA_URL}" )" -u -b -p "${MINICONDA_LOCATION}"
        rm "$( basename "${MINICONDA_URL}" )"
    fi
    echo "Load conda from ${MINICONDA_LOCATION}"
    source "${MINICONDA_LOCATION}/bin/activate"
fi

# create an environment with generic tools (tox, virtualenv, ...)
if ! [ -d "${conda_prefix}/${CONDA_ENV}" ]; then
    echo "Create main conda environment in ${conda_prefix}/${CONDA_ENV}"
    conda env create -f environment.yml -p "${conda_prefix}/${CONDA_ENV}"
fi
echo "Load main conda environment"
conda activate "${conda_prefix}/${CONDA_ENV}"

# create runtime environments
envs=( py27 py34 py35 py36 py37 )
declare -A versions
versions[py27]=2.7
versions[py34]=3.4
versions[py35]=3.5
versions[py36]=3.6
versions[py37]=3.7

for env_name in "${envs[@]}"; do
    echo "Create and install ${env_name}"
    version="${versions[${env_name}]}"
    conda create -q -y -p "${conda_prefix}/${env_name}" > /dev/null || \
        { echo "${env_name} creation failed; abort"; false; }
    # anaconda repo is needed for python 3.4
    # openssl support must be included for python 3.4 and 3.5
    conda install -q -y -c anaconda -p "${conda_prefix}/${env_name}" python="${version}" pyopenssl > /dev/null || \
        { echo "${env_name} installation failed; abort"; false; }
done

