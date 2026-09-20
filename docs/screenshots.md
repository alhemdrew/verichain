# VeriChain Demo Screenshots

These screenshots document the running VeriChain prototype using synthetic data only.

> All evidence used in this demonstration is synthetic and was created specifically for testing VeriChain's evidence-integrity and chain-of-custody workflows. No real personal data is used.

## Verified captures

| File | Demonstrates |
| --- | --- |
| [01-login-page.png](screenshots/01-login-page.png) | Secure access screen with the VeriChain identity. |
| [02-dashboard.png](screenshots/02-dashboard.png) | Authenticated investigator workspace, case/evidence counters, and local-only status. |
| [03-case-created.png](screenshots/03-case-created.png) | Synthetic case inventory with organization-scoped case numbering. |
| [04-evidence-upload.png](screenshots/04-evidence-upload.png) | Evidence registration surface with visible preservation workflow and evidence list. |
| [05-evidence-detail.png](screenshots/05-evidence-detail.png) | Evidence workspace with real sealed, verified, and pending records visible together. |
| [06-verification.png](screenshots/06-verification.png) | Presented-file verification surface with a registered evidence selector and explicit awaiting state. |
| [08-sharing-controls.png](screenshots/08-sharing-controls.png) | Permissioned sharing controls, recipient lookup, expiry, and email-send action. |
| [09-reports-page.png](screenshots/09-reports-page.png) | In-app report view showing the verified status and download actions. |
| [10-settings-profile.png](screenshots/10-settings-profile.png) | Investigator profile, account, retention, and synchronization controls. |
| [13-summary-report.png](screenshots/13-summary-report.png) | Rasterized first page of the generated executive report. |
| [14-detailed-report.png](screenshots/14-detailed-report.png) | Rasterized first page of the generated detailed technical report. |

The complete local capture set is stored in `~/VeriChain-Screenshots`, organized by workflow area. It includes login, dashboard, cases, evidence, verification, sharing, reports, settings, and responsive captures. The repository includes the strongest reviewed desktop views; the mobile capture remains local because its current viewport exposes a navigation overflow that should be corrected before publishing.

## Workflow evidence

The live synthetic run created case `CASE-0001`, uploaded `verichain-synthetic.txt`, sealed it with SHA-256, created and verified an Ed25519 signature, created a derivative with provenance, and synchronized the original without changing its identity.

A modified copy was compared against the original and returned `NO MATCH`. The original SHA-256 remained unchanged. The generated summary PDF was two pages and the detailed PDF was three pages; both were rasterized and visually reviewed for clipping and overlap.

## Important limitations

- The capture set does not claim that an email was delivered: SMTP credentials were intentionally not configured in this local environment.
- Windows packaging was not tested because this Linux environment does not include a Windows build environment and the Tauri directory is currently a scaffold.
- Screenshots show application state and workflow evidence; they are not independent proof that an underlying real-world event occurred.
- Processing and failure-state captures should be refreshed from a browser session that triggers those exact states before a public presentation. No screenshot here is fabricated to represent a state that was not observed.
