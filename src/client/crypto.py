"""Cryptographic helpers for Zero-Knowledge encryption."""
import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

class CryptoManager:
    """Handles AES-256 key derivation and stream cipher creation."""
    
    @staticmethod
    def derive_key(password: str, username: str) -> str:
        """
        Derives a robust 256-bit (32-byte) AES key from the user's password.
        Uses the username as a deterministic salt for simplicity in this architecture.
        Returns the key as a base64 string for easy local storage.
        """
        salt = username.encode('utf-8').ljust(16, b'\0')[:16]
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))
        return base64.b64encode(key).decode('utf-8')

    @staticmethod
    def get_stream_cipher(base64_key: str, chunk_filename: str):
        """
        Creates an AES-256-CTR cipher for a specific chunk.
        CTR mode is perfect for streaming as it does not require block padding.
        We derive a unique 16-byte Nonce (IV) directly from the chunk filename.
        """
        key = base64.b64decode(base64_key)
        
        # Derive a unique 16-byte nonce for this specific chunk
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(chunk_filename.encode('utf-8'))
        nonce = digest.finalize()[:16] 
        
        return Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
