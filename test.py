import hashlib
import base64
import secrets

def generate_code_verifier():
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('ascii')

def generate_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')

code_verifier = generate_code_verifier()
code_challenge = generate_code_challenge(code_verifier)

print("code_verifier:", code_verifier)
print("code_challenge:", code_challenge)