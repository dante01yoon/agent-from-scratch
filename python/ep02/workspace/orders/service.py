ORDERS = {}


def create_order(body):
    # TODO: 수량이 0 이하면 거절하기
    order_id = len(ORDERS) + 1
    ORDERS[order_id] = body
    return {"id": order_id}


def get_order(order_id):
    return ORDERS.get(order_id)
