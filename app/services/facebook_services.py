import httpx

from app.core.config import FB_GRAPH_API_VERSION


class FacebookSendError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def send_facebook_text(
    *, page_id: str, access_token: str, recipient_id: str, text: str
) -> str:
    """Send a text message through Meta's Messenger Send API."""
    url = f"https://graph.facebook.com/{FB_GRAPH_API_VERSION}/{page_id}/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url, params={"access_token": access_token}, json=payload
            )
    except httpx.HTTPError as exc:
        raise FacebookSendError(502, f"Không thể kết nối Facebook: {exc}") from exc

    if response.is_error:
        try:
            error = response.json().get("error", {})
            detail = error.get("message") or response.text
        except ValueError:
            detail = response.text
        raise FacebookSendError(response.status_code, f"Facebook API: {detail}")

    try:
        result = response.json()
    except ValueError as exc:
        raise FacebookSendError(502, "Facebook trả về dữ liệu không hợp lệ") from exc

    message_id = result.get("message_id")
    if not message_id:
        raise FacebookSendError(502, "Facebook không trả về message_id")
    return message_id
