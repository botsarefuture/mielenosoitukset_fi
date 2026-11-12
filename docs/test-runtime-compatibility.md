# Test runtime compatibility

The `python-tests` job temporarily uses `ubuntu-22.04`, not `ubuntu-latest`.
Python 3.12, MongoDB 8, Redis, Mailpit, LocalStack, Chromium and the complete
required pytest command remain unchanged. Production jobs/hosts are not changed.

## Observed failure (2026-10-22)

[Run 39733692011](https://github.com/botsarefuture/mielenosoitukset_fi/actions/runs/39733692011)
failed before tests: MongoDB refused to start because of its kernel compatibility
check. The runner used Ubuntu 24 image 20261018.339.1, whose
[image manifest](https://github.com/actions/runner-images/blob/ubuntu24/20261018.339/images/ubuntu/Ubuntu2404-Readme.md)
lists kernel 7.0.0. The earlier Ubuntu 24 image 20261012.334.1 had kernel 6.17.
Simply pinning `ubuntu-24.04` would not fix this observed failure.

[MongoDB's production notes](https://www.mongodb.com/docs/manual/administration/production-notes/)
identify kernels 6.19 through 7.0.13 as incompatible and explain that MongoDB stops
at startup to avoid crashes. Docker containers share their host kernel.
The current [Ubuntu 22 manifest](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2204-Readme.md)
lists kernel 6.8; the new hosted CI run, not this static document, must verify startup
and complete the suite. No known-incompatibility check is disabled.

## Removal condition

This is a temporary host selection, not a database downgrade or pinned image
snapshot. Re-evaluate a supported runner with a compatible MongoDB/kernel pairing
and run the full required suite before changing the guard in
`tests/test_ci_runtime_contract.py`. Record actual runner/kernel/service evidence.
Do this before the [Ubuntu 22 retirement deadline](https://github.com/actions/runner-images/issues/14254)
of 2027-04-17; its deprecation can already cause longer queues.
