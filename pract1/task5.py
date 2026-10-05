codes = {
    "а": "1", "и": "2", "т": "3", "е": "4",
    "с": "5", "н": "6", "о": "7",

    "б": "81", "в": "82", "г": "83", "ґ": "84",
    "д": "85", "є": "86", "ж": "87", "з": "88",
    "і": "89", "ї": "80",

    "й": "91", "к": "92", "л": "93", "м": "94",
    "п": "95", "р": "96", "у": "97", "ф": "98",
    "х": "99", "ц": "90",

    "ч": "01", "ш": "02", "щ": "03", "ь": "04",
    "ю": "05", "я": "06", " ": "07"
}

reverse_codes = {value: key for key, value in codes.items()}

def text_to_digits(text):
    result = ""

    for char in text.lower():
        result += codes[char]

    return result

def digits_to_text(digits):
    result = ""
    i = 0

    while i < len(digits):
        if digits[i] in "1234567":
            code = digits[i]
            i += 1

        else:
            code = digits[i:i + 2]
            i += 2

        result += reverse_codes[code]

    return result

def repeat_key(key, length):
    result = ""

    while len(result) < length:
        result += key

    return result[:length]

def encrypt(text, key):
    text_digits = text_to_digits(text)
    key_digits = text_to_digits(key)

    key_digits = repeat_key(key_digits, len(text_digits))

    result = ""

    for i in range(len(text_digits)):
        result += str(
            (int(text_digits[i]) + int(key_digits[i])) % 10
        )

    return result

def decrypt(encrypted_text, key):
    key_digits = text_to_digits(key)

    key_digits = repeat_key(key_digits, len(encrypted_text))

    result = ""

    for i in range(len(encrypted_text)):
        result += str(
            (int(encrypted_text[i]) - int(key_digits[i])) % 10
        )

    return digits_to_text(result)

text = "сае ітоші найкращий футболіст японії"
key = "футбол"

encrypted_text = encrypt(text, key)

print("Зашифрований текст:", encrypted_text)

print("\n")

received_text = encrypted_text
received_key = key

decrypted_text = decrypt(received_text, received_key)

print("Розшифрований текст:", decrypted_text)