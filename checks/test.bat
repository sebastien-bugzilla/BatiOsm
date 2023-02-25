#!/bin/bash

# stop on error
# unset variable is to be considered as an error
set -eu

DIR=$(pwd)
WORK_DIR=$(mktemp -d)
PREFIX="check1_ci"

# deletes the temp directory
function cleanup {
  rm -rf "$WORK_DIR"
}

# register the cleanup function to be called on the EXIT signal
trap cleanup EXIT

{
    echo "Checks step 0: install prerequisites"
    cd "$WORK_DIR"
    virtualenv hop --quiet
    source hop/bin/activate
    pip install -r "${DIR}/../requirements.txt" --quiet

    echo "Checks step 1: run the script"
    python "${DIR}/../BatiOsm.py" "${DIR}/check1_as_in.osm" "${DIR}/check1_cadastre.osm" "$PREFIX"

    echo "Checks step 2: check logs are the same"
    sed -i -e "s/${PREFIX}_.*\.osm/REPLACEME/g" "${PREFIX}_log.txt"
    sed -i -e "s|${DIR}/||g" "${PREFIX}_log.txt"
    diff "${DIR}/check1_result_log.txt" "${PREFIX}_log.txt" -u0

    echo "Checks step 3: check generated osm file are the same"
    diff "${DIR}/check1_result_mod_1_a_104.osm" "${PREFIX}_mod_1_a_104.osm" -u0
    diff "${DIR}/check1_result_new_1_a_85.osm"  "${PREFIX}_new_1_a_85.osm" -u0
    diff "${DIR}/check1_result_sup_1_a_15.osm"  "${PREFIX}_sup_1_a_15.osm" -u0
    diff "${DIR}/check1_result_unModified.osm"  "${PREFIX}_unModified.osm" -u0

    echo "Checks are done"
}