# Threat Model

## Assets

- Evidence files and their preserved hashes
- Signing keys and key identifiers
- Investigation metadata and custody chain
- User identities and organization membership

## Threats

- Unauthorized file tampering
- Evidence replacement or deletion
- Credential leakage
- Key compromise
- Missing audit trail

## Controls

- Strong hashing
- Manifest sealing
- Signature verification
- Organization-scoped access
- Audit logging for sensitive actions
- Exclusion of secrets and local data from source control
