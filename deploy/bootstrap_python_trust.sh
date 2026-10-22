#!/usr/bin/env bash
# Bootstrap from the SHA256 published by the Python security announcement.
# Do not use an unpinned index download through pip's old bundled CA store.
set -euo pipefail

"${1:-python3}" -m pip install --disable-pip-version-check --no-cache-dir --upgrade \
  'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'
