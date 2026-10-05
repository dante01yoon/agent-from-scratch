def pay(order, amount):
    # TODO: 결제가 실패하면 재시도하기
    return {"order": order, "amount": amount, "paid": True}
