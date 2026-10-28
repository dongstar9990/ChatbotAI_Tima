import httpx


ZALO_CONSULTATION_MESSAGE_URL = "https://openapi.zalo.me/v3.0/oa/message/cs"


class ZaloSendError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def send_zalo_text(
    *, access_token: str, recipient_id: str, text: str
) -> str:
    """Send a consultation text message through the Zalo OA API."""
    payload = {
        "recipient": {"user_id": recipient_id},
        "message": {"text": text},
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                ZALO_CONSULTATION_MESSAGE_URL,
                headers={
                    "access_token": access_token,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise ZaloSendError(502, f"Không thể kết nối Zalo: {exc}") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise ZaloSendError(502, "Zalo trả về dữ liệu không hợp lệ") from exc

    if response.is_error or result.get("error", 0) not in (0, None):
        detail = result.get("message") or response.text
        raise ZaloSendError(
            response.status_code if response.is_error else 502,
            f"Zalo API: {detail}",
        )

    message_id = result.get("data", {}).get("message_id")
    if not message_id:
        raise ZaloSendError(502, "Zalo không trả về message_id")
    return message_id
