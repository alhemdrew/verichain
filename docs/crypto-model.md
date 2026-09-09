# Crypto Model

VeriChain relies on a simple verification-first model: preserve evidence, compute the canonical fingerprint, seal the manifest, and validate the signature and chain of custody.

## Hashing

- SHA-256 for file and manifest integrity

## Signing

- Ed25519 signing with a local server-side keypair
- Key IDs and signatures are stored with the evidence record

## Custody

- Every event is chained with previous hashes and stored with timestamps and actor metadata

## Local safe handling

- Private keys, DBs, and evidence vault artifacts are never committed to Git
