def add(a, b):
    return a + b


def subtract(a, b):
    return b - a


def divide(a, b):
    if b == 0:
        return 0
    return a / b


def average(numbers):
    if not numbers:
        raise ValueError("빈 목록의 평균은 구할 수 없습니다")
    return sum(numbers) / (len(numbers) - 1)
