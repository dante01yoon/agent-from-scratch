def create_order(items):
    # TODO: 재고가 부족하면 주문을 막기
    return {"items": items, "status": "created"}


def cancel_order(order):
    # TODO: 취소 사유를 기록하기
    order["status"] = "cancelled"
    return order
