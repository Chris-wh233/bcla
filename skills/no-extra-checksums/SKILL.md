---
name: no-extra-checksums
description: "Apply automatically during BCLA resource acquisition, build commands, Dockerfile/Makefile editing, recipe/export generation and result reporting. Avoid added SHA-256 verification and checksum files."
---

# No extra checksums

Do not add discretionary SHA-256 verification commands, checksum files/manifests or digest listings to tasks, generated files or final responses, even if a publisher provides hashes. Do not substitute another extra checksum/signature step.

Confirm fetched source revisions against the requested commit/tag. Preserve checks from the upstream Dockerfile for their original inputs, or checks explicitly requested by the user; do not extend them to other artifacts or reuse old hashes for changed inputs. Omit discretionary checks introduced during the task from generated recipes/exports, without altering historical evidence or unrelated user files.

Leave existing package/build-tool integrity checks, Docker digests and BCLA's internal accepted-file/KB hashes intact; no additional manual hashing is needed. Continue version, architecture/ABI and functional validation.
