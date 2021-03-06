#!/usr/bin/env bash

mkdir build
cd build

cmake $RECIPE_DIR -DCMAKE_INSTALL_PREFIX=$PREFIX -DCMAKE_Fortran_COMPILER=$FC -DCMAKE_Fortran_FLAGS="${FFLAGS}"
make VERBOSE=1
make install

mkdir $PREFIX/share/pac99
cp $RECIPE_DIR/new.groups $PREFIX/share/pac99/.
