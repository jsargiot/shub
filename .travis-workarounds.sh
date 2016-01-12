#!/bin/bash
set -e
set -x

if [[ "${TOXENV}" == "pypy" ]]; then
    sudo add-apt-repository -y ppa:pypy/ppa
    sudo apt-get -qy update
    sudo apt-get install -y pypy pypy-dev
    # This is required because we need to get rid of the Travis installed PyPy
    # or it'll take precedence over the PPA installed one.
    sudo rm -rf /usr/local/pypy/bin
fi

if [[ "$TRAVIS_OS_NAME" == "osx" ]]; then
    brew update > /dev/null

    brew install python

    # Now easy_install and pip are in /usr/local we need to force link
    brew unlink python && brew link --overwrite python

    ls -ltrah /usr/local/bin

    PATH="/usr/local/bin:$PATH"

    /usr/local/bin/python --version

    /usr/local/bin/pip install --upgrade virtualenv

    # Create a virtualenv

    /usr/local/bin/virtualenv --help

    /usr/local/bin/virtualenv ~/virtualenv/python2.7
    ~/virtualenv/python2.7/bin/python --version

    /usr/local/bin/virtualenv -p /usr/local/bin/python ~/virtualenv/python2.7X
    ~/virtualenv/python2.7X/bin/python --version



fi

# Workaround travis-ci/travis-ci#2065
pip install -U wheel
