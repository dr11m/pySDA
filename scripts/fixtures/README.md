# Steam security response provenance

`steam_twofactor_manage.form.sanitized.html` is a **sanitized derivative**, not a
complete raw response. It contains only the deauthorization form extracted from
an authenticated HTTP 200 GET of
`https://store.steampowered.com/twofactor/manage`, captured on 2026-10-19 UTC.
The action URL is reduced to its path; sessionid is replaced with `REDACTED`;
all surrounding HTML, account data and other forms are removed. The original
response is retained privately outside Git.

Collection reused existing saved cookies through the configured account route.
It did not log in, refresh credentials, submit a form or revoke any sessions.
The fixture confirms the form method, endpoint and fields, not the result of
submitting it. There is no real successful destructive POST fixture.

Password response navigation (`hash` / `html`) was checked against Steam's own
public `help.js`, served from
`https://help.steampowered.com/en/public/javascript/help.js`.
Offline response bodies in tests are synthetic cases, not captured account
responses. Password changes still require a fresh credential login before
the entered password can be persisted.

`steam_password_change.link.sanitized.html` is a link-only derivative of the
authenticated `HelpChangePassword` wizard GET on 2026-10-20. Recovery session
and account IDs are replaced with `REDACTED`. The native continuation retains
`reset=1`, `lost=0`, `issueid=406`.

`steam_password_recovery.fields.sanitized.html` contains only the three hidden
mode fields of the public forgot-password entry GET
`https://help.steampowered.com/en/wizard/HelpWithLoginInfo?issueid=406`, collected
on the same date. It is a derivative, not the complete raw response. The private
diagnostic script `fetch_password_flow.py` recorded the original HTML outside Git.
No code was sent and no password-change or verification POST was submitted.
