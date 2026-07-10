"""Tests for client-side cryptographic key and stream cipher helpers."""
import base64

from client.crypto import CryptoManager


def test_derive_key_returns_base64_encoded_32_byte_key():
    key = CryptoManager.derive_key("password123", "mario")

    decoded_key = base64.b64decode(key)

    assert len(decoded_key) == 32


def test_derive_key_is_deterministic_for_same_credentials():
    first_key = CryptoManager.derive_key("password123", "mario")
    second_key = CryptoManager.derive_key("password123", "mario")

    assert first_key == second_key


def test_derive_key_changes_when_username_changes():
    mario_key = CryptoManager.derive_key("password123", "mario")
    luigi_key = CryptoManager.derive_key("password123", "luigi")

    assert mario_key != luigi_key


def test_derive_key_changes_when_password_changes():
    old_key = CryptoManager.derive_key("password123", "mario")
    new_key = CryptoManager.derive_key("new-password", "mario")

    assert old_key != new_key


def test_stream_cipher_can_encrypt_and_decrypt_payload():
    key = CryptoManager.derive_key("password123", "mario")
    payload = b"secret chunk bytes"

    encryptor = CryptoManager.get_stream_cipher(key, "file_0.chunk").encryptor()
    ciphertext = encryptor.update(payload) + encryptor.finalize()

    decryptor = CryptoManager.get_stream_cipher(key, "file_0.chunk").decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    assert ciphertext != payload
    assert plaintext == payload


def test_stream_cipher_uses_different_nonce_per_chunk_filename():
    key = CryptoManager.derive_key("password123", "mario")
    payload = b"same plaintext"

    first_encryptor = CryptoManager.get_stream_cipher(key, "file_0.chunk").encryptor()
    second_encryptor = CryptoManager.get_stream_cipher(key, "file_1.chunk").encryptor()

    first_ciphertext = first_encryptor.update(payload) + first_encryptor.finalize()
    second_ciphertext = second_encryptor.update(payload) + second_encryptor.finalize()

    assert first_ciphertext != second_ciphertext
