from orders.service import create_order, get_order

PORT = 4317


def start():
    # TODO: 포트 번호를 config 파일에서 읽기
    print(f"서버 시작: {PORT}")


def handle(request):
    if request["method"] == "POST":
        return create_order(request["body"])
    # TODO: 없는 주문이면 404 돌려주기
    return get_order(request["id"])
