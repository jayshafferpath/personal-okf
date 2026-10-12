---
type: project
id: phimail-prototype
title: phimail-prototype
description: Polls the EMR Direct phiMail sandbox for Direct Secure Messages and stores them locally. A prototype for Epic referral intake.
owners: [human:jay.shaffer]
tags: [healthcare-interop, direct-messaging, prototype]
resource: https://github.com/jayshafferpath/phimail-prototype
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

- **Stack:** plain Node ESM over raw TLS sockets. The only dependency is dotenv.
- **Run:**
  - `npm start` polls for messages.
  - `npm run send-test-referral` sends a Referral Note.
  - `node src/sendReferral.js ccd` sends a CCD.
- **Protocol:** phiMail AUTH/CHECK/SHOW/DONE. The spec is `docs/epic_referral_intake_spec.md`, with example C-CDA XML alongside it.
- **Config:** there is no `.env.example`; the README lists the variables. They include `PHIMAIL_HOST`, `PHIMAIL_PORT`, `PHIMAIL_USERNAME`, `PHIMAIL_PASSWORD`, `PHIMAIL_TRUST_ANCHOR_PATH`, `POLL_INTERVAL_MS`, `DATA_DIR`, `TEST_REFERRAL_RECIPIENT` and `DOC_TYPE`.
- **Tests:** none.

## Gotchas

- `DONE` deletes the message on production accounts. The code sends it only after the message is on disk.
- Sandbox credentials never work in production. Never send PHI through the sandbox.
- The trust anchor cert has to be pulled manually from the phiMail SDK ZIP into `certs/`.
