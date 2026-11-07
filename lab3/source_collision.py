# Простий калькулятор для лабораторної роботи №3

TAX_RATE = 20


def price_with_tax(price):
    """Повертає ціну з урахуванням податку."""
    return price + price * TAX_RATE / 100


def main():
    items = [100, 250, 75]
    total = sum(price_with_tax(p) for p in items)
    print("Разом до сплати:", total)


if __name__ == "__main__":
    main()   		
