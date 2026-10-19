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
