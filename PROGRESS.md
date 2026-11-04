# Progress

All phases are implemented and unit tested (31 tests).

- [x] 1. create, local mode, strict DNS, Traefik bootstrap
- [x] 2. list, info, start, stop, restart, logs, shell, bench, delete
- [x] 3. apps (create-time and `fmt apps list|add|remove`), layered builds
- [x] 4. backup, restore, update, rollback, clone
- [x] 5. ssl status, doctor
- [x] 6. install.sh, README, docs, CI

Verified on a VPS: create, Traefik detection, doctor, ssl status, Let's Encrypt issuance (after a DNS-propagation retry). Still to verify: apps add, update, rollback, backup, restore, clone.
Next: `fmt ssl retry`, public-resolver DNS check, then the unverified commands above.
