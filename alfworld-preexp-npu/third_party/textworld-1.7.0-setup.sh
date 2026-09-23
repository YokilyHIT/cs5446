#!/usr/bin/env bash

# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.

set -ex
echo "Running setup.sh...";

unameOut="$(uname -s)"
case "${unameOut}" in
    Linux*)     machine=Linux;;
    Darwin*)    machine=Mac;;
    CYGWIN*)    machine=Cygwin;;
    MINGW*)     machine=MinGW;;
    *)          machine="UNKNOWN:${unameOut}"
esac

cd textworld/thirdparty/

# Install command line Inform 7
if [ ! -e I7_6M62_Linux_all.tar.gz ]; then
    echo "Downloading Inform7 CLI"
    curl -LO http://emshort.com/inform-app-archive/6M62/I7_6M62_Linux_all.tar.gz
    if [ "${machine}" == 'Mac' ] && [ ! -e I7-6M62-OSX-Interim.dmg ]; then
        echo "Downloading Inform7 for Mac"
        curl -LO http://emshort.com/inform-app-archive/6M62/I7-6M62-OSX-Interim.dmg
    fi
fi
if [ ! -d inform7-6M62 ]; then
    tar xf I7_6M62_Linux_all.tar.gz
fi
(
    echo "Installing Inform7 CLI"
    cd inform7-6M62/
    # Manually extract the files from the tarballs instead of calling install-inform7.sh.
    # ./install-inform7.sh --prefix $PWD
    tar xzf "inform7-common_6M62_all.tar.gz"
    if [ "${machine}" != 'Mac' ]; then
        ARCH=$(uname -m)
        # PATCHED (aarch64 host): Inform7 6M62 only ships i386/x86_64/ppc/armv6lhf
        # binaries -- there is no aarch64 build. Those binaries are the Inform7
        # *compiler* (ni/inform6) and the glulx *interpreter*, which TextWorld
        # only needs to GENERATE new .ulx games or play z-machine/glulx games.
        # ALFWorld's TextWorld tasks are pre-generated .tw-pddl games executed by
        # textworld/envs/pddl (pure Python), so a missing compiler for this arch
        # is not fatal -- warn and continue instead of aborting the whole build.
        if [ -e "inform7-compilers_6M62_${ARCH}.tar.gz" ]; then
            tar xzf "inform7-compilers_6M62_${ARCH}.tar.gz"
            tar xzf "inform7-interpreters_6M62_${ARCH}.tar.gz"
        else
            echo "WARNING: no Inform7 6M62 binaries for ARCH=${ARCH}; skipping."
            echo "         Generating new TextWorld games will not work on this host;"
            echo "         playing pre-generated .tw-pddl games (ALFWorld) still does."
        fi
    fi

    cd ..
    rm -f inform7-6M62/share/inform7/Internal/I6T/Actions.i6t
    cp inform7/share/inform7/Internal/I6T/Actions.i6t inform7-6M62/share/inform7/Internal/I6T/Actions.i6t
)

# Mount DMG if we're using a Mac
if [ "${machine}" == 'Mac' ] && [ -e inform7-6M62 ]; then
    echo "Mounting Inform for Mac"
    hdiutil attach ./I7-6M62-OSX-Interim.dmg

    echo "Copying Mac compiled inform files"
    current_dir="$(pwd)"
    cd /Volumes/Inform/Inform.app/Contents/MacOS
    mkdir -p "$current_dir/inform7-6M62/share/inform7/Compilers/"
    cp inform6 ni "$current_dir/inform7-6M62/share/inform7/Compilers/"

    cd "$current_dir"

    echo "Unmounting Inform for Mac"
    hdiutil detach /Volumes/Inform/
fi
