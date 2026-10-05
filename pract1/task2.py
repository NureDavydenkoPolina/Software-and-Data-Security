# Український алфавіт
ALPHABET = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"

def encrypt(text, key):
    result = ""
    key = key.upper()
    key_pos = 0

    for char in text:
        if char.upper() in ALPHABET:
            text_pos = ALPHABET.index(char.upper())

            key_pos_value = ALPHABET.index(key[key_pos % len(key)])

            new_pos = (text_pos + key_pos_value) % len(ALPHABET)

            new_char = ALPHABET[new_pos]

            if char.islower():
                new_char = new_char.lower()

            result += new_char
            key_pos += 1
        else:
            result += char

    return result


def decrypt(text, key):
    result = ""
    key = key.upper()
    key_pos = 0

    for char in text:
        if char.upper() in ALPHABET:
            text_pos = ALPHABET.index(char.upper())

            key_pos_value = ALPHABET.index(key[key_pos % len(key)])

            new_pos = (text_pos - key_pos_value) % len(ALPHABET)

            new_char = ALPHABET[new_pos]

            if char.islower():
                new_char = new_char.lower()

            result += new_char
            key_pos += 1
        else:
            result += char

    return result


# cipher_text = "Кгжирґоґжяю жбхнмяоочдць лглйч рьґькяріфю оїун'ьгкялць фюякзз кяфнїпцйн шьщсхн. Юзр кї рр зюлга янмлд, мр, ім яябмияойї ґгсіґґж їпяс йбаязрюс, лглйї авжсфямх мхлґшяґіюк зізаи. Щхрїкфґжє шьщс, м гжзґ ююмрююмфзлґе нйчвґжщяграч лпґьсркфзлґе щоґаґмчщомкфґкдм т лчлаоїь нжйкрїїмху шхґ."
cipher_text = "Зслматщиянч кщифтїгщащіц сюара аллгднмнпм хогв'жздніях зддччр рузйокіру жлєчмв. Члл яп ца чзсчо шуіаї, та, щч дупїмчгро нсянштґ окнш пкоилімн, сюаро йрпчлнїю іитижнлнтя днґон. Вддурлтґй улгч, щ сплш мчтлмдтґчциь взаьтлвїсюео алихечрґчциь ккиштуазгчрлтиіі є ташощос вґпздпощиб бмт."

# key = "ключ"
key = "задача"


# decrypted_text = decrypt(cipher_text, key)

# print("РОЗШИФРОВАНИЙ ТЕКСТ:", decrypted_text)

# print("\n")

# encrypted_again = encrypt(decrypted_text, key,)

# print("ПЕРЕВІРКА:", encrypted_again)