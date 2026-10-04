# Pinned Termux packages

Official Termux .deb packages from which the PRoot launcher libraries bundled in the APK are extracted.
`prepare_android_toolchain.py` verifies each file against its pinned size and SHA-256 before use.
They are kept here because the Termux repository removes old package versions, which would otherwise
break builds from source.

| Package | License | Upstream |
|---|---|---|
| proot 5.1.107.95 | GPL-2.0 | https://github.com/termux/proot |
| libtalloc 2.4.3 | LGPL-3.0-or-later | https://talloc.samba.org |
| libandroid-shmem 0.7 | BSD-3-Clause | https://github.com/termux/libandroid-shmem |

Corresponding source for the shipped binaries is packaged into the APK at build time; see
`THIRD_PARTY_NOTICES.md`.
