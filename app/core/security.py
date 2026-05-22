import hashlib
import hmac
import base64
import json
import logging
from typing import Optional
from Crypto.Cipher import AES
from app.core.config import settings
from app.core.exceptions import LarkSignatureVerificationError

class LarkDecryptor:
    def __init__(self, encrypt_key: str):
        # The key is SHA256 of the encrypt_key string
        self.key = hashlib.sha256(encrypt_key.encode('utf-8')).digest()

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypts AES-256-CBC encrypted payload from Lark Suite"""
        try:
            raw_data = base64.b64decode(encrypted_text)
            iv = raw_data[:16]
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(raw_data[16:])
            # Strip PKCS7 padding
            padding_len = decrypted[-1]
            decrypted = decrypted[:-padding_len]
            return decrypted.decode('utf-8')
        except Exception as e:
            logging.error(f"Lark payload decryption failed: {str(e)}")
            raise LarkSignatureVerificationError("Giải mã gói tin Lark Suite thất bại.")

def verify_lark_signature(timestamp: str, nonce: str, signature: str, body: str) -> bool:
    """
    Verifies that the webhook request is indeed from Lark Suite.
    Formula: signature = SHA256(timestamp + nonce + encrypt_key + body)
    """
    if not settings.LARK_ENCRYPT_KEY:
        # If no key is set, skip verification (useful for local development)
        return True
        
    try:
        # Concatenate signature components
        message = timestamp + nonce + settings.LARK_ENCRYPT_KEY + body
        computed = hashlib.sha256(message.encode('utf-8')).hexdigest()
        
        # Safe comparison of signatures
        return hmac.compare_digest(computed, signature)
    except Exception as e:
        logging.error(f"Error calculating Lark signature: {str(e)}")
        return False
