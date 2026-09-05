"""Run once: python3 gen_vapid_keys.py  (needs: pip install cryptography)"""
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

key = ec.generate_private_key(ec.SECP256R1())
priv = key.private_numbers().private_value.to_bytes(32, "big")
pub = key.public_key().public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
print("VAPID_PRIVATE_KEY=" + b64(priv))
print("VAPID_PUBLIC_KEY=" + b64(pub))
