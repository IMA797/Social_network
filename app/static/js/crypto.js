//Перевод из байт в текст
function bufferToBase64(buffer) {
    //Превращение данных в массив байт
    const bytes = new Uint8Array(buffer);
    let binary = '';
    //Проходимся по каждому байту
    for (let i = 0; i < bytes.byteLength; i++) {
        //Превращаем число в байт
        binary += String.fromCharCode(bytes[i]);
    }
    //btoa - Binary to Ascii
    return btoa(binary);
}

//Перевод из текста в байты 
function base64ToBuffer(base64) {
    //Кодируем: atob - Ascii to Binary
    const binary = atob(base64);
    //Массив байт
    const bytes = new Uint8Array(binary.length);
    //Проходимся по каждому символу и превращаем его в байты
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}


async function generateKeyPair() {
    //Генерируем ключи по Диффи-Хеллману на кривой Р_256
    //Первый аргумент - название, второй - можно или нельзя сохранять ключи, третий: deriveKey - ключ можно использоваь для создания другого ключа, deriveBits - можно получить общий секрет
    const keyPair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" },
        true, ["deriveKey", "deriveBits"]
    );
    //Сгенерированные публичный и приватные ключи через встроенный в браузер инструмент для шифрования (crypto.subtle -) экспортируемм в разные форматы
    //Говоря проще, превращаем их в бинарные данные
    const exportedPublic = await crypto.subtle.exportKey("spki", keyPair.publicKey);
    const exportedPrivate = await crypto.subtle.exportKey("pkcs8", keyPair.privateKey);
    //keyPair - это структура, которая хранит публичные и приватные ключи
    return {
        publicKey: bufferToBase64(exportedPublic),
        privateKey: bufferToBase64(exportedPrivate),
        keyPair: keyPair
    };
}

async function importPublicKey(publicKeyBase64) {
    return await crypto.subtle.importKey(
        "spki", //Формат ключа
        base64ToBuffer(publicKeyBase64), //переводим в байты
        { name: "ECDH", namedCurve: "P-256" }, //Говорим как получили данные
        true, [] //Разрешвем потом экспортировать этот ключ обратно в текст
    );
}

//Аналогично функции выше, только для приватного ключа
async function importPrivateKey(privateKeyBase64) {
    return await crypto.subtle.importKey(
        "pkcs8",
        base64ToBuffer(privateKeyBase64), { name: "ECDH", namedCurve: "P-256" },
        true, ["deriveKey", "deriveBits"]
    );
}

//Вычисляем общий AES-ключ для шифрования сообщений
async function deriveAesKey(myPrivateKey, peerPublicKey) {
    //Получаем общий секрет через приватный ключ и ключ собеседника (32 байта)
    const sharedBits = await crypto.subtle.deriveBits({ name: "ECDH", public: peerPublicKey },
        myPrivateKey,
        256
    );

    //Превращаем общий секрет в ключ для AES-256
    return await crypto.subtle.importKey(
        "raw", //байты
        sharedBits, //Сам общий секрет
        { name: "AES-GCM" }, //говрим что сделать: aes-ключ
        false, //можно ли как-то получить ключ - нет
        ["encrypt", "decrypt"] //Этот ключ будет шифровать и расшифровывать (функции ниже)
    );
}

async function encryptMessage(aesKey, message) {
    //Превращаем текст в числа
    const encoder = new TextEncoder();
    //Превращаем полученные числа в массив чисел
    const data = encoder.encode(message);
    //Случайный набор 12 байт, благодаря которому одинаковые сообщения шифруются по-разному
    const iv = crypto.getRandomValues(new Uint8Array(12));
    //Шифруем сообщение с AES-ключом и с любым числом из iv
    const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv: iv },
        aesKey,
        data
    );

    return {
        ciphertext: bufferToBase64(encrypted),
        iv: bufferToBase64(iv)
    };
}

async function decryptMessage(aesKey, encryptedData) {
    //Превращаем текст в массив чисел
    const ciphertext = base64ToBuffer(encryptedData.ciphertext);
    //Превращаем в массив чисел iv
    const iv = base64ToBuffer(encryptedData.iv);
    //Расшифровываем сообщение, используя ключ и iv
    const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv: iv },
        aesKey,
        ciphertext
    );
    //Возвращаем числа из массива в текст
    return new TextDecoder().decode(decrypted);
}