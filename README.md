<div align="center">

<img src="logos/icon logo.png" alt="VeriChain Logo" width="120" />

# VeriChain

### **Prove your digital evidence hasn't changed.**

Cryptographic digital evidence integrity and chain-of-custody platform for preserving, verifying, and securely sharing digital evidence — online or offline.

<br />

![Status](https://img.shields.io/badge/status-active_development-00C853?style=for-the-badge)
![Security](https://img.shields.io/badge/security-cryptographic-7C3AED?style=for-the-badge)
![Offline](https://img.shields.io/badge/offline-first-00A6FF?style=for-the-badge)
![Tests](https://img.shields.io/badge/tests-60%20passing-16A34A?style=for-the-badge)

<br /><br />

## 🧰 Technology Stack

### Frontend

![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge\&logo=react\&logoColor=111827)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge\&logo=typescript\&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge\&logo=vite\&logoColor=white)

### Backend

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge\&logo=python\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge\&logo=fastapi\&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge\&logo=sqlalchemy\&logoColor=white)

### Desktop

![Tauri](https://img.shields.io/badge/Tauri-FFC131?style=for-the-badge\&logo=tauri\&logoColor=111827)
![Rust](https://img.shields.io/badge/Rust-000000?style=for-the-badge\&logo=rust\&logoColor=white)

### Data & Storage

![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge\&logo=postgresql\&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge\&logo=sqlite\&logoColor=white)

### Cryptography & Security

![SHA-256](https://img.shields.io/badge/SHA--256-EF4444?style=for-the-badge)
![Ed25519](https://img.shields.io/badge/Ed25519-7C3AED?style=for-the-badge)
![AES-GCM](https://img.shields.io/badge/AES--GCM-059669?style=for-the-badge)

### Tooling

![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge\&logo=git\&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge\&logo=github\&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge\&logo=docker\&logoColor=white)

</div>

---

# 🔐 VeriChain

## **Digital evidence should not require blind trust.**

VeriChain is a cryptographic digital evidence integrity and chain-of-custody platform designed to help investigators, journalists, legal teams, security professionals, and organizations **collect, preserve, verify, and securely share digital evidence without losing trust in its history.**

From the moment evidence is collected, VeriChain establishes a cryptographic identity for the artifact and records its lifecycle through a tamper-evident custody chain.

> **The file is the evidence.
> The hash proves its identity.
> The custody chain proves its history.**

---

## ⚡ At a Glance

|     | Capability                  |                                      |
| --- | --------------------------- | ------------------------------------ |
| 🔐  | **Cryptographic Integrity** | SHA-256 evidence fingerprinting      |
| 🔏  | **Digital Signatures**      | Ed25519 signed manifests             |
| 🔗  | **Chain of Custody**        | Hash-linked append-only lifecycle    |
| 📴  | **Offline Collection**      | Secure local evidence vault          |
| 🔄  | **Synchronization**         | Offline → online recovery            |
| 👥  | **Secure Sharing**          | Permission-controlled access         |
| 🧬  | **Provenance**              | Cryptographically linked derivatives |
| 🛡️ | **Verification**            | Multi-layer integrity validation     |

---

# 🎯 The Problem

Digital evidence is easy to copy, alter, replace, rename, or redistribute.

A video can be edited.

A screenshot can be manipulated.

A document can be replaced.

And after an evidence file passes through several people or systems, answering **"what exactly happened to this file?"** can become difficult.

Traditional storage tells you where the file exists.

VeriChain is designed to answer a different question:

> ### **Can we demonstrate that the evidence we have now corresponds to the evidence that was originally collected, and can we show its recorded history?**

---

# 🧠 The VeriChain Model

```text
COLLECT
   │
   ▼
FINGERPRINT
   │
   ▼
MANIFEST
   │
   ▼
SIGN
   │
   ▼
SEAL
   │
   ▼
CUSTODY CHAIN
   │
   ├───────────────┐
   ▼               ▼
OFFLINE          ONLINE
VAULT            STORAGE
   │               │
   └───────┬───────┘
           ▼
        VERIFY
           │
           ▼
     TRUSTED RECORD
```

---

# 🔬 Security Architecture

VeriChain combines several independent integrity mechanisms:

```text
                  ┌──────────────────────┐
                  │    EVIDENCE BYTES    │
                  └──────────┬───────────┘
                             │
                             ▼
                       ┌───────────┐
                       │ SHA-256   │
                       └─────┬─────┘
                             │
                             ▼
                       ┌───────────┐
                       │ MANIFEST  │
                       └─────┬─────┘
                             │
                             ▼
                       ┌───────────┐
                       │ Ed25519   │
                       │ SIGNATURE │
                       └─────┬─────┘
                             │
                             ▼
                       ┌───────────┐
                       │  CUSTODY  │
                       │   CHAIN   │
                       └─────┬─────┘
                             │
                             ▼
                       ┌───────────┐
                       │PROVENANCE │
                       └─────┬─────┘
                             │
                             ▼
                         VERIFY
```

---

# 📴 Offline → Online

Connectivity should not determine whether evidence can be preserved.

VeriChain can collect and protect evidence locally before connectivity returns.

```text
┌─────────────┐
│   OFFLINE   │
└──────┬──────┘
       │
       ▼
   Collect
       │
       ▼
    SHA-256
       │
       ▼
   Sign + Seal
       │
       ▼
 Encrypted Vault
       │
       ▼
   Sync Queue
       │
       │ INTERNET RETURNS
       ▼
 Secure Synchronization
       │
       ▼
 Server Verification
```

---

# 🧬 Evidence Provenance

Original evidence remains distinct from derivatives.

```text
                   ORIGINAL
                      │
                 Evidence A
                      │
                ──────┴──────
                      │
                 DERIVATION
                ╱           ╲
               ▼             ▼
        Evidence B       Evidence C
        Screenshot       Redacted Copy
```

Every derivative receives its own cryptographic identity while retaining an explicit relationship to its parent.

---

# 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────┐
│                      VERICHAIN                          │
│                                                         │
│   React Web                  Tauri Desktop              │
│       │                           │                     │
│       └────────────┬──────────────┘                     │
│                    ▼                                    │
│               FastAPI API                               │
│                    │                                    │
│        ┌───────────┼────────────┐                       │
│        ▼           ▼            ▼                       │
│    Evidence     Security      Sync                      │
│    Services     Services     Services                    │
│        │           │            │                       │
│        └───────────┼────────────┘                       │
│                    ▼                                    │
│              Data / Storage                             │
│              ┌───────────┐                              │
│              │PostgreSQL │                              │
│              └───────────┘                              │
│                                                         │
│              Local Offline Layer                        │
│              ┌───────────┐                              │
│              │  SQLite   │                              │
│              │Encrypted  │                              │
│              │   Vault   │                              │
│              └───────────┘                              │
└─────────────────────────────────────────────────────────┘
```

---

# 📦 Project Structure

```text
verichain/
│
├── apps/
│   ├── api/                  # FastAPI backend
│   ├── web/                  # React web application
│   └── desktop/              # Tauri desktop application
│
├── packages/
│   ├── types/                # Shared TypeScript types
│   ├── ui/                   # Shared UI components
│   └── crypto-contracts/     # Cryptographic contracts
│
├── docs/
│   ├── architecture.md
│   ├── threat-model.md
│   ├── crypto-model.md
│   ├── evidence-lifecycle.md
│   └── api.md
│
├── docker/
├── logos/
│   └── icon-logo.png
│
├── IMPLEMENTATION_PLAN.md
├── VERICHAIN_SPEC.md
├── README.md
└── .env.example
```

---

# 🧪 Engineering Status

<div align="center">

| Validation            |            Result |
| --------------------- | ----------------: |
| Backend Tests         |   ✅ **60 passed** |
| Frontend Build        |     ✅ **Passing** |
| TypeScript            |     ✅ **Passing** |
| Secret Protection     |    ✅ **Verified** |
| Offline Evidence      | ✅ **Implemented** |
| Cryptographic Sealing | ✅ **Implemented** |
| Chain of Custody      | ✅ **Implemented** |
| Digital Signatures    | ✅ **Implemented** |
| Secure Sharing        | ✅ **Implemented** |
| Provenance            | ✅ **Implemented** |

</div>

---

# 🚧 Roadmap

```text
FOUNDATION
    │
    ├── Authentication
    ├── Evidence Core
    ├── Cryptographic Sealing
    ├── Chain of Custody
    ├── Digital Signatures
    ├── Offline Vault
    ├── Synchronization
    ├── Secure Sharing
    └── Provenance
             │
             ▼
       NEXT GENERATION
             │
             ├── Forensic Reports
             ├── Desktop Release
             ├── Production Key Management
             ├── Object Storage
             ├── Advanced Verification
             └── Production Hardening
```

---

# ⚠️ Security & Trust Boundary

VeriChain is designed to provide cryptographic evidence integrity and a verifiable record of recorded custody events.

It does **not** claim to prove that the underlying real-world event itself occurred.

For example:

```text
SHA-256 MATCH
      ≠
REAL-WORLD TRUTH
```

A matching fingerprint demonstrates that the current bytes correspond to the recorded fingerprint.

It does not independently establish the authenticity of the original source, the honesty of the collector, or the truthfulness of the event represented by the evidence.

VeriChain also does not claim to completely protect evidence against a fully compromised operating system, compromised source device, compromised signing keys, or physical destruction.

---

# 🤝 Development Principles

VeriChain follows several non-negotiable principles:

* **Original evidence is never silently modified.**
* **Evidence identity is immutable.**
* **Verification failures are never represented as successful verification.**
* **Custody history is append-only.**
* **Evidence sharing is authorization-controlled.**
* **Secrets and private keys never belong in Git.**
* **Established cryptographic libraries are preferred over custom cryptography.**
* **Offline collection must remain possible when connectivity is unavailable.**
* **Organization boundaries must be enforced server-side.**
* **Security-sensitive functionality must be tested.**

---

# 📜 License

License information will be added before the public release.

---

<div align="center">

<img src="logos/icon logo.png" alt="VeriChain" width="72" />

### **VERIFY THE FILE.**

### **VERIFY THE HISTORY.**

`COLLECT` · `HASH` · `SEAL` · `SIGN` · `PRESERVE` · `VERIFY`

<br />

**VeriChain — Digital Evidence Integrity Infrastructure**

</div>
