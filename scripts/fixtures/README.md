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

`steam_password_change.error84.sanitized.html` is an error-only derivative of an
authenticated GET of `HelpChangePassword`, captured on 2026-10-20 at 17:46 UTC.
The response redirected to `/ru/wizard/HelpChangePassword` and returned HTTP 200
with `#error_description` and code 84 (temporary rate limit), without a wizard
continuation. The derivative retains the `page_error` wrapper that activates the
error display. The original response bytes remain outside Git. The reusable
read-only collector is `scripts/fetch_password_flow.py`; it takes an account
alias, its existing session file, and a private output directory. It replaces
saved routing with the current configured account route, verifies the Steam
Help cookie owner, performs no login or POST, and does not persist cookies.

`steam_password_change.continuation.sanitized.html` is a wrapper-and-link
derivative of a real authenticated wizard entry GET captured on 2026-10-20 at
18:04 UTC. The normal `page_content` wrapper contains an inactive generic
`error_description` template and a native Russian continuation link. Recovery
and account IDs are replaced with `REDACTED`. Merely finding the generic error
template does not indicate a failed page; an active error uses `page_error`.

The `steam_Ajax*.success.sanitized.json` derivatives were collected during one
authorized password change on 2026-10-20 at 18:06 UTC. They preserve the observed
boolean and error fields; navigation `hash` and `redirect` values are replaced
with `REDACTED`. Each file identifies its endpoint. Original response bytes are
retained privately outside Git. `steam_getrsakey.success.sanitized.json` retains
the public RSA key and timestamp; it contains no private key or password.
`tests/test_password_response_fixtures.py` checks these observed formats against
the Pydantic models and rejects ambiguous availability values. The fresh login,
not a navigation response alone, establishes the password change result.
