
# VERICHAIN

## Digital Evidence Collection, Integrity & Chain-of-Custody Platform

### Product & Technical Specification — v1.0

---

# 1. PRODUCT DEFINITION

## Product Name

**VeriChain**

## Product Category

Digital Evidence Collection, Preservation, Integrity Verification and Chain-of-Custody Platform.

## Core Statement

> **Don't just store evidence. Prove its history.**

## Mission

VeriChain provides a trustworthy digital lifecycle for evidence from the moment it is collected until the moment it is reviewed, shared, verified, or presented.

The platform must allow authorised users to:

* collect evidence;
* preserve the original;
* establish a cryptographic fingerprint at collection;
* record contextual metadata;
* establish who collected it and when;
* maintain a tamper-evident custody trail;
* protect locally stored evidence;
* synchronize evidence to a central server;
* continue operating when offline;
* securely share evidence;
* create controlled derivatives without destroying the original;
* verify evidence independently;
* detect modification;
* generate a human-readable evidence integrity report.

The system must not claim that cryptography proves that an underlying event actually happened. It proves the integrity and recorded history of the digital object.

---

# 2. H1 ALIGNMENT

VeriChain directly addresses the H1 challenge:

**Media & Civic Trust — Proving Digital Evidence Has Not Been Changed.**

The challenge identifies the central problem as evidence being copied through flash drives, email, shared computers and folders without reliable answers to:

* whether the copy matches the original;
* who handled it;
* what happened to it;
* whether it was changed.

It specifically requires a working prototype that:

1. records evidence from collection;
2. makes later changes detectable;
3. maintains a custody trail;
4. demonstrates deliberate alteration detection;
5. produces a simple report understandable by a judge or panel;
6. works when collection occurs without network connectivity.

VeriChain must demonstrate all six.

---

# 3. PRODUCT PRINCIPLES

## Principle 1 — Preserve, don't modify

The original evidence must never be altered simply to make it easier to share.

If metadata needs to be removed for privacy, create a derivative.

Never overwrite the original.

---

## Principle 2 — Integrity begins at collection

The first trusted cryptographic fingerprint must be created as close as possible to the moment evidence enters the system.

---

## Principle 3 — Offline does not mean unprotected

The system must continue to:

* identify evidence;
* hash evidence;
* record custody;
* protect local evidence;
* queue synchronization;

when the network is unavailable.

---

## Principle 4 — Online provides independent continuity

When connectivity exists, evidence and its integrity records synchronize to the central platform.

The server provides an independent remote copy and verification point.

---

## Principle 5 — Never rewrite history

The custody record is append-oriented.

A correction or new action creates another event.

It does not silently rewrite an old event.

---

## Principle 6 — Detection over impossible promises

VeriChain must not claim:

> "Tampering is impossible."

It claims:

> "Unauthorized modification of protected evidence or its recorded history is detectable."

---

## Principle 7 — The original and derivative are different objects

An anonymized/sanitized version is a derivative.

It has:

* its own ID;
* its own hash;
* its own creation event;
* its own provenance linking it to the parent.

---

# 4. TARGET USERS

## Investigator / Collector

Collects and manages evidence.

Capabilities:

* create cases;
* collect evidence;
* enter collection context;
* seal evidence;
* view assigned evidence;
* synchronize;
* share evidence;
* generate reports.

---

## Reviewer

Reviews and verifies evidence.

Capabilities:

* view authorised evidence;
* verify integrity;
* inspect custody;
* download where permitted;
* access reports.

---

## Administrator

Manages the platform.

Capabilities:

* manage users;
* manage roles;
* manage cases;
* manage permissions;
* inspect system audit events;
* manage organization settings.

The administrator must not have a hidden mechanism to silently rewrite evidence history.

---

# 5. HIGH-LEVEL ARCHITECTURE

```text
                         ┌─────────────────────┐
                         │      INTERNET       │
                         └──────────┬──────────┘
                                    │
                           HTTPS / Secure API
                                    │
                   ┌────────────────▼────────────────┐
                   │        VERICHAIN CLOUD          │
                   │                                 │
                   │            API                  │
                   │             │                   │
                   │      ┌──────▼──────┐            │
                   │      │ PostgreSQL  │            │
                   │      └─────────────┘            │
                   │             │                   │
                   │      ┌──────▼──────┐            │
                   │      │ Evidence    │            │
                   │      │ Object      │            │
                   │      │ Storage     │            │
                   │      └─────────────┘            │
                   │             │                   │
                   │      ┌──────▼──────┐            │
                   │      │ Integrity / │            │
                   │      │ Audit       │            │
                   │      └─────────────┘            │
                   └────────────────┬────────────────┘
                                    │
                                    │
              ┌─────────────────────▼─────────────────────┐
              │               FIELD DEVICE                │
              │                                           │
              │             VERICHAIN DESKTOP             │
              │                                           │
              │     React + TypeScript + Tauri/Rust       │
              │                    │                      │
              │          ┌─────────▼─────────┐            │
              │          │ Local SQLite     │            │
              │          └───────────────────┘            │
              │                    │                      │
              │          ┌─────────▼─────────┐            │
              │          │ Encrypted Evidence│            │
              │          │ Vault             │            │
              │          └───────────────────┘            │
              │                    │                      │
              │          ┌─────────▼─────────┐            │
              │          │ Hash / Signature  │            │
              │          │ / Custody Engine  │            │
              │          └───────────────────┘            │
              │                                           │
              │              OFFLINE CAPABLE              │
              └───────────────────────────────────────────┘
                                    │
                              Sync when online
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   REVIEWER WEB APP  │
                         └─────────────────────┘
```

---

# 6. TECHNOLOGY STACK

## Desktop Application

**Tauri + React + TypeScript**

Tauri provides the native application layer while allowing the interface to use the same modern web technology stack.

Rust should handle sensitive native operations where appropriate:

* filesystem operations;
* encrypted vault operations;
* hashing;
* signing;
* local database access;
* synchronization primitives.

The UI should not directly manipulate protected evidence files.

---

## Web Application

React + TypeScript.

The desktop and web applications should share:

* design system;
* types;
* API models;
* visual language;
* validation conventions.

---

## Backend

**FastAPI + Python**

Responsibilities:

* authentication;
* authorization;
* case management;
* evidence APIs;
* synchronization;
* integrity verification;
* sharing;
* audit events;
* report generation.

---

## Database

**PostgreSQL**

Stores structured records, not the only copy of large binary evidence.

---

## Local Database

**SQLite**

Stores:

* cases;
* evidence metadata;
* custody events;
* sync queue;
* local state;
* verification results.

---

## Evidence Storage

Use an object-storage abstraction.

For the prototype, local/server filesystem-backed object storage is acceptable.

The code must not hard-code the storage implementation.

Design an interface such as:

```text
EvidenceStorage
 ├── LocalStorage
 └── ServerObjectStorage
```

so the implementation can later use S3-compatible storage, MinIO, cloud object storage, etc.

---

# 7. EVIDENCE LIFECYCLE

Every evidence item follows a defined lifecycle.

```text
COLLECTED
    ↓
HASHED
    ↓
SEALED
    ↓
LOCALLY PROTECTED
    ↓
SYNC QUEUED
    ↓
SERVER SYNCHRONIZED
    ↓
SERVER VERIFIED
    ↓
AVAILABLE
    ↓
VIEWED / SHARED / DERIVED
    ↓
ARCHIVED
```

If integrity fails:

```text
AVAILABLE
    ↓
VERIFICATION FAILURE
    ↓
INTEGRITY ALERT
```

---

# 8. EVIDENCE IDENTITY

Every evidence item receives a globally unique identifier.

Example:

```text
EV-2026-000001
```

The ID is not the cryptographic identity by itself.

The cryptographic identity is represented by:

* evidence ID;
* original file hash;
* manifest;
* signature;
* custody chain.

---

# 9. EVIDENCE COLLECTION

The collector screen should provide:

### Case

Select existing case or create one.

### Evidence type

Examples:

* Video
* Image
* Audio
* Document
* Log
* Export
* Screenshot
* Archive
* Other

### Source

Examples:

* CCTV
* Mobile device
* Server
* Email export
* Transaction system
* User submission
* Other

### Description

Human-readable description.

### Collection notes

Optional contextual information.

### Collector

Authenticated user.

### Collection time

Automatically generated by the system.

### Original filename

Automatically captured.

### File size

Automatically captured.

### MIME/type

Automatically detected.

---

# 10. COLLECTION OPERATION

When the user selects a file:

```text
SELECT FILE
     ↓
READ FILE
     ↓
CALCULATE HASH
     ↓
CAPTURE METADATA
     ↓
GENERATE EVIDENCE ID
     ↓
CREATE MANIFEST
     ↓
SIGN MANIFEST
     ↓
ENCRYPT LOCAL COPY
     ↓
CREATE CUSTODY EVENT
     ↓
STORE LOCALLY
     ↓
QUEUE SYNCHRONIZATION
```

The UI should visually communicate this.

Example:

```text
COLLECTING EVIDENCE

Reading file                 ✓
Generating fingerprint       ✓
Capturing metadata           ✓
Creating evidence manifest   ✓
Securing local copy          ✓
Recording custody            ✓

EVIDENCE SEALED

EV-2026-000001
```

---

# 11. ORIGINAL EVIDENCE RULE

The system must preserve the original.

Do not:

* strip metadata from the original;
* resize the original;
* recompress the original;
* rename its logical identity;
* alter the contents.

The original hash is permanent for that evidence record.

If the user wants privacy protection:

```text
ORIGINAL
   │
   └── CREATE DERIVATIVE
              │
              ├── Sanitise metadata
              ├── Remove sensitive information
              └── Generate new hash
```

---

# 12. METADATA MODEL

Capture relevant metadata without pretending that every file format provides reliable metadata.

Possible fields:

```text
original_filename
mime_type
extension
size_bytes
created_at_if_available
modified_at_if_available
accessed_at_if_available
file_system_metadata
media_metadata_if_available
collection_timestamp
collector
source
device_information_if_available
```

Important distinction:

### Collection metadata

Information generated by VeriChain.

### Source metadata

Metadata originating from the supplied evidence.

They must not be confused.

---

# 13. CRYPTOGRAPHIC MODEL

The system must use mature, standard cryptographic libraries.

Do not implement cryptography manually.

---

## File integrity

Use SHA-256 for the evidence fingerprint.

Conceptually:

```text
SHA256(original_bytes)
        ↓
8A7F9D...C31
```

Any content change results in a different digest with overwhelming probability.

---

## Local confidentiality

Protected evidence stored locally should use authenticated encryption.

For example:

**AES-256-GCM**

or another mature authenticated-encryption construction supported by the chosen library.

Authenticated encryption provides confidentiality and integrity protection and is preferred over unauthenticated encryption modes.

---

# 14. KEY MANAGEMENT

Do not:

* hard-code encryption keys;
* store keys in source code;
* store plaintext keys beside evidence;
* put master secrets in ordinary JSON configuration;
* commit secrets to Git.

Use the operating system's secure credential/key storage where available.

The architecture should separate:

```text
DATA ENCRYPTION KEY
        │
        ▼
Encrypted / wrapped
        │
        ▼
KEY ENCRYPTION KEY / SECURE KEY STORE
```

Keys and encrypted data should be separated where practical.

The system must have a documented key-loss and key-compromise strategy.

---

# 15. DIGITAL SIGNATURES

Where practical, the evidence manifest should be digitally signed.

The signature should cover a canonical representation of the manifest.

Conceptually:

```text
Evidence Manifest
       ↓
Canonicalization
       ↓
Hash
       ↓
Private Signing Key
       ↓
Digital Signature
```

Verification:

```text
Manifest
   ↓
Hash
   ↓
Public Key
   ↓
Signature Verification
   ↓
VALID / INVALID
```

Digital signatures provide integrity and origin/authentication properties when the signing key is properly controlled.

For the prototype, do not build a complicated certificate authority unless required.

---

# 16. EVIDENCE MANIFEST

Every sealed evidence item should have a manifest.

Example conceptual structure:

```json
{
  "schema_version": "1.0",
  "evidence_id": "EV-2026-000001",
  "case_id": "CASE-2026-0001",
  "original_filename": "camera04.mp4",
  "mime_type": "video/mp4",
  "size_bytes": 284392120,
  "sha256": "8a7f...",
  "collected_at": "2026-09-01T14:23:10Z",
  "collector_id": "USR-001",
  "source_type": "CCTV",
  "description": "Camera 04 recording",
  "metadata": {},
  "manifest_version": 1
}
```

The actual implementation must use canonical serialization before signing.

---

# 17. CHAIN OF CUSTODY

Every action that materially affects the evidence lifecycle becomes an event.

Examples:

* COLLECTED
* HASHED
* SEALED
* LOCAL_STORED
* SYNC_QUEUED
* UPLOADED
* SERVER_VERIFIED
* VIEWED
* DOWNLOADED
* SHARED
* DERIVATIVE_CREATED
* VERIFIED
* ARCHIVED
* INTEGRITY_ALERT

---

# 18. CUSTODY EVENT STRUCTURE

```text
event_id
evidence_id
case_id
actor_id
action
timestamp
details
previous_event_hash
event_hash
signature
```

Conceptually:

```text
EVENT 001
      │
      └── Hash A
             │
EVENT 002 ────┘
      │
      └── Hash B
             │
EVENT 003 ────┘
      │
      └── Hash C
```

If Event 002 is modified, the subsequent chain no longer validates.

---

# 19. SERVER INTEGRITY VERIFICATION

When an evidence item reaches the server:

```text
CLIENT
 │
 │ file + manifest + hash + signature
 ▼
SERVER
 │
 ├── calculate received-file hash
 │
 ├── compare with client hash
 │
 ├── validate manifest
 │
 ├── validate signature
 │
 ├── validate custody continuity
 │
 └── store
```

Only after successful validation should the server mark the evidence:

```text
SERVER_VERIFIED
```

---

# 20. OFFLINE-FIRST SYNCHRONIZATION

The desktop application must not require internet connectivity for collection.

When offline:

```text
NETWORK
OFFLINE

Evidence collection       ✓
Hashing                    ✓
Local encryption           ✓
Custody recording          ✓
Verification               ✓
Viewing                    ✓
Synchronization            WAITING
```

The sync queue stores pending operations.

Example:

```text
SYNC QUEUE

EV-000031     Pending
EV-000032     Pending
EV-000033     Pending
```

When internet returns:

```text
CONNECTION RESTORED

EV-000031     Uploading... ✓
EV-000032     Uploading... ✓
EV-000033     Uploading... ✓

SERVER VERIFICATION         ✓
CUSTODY SYNCHRONIZATION     ✓

SYNC COMPLETE
```

---

# 21. SYNCHRONIZATION MUST BE IDEMPOTENT

This is important.

If the internet disappears during upload, the system must not accidentally create duplicate evidence records.

Every synchronization operation requires an idempotency identifier.

Example:

```text
sync_operation_id
```

The server must recognize:

> "I have already processed this operation."

and return the existing result rather than duplicating the evidence.

---

# 22. PARTIAL UPLOAD RECOVERY

Large evidence files may fail halfway through upload.

The system should support resumable upload architecture where practical.

Conceptually:

```text
284 MB FILE

0–50 MB       ✓
50–100 MB     ✓
100–150 MB    ✓
150–200 MB    ✗ connection lost

RECONNECT

Resume at 150 MB
```

For the prototype, this can initially be implemented at a simpler chunked-upload level.

---

# 23. LOCAL EVIDENCE VAULT

Evidence should not simply be exposed as normal files in a predictable folder.

Conceptually:

```text
VeriChain Vault
│
├── encrypted evidence
├── encrypted local metadata
├── SQLite database
├── manifests
└── sync queue
```

The desktop application controls access to the protected vault.

The system must use secure local permissions and encryption.

---

# 24. THREAT MODEL

VeriChain must explicitly document what it protects against.

## Threats addressed

### Accidental modification

Detected by cryptographic fingerprint.

### Malicious modification

Detected when verification occurs.

### File replacement

Detected because replacement content produces a different fingerprint.

### Custody-log alteration

Detected through the chained custody structure.

### Corrupted transfer

Detected by integrity validation.

### Unauthorized sharing

Controlled through permissions and share records.

### Lost connectivity

Handled by offline operation and synchronization queue.

### Server/client mismatch

Detected through independent verification.

---

# 25. THREATS THE PROTOTYPE DOES NOT CLAIM TO SOLVE

### Fully compromised operating system

If an attacker has complete privileged control of the endpoint, no ordinary application should claim absolute protection.

### Dishonest collector

Cryptography cannot prove that a collector truthfully described the real-world event.

### Compromised source device

If a CCTV system itself was compromised before acquisition, VeriChain cannot magically determine that.

### Physical destruction

Encryption and hashing do not prevent physical destruction of every copy.

### Compromised signing keys

Requires key rotation/revocation and incident response.

These limitations must be documented rather than hidden.

---

# 26. CASE MANAGEMENT

Dashboard:

```text
ACTIVE CASES
12

EVIDENCE ITEMS
438

VERIFIED
421

PENDING SYNC
7

INTEGRITY ALERTS
2
```

Case:

```text
CASE-2026-0001

RCN Digital Fraud Investigation

Status:
ACTIVE

Created:
01 Sep 2026

Investigator:
Investigator A

Evidence:
24

Verified:
23

Alerts:
1
```

---

# 27. EVIDENCE DETAIL SCREEN

Display:

```text
EV-2026-000001

CCTV Recording

STATUS
✓ VERIFIED

INTEGRITY
✓ VALID

SERVER
✓ SYNCHRONIZED

COLLECTED
01 Sep 2026 14:23

COLLECTOR
Investigator A

SHA-256
8A7F9D...C31

SIZE
284 MB
```

Actions:

```text
VIEW
VERIFY
SHARE
CREATE DERIVATIVE
DOWNLOAD
VIEW CUSTODY
GENERATE REPORT
```

---

# 28. VERIFICATION SCREEN

This should be one of the signature screens.

User provides evidence.

System:

```text
ANALYSING

Reading evidence............. ✓
Calculating SHA-256.......... ✓
Loading original fingerprint. ✓
Checking manifest............ ✓
Checking signature............✓
Checking custody..............✓
```

Result:

# ✓ INTEGRITY VERIFIED

> The supplied evidence matches the cryptographic fingerprint recorded by VeriChain.

If modified:

# ✗ INTEGRITY FAILURE

> The supplied evidence does not match the fingerprint recorded at collection.

Show:

```text
RECORDED
8A7F9D...C31

CURRENT
91B44A...77B
```

Do not expose unnecessary technical jargon by default.

Provide:

**View technical details**

for advanced users.

---

# 29. CUSTODY TIMELINE

Visual timeline:

```text
14:23
● Evidence collected
│
14:23
● Fingerprint generated
│
14:24
● Evidence sealed
│
14:27
● Synchronized
│
15:02
● Viewed by Investigator B
│
15:05
● Shared with Reviewer C
│
15:08
● Integrity verified
```

Every event can be expanded.

---

# 30. EVIDENCE SHARING

Sharing must be controlled.

User selects:

```text
Evidence:
EV-2026-000001

Recipient:
Reviewer B

Permissions:

☑ View
☑ Download
☐ Create derivative
☐ Reshare

Expiration:
7 days
```

The platform creates a share record.

Every access is auditable.

---

# 31. SHARE MODEL

Online:

```text
Investigator
      ↓
VeriChain Server
      ↓
Reviewer
```

Offline:

```text
Evidence
   ↓
VeriChain Package
   ↓
USB / Local Transfer / Other Approved Method
   ↓
Recipient VeriChain
   ↓
Import
   ↓
Verification
```

The package should contain:

```text
evidence
manifest
custody
signature
integrity information
package metadata
```

---

# 32. DERIVATIVE EVIDENCE

A derivative must maintain provenance.

Example:

```text
EV-000001
Original CCTV

        │
        └── EV-000001-D001
            Sanitized sharing copy
```

Derivative record:

```text
parent_evidence_id
derivative_id
reason
created_by
created_at
original_hash
derivative_hash
transformation_description
```

Example:

> Metadata removed for privacy-safe sharing.

The original remains untouched.

---

# 33. EVIDENCE REPORT

The report must be understandable by a non-technical audience.

Title:

# DIGITAL EVIDENCE INTEGRITY REPORT

Sections:

### Case

CASE-2026-0001

### Evidence

EV-2026-000001

### Description

CCTV recording from Camera 04.

### Collected

01 September 2026 — 14:23

### Collected By

Investigator A

### Original File

camera04.mp4

### Integrity Fingerprint

SHA-256: `8A7F...C31`

### Custody Summary

Evidence was collected, sealed, synchronized, reviewed and verified.

### Integrity Result

# VERIFIED

### Plain-language explanation

> The file examined matches the cryptographic fingerprint recorded when the evidence was collected. No change to the evidence file was detected.

### Technical Verification

Manifest:

VALID

Signature:

VALID

Custody chain:

VALID

Server record:

VALID

---

# 34. REPORT MUST ALSO SHOW FAILURE

If evidence was modified:

# INTEGRITY FAILURE

> The file examined does not match the cryptographic fingerprint recorded at collection. The system cannot establish that the supplied copy is identical to the original evidence.

This is extremely important.

Never generate a report that hides failures.

---

# 35. SECURITY ALERTS

Dashboard alert:

```text
⚠ INTEGRITY ALERT

Evidence:
EV-2026-000021

Reason:
Fingerprint mismatch

Recorded:
8A7F...C31

Current:
91B4...77B

Detected:
01 Sep 2026 16:42

ACTION REQUIRED
```

---

# 36. AUDIT SYSTEM

Separate from evidence custody, the platform should maintain application audit records.

Examples:

```text
LOGIN_SUCCESS
LOGIN_FAILURE
CASE_CREATED
EVIDENCE_COLLECTED
EVIDENCE_VIEWED
EVIDENCE_SHARED
EVIDENCE_DOWNLOADED
DERIVATIVE_CREATED
VERIFICATION_SUCCESS
VERIFICATION_FAILURE
SYNC_SUCCESS
SYNC_FAILURE
PERMISSION_CHANGED
INTEGRITY_ALERT
```

Security events should themselves be protected against silent modification.

---

# 37. DATABASE MODEL

## users

```text
id
organization_id
name
email
password_hash / identity_reference
role
status
created_at
updated_at
```

---

## organizations

```text
id
name
created_at
```

---

## cases

```text
id
organization_id
case_number
title
description
status
created_by
created_at
updated_at
```

---

## evidence

```text
id
case_id
evidence_number
original_filename
mime_type
size_bytes
sha256
collector_id
source_type
description
collection_timestamp
status
storage_reference
manifest_version
created_at
updated_at
```

---

## evidence_metadata

```text
id
evidence_id
metadata_type
key
value
source
created_at
```

---

## custody_events

```text
id
evidence_id
actor_id
action
timestamp
details
previous_event_hash
event_hash
signature
```

---

## derivatives

```text
id
parent_evidence_id
derivative_type
filename
sha256
created_by
reason
created_at
storage_reference
```

---

## shares

```text
id
evidence_id
created_by
recipient_id
permissions
expires_at
status
created_at
```

---

## sync_operations

```text
id
device_id
operation_id
entity_type
entity_id
operation_type
status
attempt_count
last_error
created_at
completed_at
```

---

## audit_events

```text
id
organization_id
actor_id
event_type
target_type
target_id
timestamp
metadata
event_hash
previous_event_hash
```

---

# 38. API STRUCTURE

Authentication:

```text
POST /auth/login
POST /auth/logout
POST /auth/refresh
GET  /auth/me
```

Cases:

```text
GET  /cases
POST /cases
GET  /cases/{id}
PATCH /cases/{id}
```

Evidence:

```text
GET  /cases/{id}/evidence
POST /evidence
GET  /evidence/{id}
GET  /evidence/{id}/manifest
GET  /evidence/{id}/custody
```

Upload:

```text
POST /evidence/{id}/upload/init
POST /evidence/{id}/upload/chunk
POST /evidence/{id}/upload/complete
```

Verification:

```text
POST /evidence/{id}/verify
POST /verification/package
```

Sharing:

```text
POST /evidence/{id}/shares
GET  /evidence/{id}/shares
DELETE /shares/{id}
```

Derivatives:

```text
POST /evidence/{id}/derivatives
GET  /evidence/{id}/derivatives
```

Synchronization:

```text
POST /sync/batch
GET  /sync/status
```

Reports:

```text
GET /evidence/{id}/report
GET /cases/{id}/report
```

---

# 39. OFFLINE DATA CONTRACT

The local application must be capable of producing valid records without the API.

Every locally generated object receives:

```text
local_id
global_id
device_id
created_at
updated_at
sync_status
```

Example:

```text
EV-LOCAL-ABC123
```

When synchronized, the server associates it with the authoritative global record.

---

# 40. CONFLICT HANDLING

Never automatically overwrite evidence.

If two devices have conflicting state:

```text
CONFLICT DETECTED

Evidence:
EV-2026-000001

Action:
MANUAL REVIEW REQUIRED
```

For custody events, append both valid events where possible.

For immutable evidence content, a conflict must never silently replace the original.

---

# 41. UI DESIGN SYSTEM

The product should feel like a serious cybersecurity/trust platform.

## Visual direction

Dark primary interface.

Use:

* deep charcoal/black backgrounds;
* subtle glass surfaces;
* restrained neon/technical accents;
* high-contrast verification states;
* fine grid/particle textures where appropriate;
* subtle gradients;
* thin borders;
* cryptographic/fingerprint motifs.

Do not make it look like a stereotypical "hacker movie" dashboard.

It should communicate:

**Trust + Security + Evidence + Precision.**

---

# 42. ANIMATION LANGUAGE

Animations should communicate system state.

### Collection

```text
COLLECTING
→ HASHING
→ SIGNING
→ SEALING
→ VERIFIED
```

### Synchronization

Evidence icon moves from:

```text
LOCAL
     ↓
SYNC
     ↓
CLOUD
```

### Verification

Fingerprint scanning animation.

### Integrity failure

Subtle red structural break/glitch effect.

### Successful verification

Controlled green/white confirmation.

Animations must never slow down actual workflows.

---

# 43. DASHBOARD VISUAL LANGUAGE

Primary cards:

```text
CASES
12

EVIDENCE
438

VERIFIED
421

PENDING SYNC
7

INTEGRITY ALERTS
2
```

Then:

### Integrity Monitor

```text
SYSTEM INTEGRITY

Evidence        100%
Custody         100%
Synchronization  94%
Audit           100%
```

---

# 44. LANDING / LOGIN

Minimal.

Logo:

**◈ VeriChain**

Tagline:

> **Don't just store evidence. Prove its history.**

Login.

Subtle cryptographic animation in the background.

No excessive text.

---

# 45. SECURITY UX

Never display cryptographic material in ways that confuse normal users.

Default:

```text
Integrity:
✓ Verified
```

Advanced:

```text
SHA-256:
8a7f9d...
Manifest:
VALID
Signature:
VALID
Chain:
VALID
```

This satisfies both judges and technical users.

---

# 46. DEMO DATA

Use only synthetic data.

The H1 rules explicitly prohibit real personal data and require synthetic, simulated or properly anonymized data.

Create:

### Case

RCN Digital Fraud Investigation

### Evidence

1. CCTV video
2. Screenshot
3. Transaction CSV
4. Chat export
5. Server log

No real victim information.

---

# 47. THE PRIMARY DEMONSTRATION

The entire competition demo should follow one coherent story.

## STEP 1

Create:

**RCN Digital Fraud Investigation**

---

## STEP 2

Collect CCTV evidence.

System:

```text
Evidence collected
Fingerprint generated
Manifest signed
Local copy protected
Custody event recorded
```

---

## STEP 3

Disconnect internet.

Collect another evidence item.

System:

```text
OFFLINE MODE

Evidence secured locally.
Synchronization pending.
```

---

## STEP 4

Reconnect.

System:

```text
CONNECTION RESTORED

Synchronizing...

2 evidence items uploaded.

Server verification:
✓

SYNC COMPLETE
```

---

## STEP 5

Open evidence timeline.

Show every event.

---

## STEP 6

Share evidence with Reviewer.

---

## STEP 7

Reviewer verifies.

```text
✓ INTEGRITY VERIFIED
```

---

## STEP 8

Deliberately modify a copy.

Verify again.

```text
✗ INTEGRITY FAILURE
```

---

## STEP 9

Demonstrate custody tampering.

Modify a simulated custody record.

Run chain verification.

```text
✗ CUSTODY CHAIN BROKEN
```

---

## STEP 10

Generate judge-friendly report.

Show:

```text
VERIFIED
```

and explain exactly what that means.

---

# 48. THE FIVE QUESTIONS WE MUST ANSWER BEFORE THE JUDGES ASK

## "What makes this different from cloud storage?"

**Answer:**

> Cloud storage stores files. VeriChain records and verifies the evidence's provenance, cryptographic identity and chain of custody.

---

## "Why blockchain?"

**Answer:**

> Blockchain is unnecessary for our core requirement. A cryptographically linked custody chain gives us the tamper-evident property required by the challenge without unnecessary infrastructure.

The challenge itself says a blockchain is not required.

---

## "What happens without internet?"

**Answer:**

> Evidence collection continues locally. Hashes, manifests and custody events are created locally and synchronization occurs when connectivity returns.

---

## "What if the computer is compromised?"

**Answer:**

> VeriChain does not claim to make a fully compromised endpoint trustworthy. It uses encrypted local storage, secure key handling, cryptographic fingerprints, signed manifests, tamper-evident custody records and independent server synchronization to provide defence in depth and detect integrity failures.

---

## "Does the hash prove the evidence is genuine?"

**Answer:**

> No. It proves that the examined file matches the file fingerprint recorded at collection. It does not prove that the underlying real-world event was truthful or that the source device itself was uncompromised.

---

# 49. CRITICAL DESIGN DECISIONS

These are now locked.

### Decision 1

**Online-first, offline-capable.**

Not local-only.

---

### Decision 2

**Original evidence is immutable within the application.**

---

### Decision 3

**Original metadata is preserved.**

Privacy sanitization creates derivatives.

---

### Decision 4

**SHA-256 identifies file content.**

---

### Decision 5

**Digital signatures protect manifests/custody records where implemented.**

---

### Decision 6

**Hash-chained custody records make history tamper-evident.**

---

### Decision 7

**Local evidence is encrypted.**

---

### Decision 8

**Keys are not stored in source code or ordinary configuration.**

---

### Decision 9

**Server independently verifies uploaded evidence.**

---

### Decision 10

**Offline synchronization is idempotent and resumable.**

---

### Decision 11

**No silent rewriting of evidence history.**

---

### Decision 12

**The system reports limitations honestly.**

---

# 50. REPOSITORY STRUCTURE

```text
verichain/
│
├── apps/
│   │
│   ├── desktop/
│   │   ├── src/
│   │   │   ├── components/
│   │   │   ├── pages/
│   │   │   ├── features/
│   │   │   │   ├── auth/
│   │   │   │   ├── cases/
│   │   │   │   ├── evidence/
│   │   │   │   ├── custody/
│   │   │   │   ├── verification/
│   │   │   │   ├── sharing/
│   │   │   │   ├── derivatives/
│   │   │   │   └── sync/
│   │   │   ├── services/
│   │   │   ├── stores/
│   │   │   ├── types/
│   │   │   └── utils/
│   │   │
│   │   └── src-tauri/
│   │       ├── commands/
│   │       ├── crypto/
│   │       ├── storage/
│   │       ├── database/
│   │       └── sync/
│   │
│   ├── web/
│   │   └── src/
│   │
│   └── api/
│       ├── app/
│       │   ├── api/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   ├── security/
│       │   ├── storage/
│       │   └── verification/
│       └── tests/
│
├── packages/
│   ├── types/
│   ├── ui/
│   └── crypto-contracts/
│
├── docs/
│   ├── architecture.md
│   ├── threat-model.md
│   ├── crypto-model.md
│   ├── evidence-lifecycle.md
│   └── api.md
│
├── docker/
│
└── README.md
```

---

# 51. COPILOT MASTER CONTEXT

Give the coder this context before implementation.

```text
You are implementing VeriChain, a serious prototype digital evidence collection,
integrity and chain-of-custody platform.

The product is online-first but offline-capable.

The system must preserve original evidence, generate a SHA-256 fingerprint at
collection, create a signed/canonical evidence manifest, protect locally stored
evidence, maintain a tamper-evident hash-chained custody trail, synchronize with
a central server when online, continue collecting while offline, support controlled
sharing, support derivative evidence without modifying originals, independently
verify evidence integrity, and generate a judge-readable evidence report.

Do not build a generic file-storage application.

Do not implement blockchain.

Do not invent cryptographic algorithms.

Do not hard-code secrets.

Do not store encryption keys in source code.

Do not modify original evidence.

Do not silently overwrite custody events.

Do not assume internet connectivity.

Do not make security claims that cannot be technically demonstrated.

Use mature cryptographic libraries.

Treat evidence content, manifests and custody history as security-sensitive.

Build cleanly, modularly and with strong typing.

The UI must be polished, modern, technical and visually impressive without becoming
a gimmicky hacker interface.

The application must be demonstrable end-to-end using synthetic evidence.
```

---

# 52. COPILOT IMPLEMENTATION ORDER

Do not ask Copilot to build everything simultaneously.

Implement in this order:

```text
1. Project foundation
2. Authentication
3. Case management
4. Evidence model
5. Evidence collection
6. SHA-256 fingerprinting
7. Manifest generation
8. Local protected vault
9. Custody chain
10. Evidence verification
11. Backend API
12. Server evidence storage
13. Client-server synchronization
14. Offline queue
15. Sharing
16. Derivatives
17. Reports
18. Audit/security events
19. UI polish
20. Full end-to-end testing
```

Each stage must compile and remain runnable before moving to the next.

---

# 53. FIRST CODER PROMPT

```text
Build the initial VeriChain application foundation.

Requirements:

- Monorepo structure.
- React + TypeScript frontend.
- Tauri desktop application.
- Rust backend layer.
- FastAPI backend service.
- PostgreSQL server database.
- SQLite local database.
- Shared TypeScript types where practical.
- Environment-based configuration.
- No secrets committed to source.
- Docker configuration for backend and PostgreSQL.
- Clean development README.
- Authentication foundation.
- Modern dark cybersecurity/trust-oriented UI.

Create the initial application shell with:

- Login
- Dashboard
- Cases
- Evidence
- Verification
- Sharing
- Reports
- Settings

At this stage, prioritize clean architecture and working navigation.

Do not implement fake security functionality.

Do not claim encryption/signatures are implemented until they actually are.

Create interfaces/placeholders for:

EvidenceService
HashService
CryptoService
VaultService
CustodyService
SyncService
VerificationService
ReportService

The application must run successfully after this task.
```

---

# 54. SECOND CODER PROMPT — EVIDENCE ENGINE

```text
Implement the VeriChain Evidence Collection Engine.

Requirements:

1. Create Case.
2. Select Case.
3. Import an evidence file.
4. Generate unique Evidence ID.
5. Read file metadata.
6. Calculate SHA-256.
7. Preserve the original file.
8. Create Evidence Manifest.
9. Store evidence metadata in SQLite.
10. Create initial custody event.
11. Display collection progress.
12. Display final integrity status.

The original evidence must never be modified.

Do not strip metadata from the original.

The Evidence record must include:

- evidence_id
- case_id
- original_filename
- MIME type
- size
- SHA-256
- collector
- source
- description
- collection timestamp
- status

Add unit tests for hashing and evidence creation.

Do not proceed to cloud synchronization yet.
```

---

# 55. THIRD CODER PROMPT — CUSTODY ENGINE

```text
Implement the VeriChain Chain-of-Custody Engine.

Every material evidence action must create a custody event.

Each event must contain:

- event ID
- evidence ID
- actor
- action
- timestamp
- details
- previous event hash
- current event hash

Use canonical serialization before calculating event hashes.

The first event has no previous event hash.

Every subsequent event must include the previous event hash.

Implement:

- create event
- retrieve timeline
- verify entire chain
- detect broken chain

Create a test that deliberately modifies an event and proves that verification fails.

Do not use blockchain.
```

---

# 56. FOURTH CODER PROMPT — PROTECTED VAULT

```text
Implement the VeriChain local evidence vault.

Requirements:

- Original evidence must be protected at rest.
- Use authenticated encryption with a mature cryptographic library.
- Do not implement custom cryptography.
- Do not hard-code encryption keys.
- Do not store plaintext keys in config files.
- Use OS secure key storage where practical.
- Separate key-management logic from evidence storage.
- Provide secure encrypt/decrypt APIs to the application.
- The UI must never directly manipulate protected evidence files.

Implement:

VaultService.store()
VaultService.retrieve()
VaultService.delete()
VaultService.exists()

Add tests for:

- successful encryption/decryption
- wrong key failure
- corrupted ciphertext failure
- evidence hash remaining identical after encrypt/decrypt

Document the security limitations clearly.
```

---

# 57. FIFTH CODER PROMPT — ONLINE SYNCHRONIZATION

```text
Implement VeriChain client-server synchronization.

Requirements:

- Desktop remains fully usable offline.
- Local evidence operations must never require the API.
- Every pending operation gets an idempotency ID.
- Sync queue stored in SQLite.
- Retry failed operations.
- Do not duplicate evidence.
- Server independently recalculates uploaded evidence hash.
- Server compares the received hash against the manifest.
- Server validates the manifest.
- Server records successful synchronization.
- Server rejects integrity mismatches.

Implement:

- sync queue
- upload initialization
- upload completion
- retry
- status tracking
- online/offline detection
- server verification

Create tests for:

1. successful sync
2. duplicate sync request
3. interrupted sync
4. integrity mismatch
5. server unavailable
```

---

# 58. SIXTH CODER PROMPT — SHARING

```text
Implement controlled VeriChain evidence sharing.

Users must be able to create a share for an evidence item.

A share contains:

- evidence ID
- sender
- recipient
- permissions
- creation timestamp
- expiration
- status

Permissions:

VIEW
DOWNLOAD
CREATE_DERIVATIVE
RESHARE

Every share action must create an audit/custody event.

The recipient must not gain access to evidence outside the assigned permissions.

Implement share revocation.

Implement expiration.

Implement verification before access.

Do not modify the original evidence.
```

---

# 59. SEVENTH CODER PROMPT — DERIVATIVES

```text
Implement controlled evidence derivatives.

The user must be able to create a derivative from an original evidence item.

The original evidence must remain untouched.

A derivative must have:

- unique ID
- parent evidence ID
- new SHA-256
- creator
- timestamp
- reason
- transformation description

The UI must clearly show:

ORIGINAL
and
DERIVATIVE

A derivative must never replace its parent.

Create an example sanitization workflow for supported image/document metadata.

Record the derivative creation in the custody chain.
```

---

# 60. EIGHTH CODER PROMPT — VERIFICATION

```text
Build the primary VeriChain Evidence Verification experience.

The user should be able to verify an evidence item or supplied evidence package.

Verification must check:

1. File SHA-256
2. Manifest
3. Manifest signature if implemented
4. Custody chain
5. Server record where available

Successful result:

INTEGRITY VERIFIED

Failure:

INTEGRITY FAILURE

Display a plain-language explanation.

Provide an expandable Technical Details section.

Create a deliberate modification test.

The demo must visibly prove that changing one supplied evidence file results in verification failure.
```

---

# 61. NINTH CODER PROMPT — REPORTING

```text
Build the VeriChain Digital Evidence Integrity Report.

The report must be understandable by a judge, magistrate or non-technical reviewer.

Include:

- Case
- Evidence ID
- Description
- Collector
- Collection timestamp
- Original filename
- Evidence type
- SHA-256
- Custody summary
- Verification status
- Signature status
- Server synchronization status
- Integrity conclusion
- Plain-language explanation

If verification fails, clearly state that integrity could not be established.

Do not hide technical failures.

Provide a clean printable/exportable layout.
```

---

# 62. TENTH CODER PROMPT — FINAL UI

```text
Polish VeriChain into a competition-quality cybersecurity product.

Design language:

- premium
- dark
- technical
- trustworthy
- minimal
- modern
- animated
- responsive

Use subtle visual concepts around:

- fingerprints
- cryptographic chains
- locks
- verification
- synchronization
- secure vaults

Do not use excessive hacker clichés.

Important screens:

1. Login
2. Dashboard
3. Case list
4. Case detail
5. Evidence collector
6. Evidence detail
7. Evidence timeline
8. Verification
9. Integrity failure
10. Sharing
11. Sync center
12. Reports
13. Security/audit

Use meaningful animations that communicate system state.

Make successful verification visually satisfying.

Make integrity failure immediately understandable.

Do not sacrifice usability for animation.
```

---

# 63. ACCEPTANCE TESTS

The prototype is not complete until these scenarios work.

## Test A — Normal Collection

```text
Create case
→ collect evidence
→ hash
→ seal
→ store
→ view
→ verify
```

Expected:

```text
PASS
```

---

## Test B — Offline Collection

```text
Disable internet
→ collect evidence
→ hash
→ seal
→ create custody
→ queue sync
```

Expected:

```text
PASS
Pending synchronization
```

---

## Test C — Reconnection

```text
Reconnect internet
→ synchronize
→ server verifies
```

Expected:

```text
PASS
```

---

## Test D — Evidence Modification

```text
Collect evidence
→ make a copy
→ modify copy
→ verify
```

Expected:

```text
INTEGRITY FAILURE
```

---

## Test E — Custody Modification

```text
Create custody events
→ modify an old event
→ verify chain
```

Expected:

```text
CUSTODY CHAIN FAILURE
```

---

## Test F — Sharing

```text
Create share
→ recipient opens
→ recipient verifies
→ access recorded
```

Expected:

```text
PASS
```

---

## Test G — Derivative

```text
Original
→ create sanitized derivative
→ calculate new hash
→ verify parent relationship
```

Expected:

```text
PASS
Original unchanged
```

---

## Test H — Server Integrity

```text
Client hash
≠
Server calculated hash
```

Expected:

```text
UPLOAD REJECTED
INTEGRITY ALERT
```

---

# 64. FINAL DEMO SCRIPT

The presenter should say:

> "Digital evidence is increasingly central to cybercrime investigations, fraud cases and disciplinary proceedings. But a file being present in a folder doesn't tell us whether it has been changed or who handled it."

Show the dashboard.

> "VeriChain begins establishing trust at collection."

Collect evidence.

Show:

**Fingerprint generated.**

**Evidence sealed.**

Disconnect internet.

> "The field investigator doesn't need connectivity to preserve evidence."

Collect another item.

Show:

**Offline — synchronization pending.**

Reconnect.

Show:

**Synchronization complete.**

Open timeline.

> "Every significant action becomes part of the evidence history."

Show custody chain.

Share evidence.

Then modify a copy.

Verify.

Show:

# INTEGRITY FAILURE

Then say:

> "We deliberately changed the file. VeriChain detected that it no longer matches the fingerprint recorded at collection."

Generate report.

> "And because the final audience may not be a security engineer, the system translates the technical verification into a report a decision-maker can understand."

Finish:

# DON'T JUST STORE EVIDENCE.

# PROVE ITS HISTORY.

---

# 65. WHAT WE ARE NOT BUILDING

Explicitly keep these out of the core prototype:

* Blockchain
* Cryptocurrency
* AI-generated forensic conclusions
* Facial recognition
* Full mobile forensic extraction
* Full operating-system forensic imaging
* Automated attribution
* Automatic determination of guilt
* Commercial-scale multi-region infrastructure
* Hardware HSM deployment
* Complex PKI infrastructure
* Unnecessary third-party integrations

These can appear under **future work**, not MVP.

---

# 66. FUTURE ROADMAP

After the prototype:

### Phase 2

* mobile collector;
* stronger device identity;
* advanced key management;
* hardware-backed keys;
* enterprise object storage;
* advanced role management;
* organizational federation.

### Phase 3

* forensic acquisition integrations;
* trusted timestamping;
* institutional archival;
* cross-organization evidence transfer;
* advanced evidence analytics.

### Phase 4

* integration with investigative/case-management systems;
* national/institutional deployment;
* specialized forensic workflows.

The prototype should demonstrate that the architecture can evolve toward these capabilities without pretending they already exist.

---

# 67. FINAL PRODUCT POSITIONING

VeriChain is not:

> "A secure Google Drive."

It is not:

> "A hashing application."

It is not:

> "A blockchain evidence system."

It is:

> **An evidence trust layer.**

The platform answers five fundamental questions:

### WHAT?

What evidence was collected?

### WHEN?

When was it collected?

### WHO?

Who collected and handled it?

### WHAT HAPPENED?

What happened to it throughout its lifecycle?

### HAS IT CHANGED?

Can we cryptographically verify that the evidence remains consistent with the record established at collection?

That is the product.

---

# 68. THE FINAL ARCHITECTURAL PRINCIPLE

Everything revolves around this:

```text
                    EVIDENCE
                       │
                       ▼
                 COLLECTION
                       │
                       ▼
                CRYPTOGRAPHIC
                  FINGERPRINT
                       │
                       ▼
                  MANIFEST
                       │
                       ▼
                  SIGNATURE
                       │
                       ▼
              PROTECTED LOCAL VAULT
                       │
              ┌────────┴────────┐
              │                 │
           OFFLINE            ONLINE
              │                 │
        LOCAL CUSTODY       SERVER SYNC
              │                 │
              └────────┬────────┘
                       │
                       ▼
                REMOTE RECORD
                       │
                       ▼
                 CONTROLLED
                   SHARING
                       │
                       ▼
                  VERIFICATION
                       │
                 ┌─────┴─────┐
                 │           │
              VERIFIED     FAILED
                 │           │
                 ▼           ▼
              REPORT      ALERT
```

**That is VeriChain.**

And that is the specification I would hand to the coder now. The H1 challenge says the problem and constraints are defined but the solution is up to the team; our job is to demonstrate a working prototype rather than attempt a finished commercial system.

The implementation should therefore start from the **Evidence Collection → Cryptographic Sealing → Custody Chain → Offline Queue → Server Synchronization → Verification** path, because that is the backbone on which every other feature depends.
