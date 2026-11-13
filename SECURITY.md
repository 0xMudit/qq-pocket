# Security and beta use

Passwords use Argon2 via pwdlib. Session/API/device tokens are random, stored as SHA-256 digests, and revocable. Hosted browser cookies are HttpOnly, SameSite=Lax and Secure on HTTPS. Origin checks guard cookie-authenticated mutations. Account ownership is enforced in service queries. Public demo accounts are intentionally shared and must contain only synthetic data.

No card details are accepted. Real GPS data belongs only in a private account with the device owner's permission. Never publish database credentials or personal location history in issues. Use a private channel to report sensitive vulnerabilities. This beta has not had an independent security audit and does not implement account recovery, MFA, or enterprise access controls.
