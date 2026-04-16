import base64
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

#Шифрование изображения, возвращаем зашифрованные данные и iv в формате Base64
def encrypt_image(image_bytes: bytes, key: bytes) -> tuple[str, str]:

    iv = os.urandom(16)  # 16 байт для AES
    
    #Добавляем padding, Выравниваение 
    #AES шифрует данные по 16 байт, и если последний блок неполный — нужно дополнить его
    #PKCS7 - стандарт выравнивания
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(image_bytes) + padder.finalize()
    
    #Создаем объект шифра
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    #Создаем объект для шифрования
    encryptor = cipher.encryptor()
    #Шифруем данные
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    
    return (
        base64.b64encode(encrypted).decode('utf-8'),
        base64.b64encode(iv).decode('utf-8')
    )

#Расшифровка изображения, возвращаем байты
def decrypt_image(encrypted_b64: str, iv_b64: str, key: bytes) -> bytes:

    #Превращаем строку и iv из base64 обратно в байты
    encrypted = base64.b64decode(encrypted_b64)
    iv = base64.b64decode(iv_b64)
    
    #Создаем объект для расшифровки, расшифровываемм данные
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted) + decryptor.finalize()
    
    #Создаем объект для удаления padding
    unpadder = padding.PKCS7(128).unpadder()
    #Удаляем pedding и завершаем операцию
    original_data = unpadder.update(padded_data) + unpadder.finalize()
    
    return original_data