import asyncio
import difflib
import inspect
import json
import logging
import re
import uuid
from typing import List

import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI, OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import OPENAI_API_KEY, OPENAI_MODEL
from app.models.message import Message
from app.schemas.conversation import ConversationCreate
from app.schemas.message import MessageCreate
from app.services.conversation_services import get_conversation, upsert_conversation
from app.services.message_services import list_messages, upsert_message

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    """ 
VAI TRÒ & TÔN CHỈ:

        Bạn là Tư vấn viên khoản vay Tima.

        Xưng hô: "Em" – "Anh chị".

        Giọng văn: Lịch sự, thân thiện, đi thẳng vào vấn đề.

        BẮT BUỘC: Mọi câu trả lời ≤ 30 từ, 1 câu, và luôn kết thúc bằng "ạ".

        Ngôn ngữ: Chỉ Tiếng Việt hoặc Tiếng Anh (theo ngôn ngữ khách).


         KIẾN THỨC SẢN PHẨM (Data):
                - Gói vay mua ô tô trả góp (hỗ trợ mua xe): chia làm 2 loại vay mua xe thường và vay mua xe vinfast
                + Gói vay mua xe thường:
                Hạn mức: 20 triệu – tối đa 2 tỷ (thường tối đa 80% giá trị xe).
                Kỳ hạn: 3–36 tháng.
                Lãi suất: từ 13%–14%/năm.
                Kết nối showroom lớn; phù hợp khách dưới chuẩn ngân hàng.
                + Gói vay mua xe vinfast:
                Hạn mức: 100 triệu - tối đa 1 tỷ (tối đa đến 90% giá trị xe).
                Kỳ hạn: 12-84 tháng.
                Lãi suất: từ 11%–12%/năm.
                -Gói vay qua đăng ký/Cavet ô tô (vay theo xe đang sở hữu): chia làm 2 loại vay thường có giữ đăng ký xe và vay nhanh không giữ đăng ký xe
                + Gói giữ đăng ký xe:
                Hạn mức: 20 triệu – tối đa 1 tỷ (phụ thuộc vào giá trị xe; thường tối đa 80% giá trị xe).
                Kỳ hạn: 3–36 tháng.
                Lãi suất: từ 13%–14%/năm , minh bạch, dựa vào giá trị xe.
                Hồ sơ: CCCD + đăng ký gốc, xe còn hạn đăng kiểm, đủ điều kiện đăng ký giao dịch bảo đảm.
                + Gói vay nhanh không giữ đăng ký xe:
                Hạn mức: 20 triệu - 80 triệu (thường tối đa 80% giá trị xe).
                Điều kiện xe chung:
                Xe con/xe bán tải ≤15 năm, xe tải/xe khách ≤10 năm.
                Chấp nhận nợ xấu, nhưng không có nợ quá hạn tại Tima.
                Quy trình & trải nghiệm:
                KHÔNG giữ xe.
                Duyệt nhanh, giải ngân trong ngày sau khi hoàn tất thủ tục.
                Online: hỗ trợ đăng ký và nộp hồ sơ trực tuyến, tiết kiệm thời gian.
                App My Tima: hỗ trợ khách theo dõi khoản vay, tra cứu lịch trả nợ, quản lý hồ sơ tiện lợi.
                Bảo mật: thông tin khách hàng được bảo vệ theo quy định pháp luật.
                Tất toán: Phí 4%-3%-2% (năm đầu), miễn sau 12 tháng.

        ---

        THU THẬP THÔNG TIN KHÁCH HÀNG (BẮT BUỘC TRƯỚC KHI CHUYỂN HỒ SƠ):

        Hệ thống cần thu thập đủ 4 thông tin theo thứ tự sau.
        Mỗi lượt chỉ hỏi 1 thông tin chưa có. Tuyệt đối Không hỏi lại thông tin đã biết.
        Không hỏi lại bất kỳ thông tin nào khách đã tự cung cấp trong lúc trò chuyện (kể cả khi họ chưa được hỏi trực tiếp) — chỉ cần trích xuất và ghi nhận.


        Thứ tự ưu tiên thu thập:
        [1] Có xe ô tô không? (có / không) — CHỈ áp dụng/kiểm tra khi nhu_cau = cavet. Với nhu_cau = mua_xe, bỏ qua bước này hoàn toàn.
        [2] Tên khách hàng
        [3] Số điện thoại (cần đủ 10 chữ số nếu và có số 0 ở đầu. Nếu không phù hợp bảo người dùng: "Anh chị vui lòng nhập số điện thoại đầy đủ để em hỗ trợ ạ")
        [4] Tỉnh thành phố đang sinh sống (tự điều chỉnh lấy tên tỉnh thành phù hợp, viết đầy đủ)

        Ghi nhớ nội bộ trạng thái thu thập:
        - nhu_cau: null/mua_xe/cavet
        - co_xe: null/true/false
          (Chỉ có ý nghĩa với nhu_cau = cavet, dùng để xác nhận khách đang sở hữu xe hợp lệ để thế chấp đăng ký.
           Với nhu_cau = mua_xe, luôn set co_xe = false ngay khi xác định nhu_cau, và KHÔNG bao giờ hỏi khách về việc này.)
        - ten: null/<giá trị>
        - sdt: null/<giá trị>
        - tinh_thanh: null/<giá trị>

        Khi đã đủ 4 thông tin → KHÔNG kết thúc ngay, thay vào đó gửi xác nhận đầy đủ:

        "Dạ em xác nhận lại thông tin của anh chị ạ:
        - Họ tên: [TÊN]
        - Số điện thoại: [SĐT]
        - Khu vực: [TỈNH/THÀNH] (luôn ghi rõ ràng không viết tắt, ví dụ: Hà Nội, TP.Hồ Chí Minh, Đồng Nai, Hà Tĩnh)
        - Nhu cầu: [vay mua xe / vay theo đăng ký xe đang có]
        Thông tin đúng chưa ạ?"

        Nếu khách xác nhận đúng ("đúng/ok/đúng rồi/chính xác") →
        "Dạ em đã ghi nhận, nhân viên sẽ liên hệ anh chị [TÊN] sớm nhất ạ."

        Nếu khách báo sai thông tin nào →
        Hỏi lại đúng thông tin đó, cập nhật, rồi gửi lại toàn bộ xác nhận 1 lần nữa.

        Sau khi khách nhắn "ok/cảm ơn/được" →
        "Dạ em cảm ơn anh chị [TÊN], hẹn gặp lại ạ."
 ---

        KỊCH BẢN XỬ LÝ (TUÂN THỦ THỨ TỰ ƯU TIÊN):
        0) NGOẠI LỆ ƯU TIÊN CAO NHẤT (không cần thu thập thông tin):
        Nếu khách hỏi về đơn vay/tất toán/hợp đồng/hỗ trợ khoản vay hiện có →
        "Dạ anh chị tải app My Tima tại https://onelink.to/9fxq7u để tra cứu khoản vay, hoặc gọi hotline 1900.633.688 ấn phím 2 giúp em ạ."

	    0.5) ƯU TIÊN TRẢ LỜI CÂU HỎI SẢN PHẨM XEN GIỮA (áp dụng ở MỌI bước, kể cả khi đang thu thập thông tin [1]-[4]):
        Nếu ở bất kỳ lượt nào khách hỏi câu hỏi liên quan sản phẩm/khoản vay (lãi suất, hạn mức, kỳ hạn, phí, hồ sơ,
        tất toán, điều kiện xe, cách tính lãi...) thay vì trả lời đúng câu đang được hỏi (tên/SĐT/tỉnh thành) →
        BẮT BUỘC trả lời ngắn gọn câu hỏi đó của khách trước (theo KIẾN THỨC SẢN PHẨM hoặc mục 4/5 tương ứng),
        sau đó NỐI TIẾP ngay trong cùng câu trả lời bằng câu hỏi thu thập thông tin còn thiếu tiếp theo.
        → TUYỆT ĐỐI KHÔNG lờ đi câu hỏi của khách để lặp lại y nguyên câu hỏi thu thập trước đó.
        → TUYỆT ĐỐI KHÔNG lặp lại nguyên văn một câu hỏi thu thập đã hỏi ở lượt liền trước; nếu khách chưa trả lời,
        diễn đạt lại ngắn gọn khác đi, ghép cùng câu trả lời cho câu hỏi của khách.

        Ví dụ: đang hỏi tên, khách hỏi "lãi suất bao nhiêu" →
        "Dạ lãi suất từ 13%-14%/năm ạ, anh chị cho em xin tên để tiện xưng hô ạ."

        1) PHÂN LOẠI NHU CẦU & XÁC ĐỊNH CÓ XE (kiểm tra 1A TRƯỚC TIÊN; nếu khớp bất kỳ từ khóa nào ở 1A thì DỪNG NGAY, không xét tiếp 1B/1C):

        1A) Nếu khách đã nói rõ nhu cầu ngay từ đầu hoặc trong bất kỳ lượt nào:
        - Câu khách nhắc đến "mua xe / mua ô tô / mua trả góp" (có ý định MUA xe mới) → set nhu_cau = mua_xe, co_xe = false.
        → BỎ QUA HOÀN TOÀN câu hỏi có xe (không hỏi ở bước 1C lẫn bước [1]), chuyển thẳng sang thu thập [2] Tên.
        → TUYỆT ĐỐI KHÔNG hỏi "có xe ô tô không" hay bất kỳ biến thể nào của câu này khi nhu_cau = mua_xe, dù ở bất kỳ thời điểm nào trong hội thoại.
        - Câu khách CÓ CHỨA từ "đăng ký xe" hoặc "cavet" hoặc "cà vẹt" hoặc "đăng ký" ở BẤT KỲ vị trí nào trong câu, dù đi kèm từ gì khác (VD: "vay qua đăng ký xe", "vay bằng cavet", "thế chấp đăng ký xe")
        LUÔN hiểu là khách ĐANG SỞ HỮU XE. Set nhu_cau = cavet, co_xe = true NGAY LẬP TỨC.
        → TUYỆT ĐỐI KHÔNG hỏi "có xe ô tô không" trong mọi trường hợp này, kể cả khi câu không nói rõ "tôi đang có xe".
        → Chuyển thẳng sang thu thập [2] Tên.

        1B) Nếu khách hỏi số tiền cụ thể hoặc tư vấn gói vay mà CHƯA rõ nhu cầu (nhu_cau vẫn null) →
        "Dạ anh chị đang có nhu cầu vay mua xe mới hay vay theo đăng ký xe đang sở hữu ạ?"
        (Chỉ hỏi câu này khi nhu_cau vẫn null. KHÔNG hỏi "có xe ô tô không" — câu hỏi phân loại luôn là hỏi về NHU CẦU vay, không phải hỏi tình trạng sở hữu xe.)

        Xử lý câu trả lời của khách sau câu hỏi 1B/1C:
        - Khách trả lời "mua xe/mua xe mới/mua trả góp" → set nhu_cau = mua_xe, co_xe = false, KHÔNG hỏi thêm về việc có xe, chuyển thẳng bước [2] Tên.
        - Khách trả lời "theo xe đang có/cavet/đăng ký xe" → set nhu_cau = cavet, co_xe = true, chuyển thẳng bước [2] Tên.
        - Nếu khách trả lời mơ hồ (chỉ "có" hoặc "không") mà chưa rõ đang trả lời cho câu hỏi nào → hỏi lại rõ: "Dạ anh chị muốn vay mua xe mới hay vay theo đăng ký xe đang sở hữu ạ?"

        2) KHÁCH KHÔNG SỞ HỮU Ô TÔ (chỉ áp dụng cho nhánh VAY THEO ĐĂNG KÝ XE/CAVET, khi khách tự nói mình không có/không đứng tên xe ô tô):
        → "anh chị vui lòng đăng ký tại https://tima.vn/vay-tien-online
        để nhân viên gọi tư vấn thêm cho mình ạ."
        (Dừng thu thập thông tin, không hỏi tiếp.)

        Lưu ý quan trọng: Với nhu_cau = mua_xe, KHÔNG áp dụng bước này trong bất kỳ trường hợp nào — khách chưa có xe là điều bình thường vì đang cần vay để MUA xe mới.

        3) KHÁCH CÓ Ô TÔ / ĐỒNG Ý VAY / ĐÃ XÁC ĐỊNH NHU CẦU:
        → Bắt đầu/tiếp tục thu thập thông tin theo thứ tự [2] → [3] → [4].

        Câu hỏi mẫu theo từng bước:
        - Hỏi tên:  "Dạ anh chị cho em biết tên để tiện xưng hô ạ?"
        - Hỏi SĐT:  "Dạ anh chị cho em xin số điện thoại để nhân viên liên hệ hỗ trợ ạ?"
        - Hỏi tỉnh: "Dạ anh chị đang sinh sống tại tỉnh thành phố nào ạ?"

        4) HỒ SƠ & PHÍ (giải đáp nhanh, sau đó tiếp tục thu thập thông tin còn thiếu):
        - Hỏi định giá xe → xác định hãng xe TRƯỚC TIÊN (nếu chưa rõ, dùng tool tim_kiem_web để xác định hãng,
        hoặc hỏi lại khách). 
        BẮT BUỘC hỏi khách năm sản xuất xe nếu khách CHƯA cung cấp rõ năm (VD: "Dạ xe của mình sản xuất năm bao
        nhiêu ạ?"). TUYỆT ĐỐI KHÔNG tự suy đoán/mặc định bất kỳ năm nào khi khách chưa nói.
        Sau khi có đủ hãng xe + năm khách cung cấp, dùng tool tra_nam_hop_le(hãng) để xác nhận năm đó có hợp lệ
        trong hệ thống định giá không:
        Nếu năm khách nói KHÔNG nằm trong danh sách năm hợp lệ trả về, báo cho khách các năm gần nhất hệ
        thống hỗ trợ và hỏi khách chọn lại, KHÔNG tự ý làm tròn/thay bằng năm khác.
        Nếu hợp lệ, dùng tra_khoang_gia_xe(hãng, năm, tu_khoa = tên xe khách mô tả dù không đầy đủ).
        Nếu tool trả 1 giá duy nhất, báo đúng số đó; nếu trả khoảng giá (thấp nhất-cao nhất), báo dạng
        "khoảng [thấp nhất] - [cao nhất] đồng tuỳ theo mẫu cụ thể ạ". 
        Nếu chỉ tìm được khoảng giá thì phải có cụm tuỳ theo mẫu cụ thể trong câu trả lời.
        Sau đó tính luôn khoản tiền khách có thể vay được từ giá/khoảng giá vừa tra được.
        Nếu lỗi/không hỗ trợ/rỗng, báo "anh chị tra cứu tại https://tima.vn/dinh-gia-xe.html giúp em ạ."      
        - Hỏi giấy tờ   → "Chỉ cần CCCD và đăng ký xe gốc, xe còn hạn đăng kiểm là được anh chị nhé ạ."
        - Hỏi phí → "Khoản vay có phí anh chị nhé ạ, anh chị để lại số điện thoại để bên em báo chi tiết ạ."
                Phí tất toán sớm → "Phí tất toán dao động từ 2%-4% và cụ thể dựa vào thời điểm tất toán ạ. "
                Phí phạt trả chậm → "Anh chị vui lòng gọi đến hotline 1900.633.688 để được hỗ trợ ạ."

        5) KHU VỰC & CÂU HỎI KHÁC & TÍNH LÃI:
        - Khách hỏi khu vực/tỉnh thành ngoài phạm vi phục vụ → "anh chị vui lòng đăng ký tại https://tima.vn/vay-tien-online để nhân viên gọi tư vấn theo khu vực giúp mình ạ."
        - Hỏi cách theo dõi hồ sơ/lịch trả nợ/thông tin khoản vay → "anh chị tải app My Tima tại https://onelink.tima.vn/ để theo dõi khoản vay tiện lợi hơn ạ."
        - Hỏi lãi/hạn mức/nợ xấu → trả ngắn gọn theo KIẾN THỨC SẢN PHẨM, sau đó hỏi thông tin còn thiếu.
        - TÍNH LÃI: Lãi hàng tháng (đồng) = số tiền vay (đồng) × 0.0108. Tính ra số nguyên đầy đủ trước, sau đó mới định dạng dấu chấm hàng nghìn (VD: 20.000.000 vay → lãi = 216.000).
        Trả lời ngắn gọn: "Dạ số tiền lãi anh chị phải trả hàng tháng là [SỐ TIỀN] đồng ạ."
        - Hỏi chi nhánh: dùng tool tim_kiem_web tra chi nhánh, PGD của Tima.
         - Câu hỏi khác ngoài phạm vi khoản vay (không thuộc các mục trên) → "anh chị vui lòng để lại số điện thoại để nhân viên hỗ trợ ạ, hotline 1900.633.688 ạ."

        ---

        KẾT THÚC:
        Nếu khách nhắn "ok/cảm ơn/được" sau khi đã đủ thông tin →
        "Dạ em cảm ơn anh chị đã dành thời gian cho tima. Nếu còn thắc mắc gì thì anh chị cứ nhắn cho em nhé ạ."	
    """
)

FALLBACK_REPLY = "Em xin lỗi, xin anh chị vui lòng để lại số điện thoại bên em sẽ cho nhân viên gọi đến và hỗ trợ mình ngay ạ."

MAX_TOOL_ITERATIONS = 5 # flow định giá xe cần 2 vòng (năm -> khoảng giá), chừa buffer


# ---------------------------------------------------------------------------
# Tool: tra định giá xe (gọi API nội bộ tima.vn/Valuation/ModalPrice)
# ---------------------------------------------------------------------------

async def tim_kiem_web(query: str) -> dict:
    """Tìm kiếm nhanh trên web (DuckDuckGo, free, không cần API key).
    Dùng khi cần xác định hãng xe từ tên xe, tra chi nhánh Tima, hoặc thông tin chưa có sẵn."""
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            snippet = data.get("AbstractText") or ""
            if not snippet and data.get("RelatedTopics"):
                snippet = data["RelatedTopics"][0].get("Text", "")
            return {"query": query, "ket_qua": snippet or "Không tìm thấy kết quả rõ ràng"}
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.warning("Lỗi tìm kiếm web (%s): %s", query, e)
        return {"error": "Không tìm kiếm được lúc này"}


# ---------------------------------------------------------------------------
# Tools: tra năm hợp lệ / tên xe hợp lệ / định giá xe (API nội bộ tima.vn)
# ---------------------------------------------------------------------------

_COMMON_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://tima.vn/dinh-gia-xe.html",
}


async def tra_nam_hop_le(hang_xe: str) -> dict:
    """Lấy danh sách năm sản xuất hợp lệ theo hãng xe."""
    url = "https://tima.vn/Valuation/GetYearCar"
    params = {"brand": hang_xe.lower().strip()}
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.get(url, params=params, headers=_COMMON_HEADERS)
            resp.raise_for_status()
            logger.info("tra_nam_hop_le(%s) raw response: %s", hang_xe, resp.text[:300])
            data = resp.json()
            return {"hang_xe": hang_xe, "nam_hop_le": data.get("data", [])}
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.warning("Lỗi tra năm hợp lệ (%s): %s", hang_xe, e)
        return {"error": "Không tra được danh sách năm cho hãng này"}


async def _lay_danh_sach_xe_goi_y(hang_xe: str, nam_san_xuat: int, tu_khoa: str) -> list[str]:
    """Helper nội bộ: lấy toàn bộ tên xe hợp lệ rồi lọc/sắp xếp theo độ khớp với tu_khoa."""
    url = "https://tima.vn/Valuation/GetVehiclesCar"
    params = {"brand": hang_xe.lower().strip(), "year": nam_san_xuat}
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        resp = await http_client.get(url, params=params, headers=_COMMON_HEADERS)
        resp.raise_for_status()
        logger.info(
            "_lay_danh_sach_xe_goi_y(%s, %s) raw response: %s",
            hang_xe, nam_san_xuat, resp.text,
        )
        all_names = resp.json().get("data", [])

    keywords = tu_khoa.lower().split()
    candidates = [n for n in all_names if all(k in n.lower() for k in keywords)]

    if not candidates:
        candidates = difflib.get_close_matches(tu_khoa.lower(), all_names, n=8, cutoff=0.3)
    else:
        candidates.sort(
            key=lambda n: difflib.SequenceMatcher(None, tu_khoa.lower(), n).ratio(),
            reverse=True,
        )

    return candidates


async def tra_khoang_gia_xe(hang_xe: str, nam_san_xuat: int, tu_khoa: str) -> dict:
    """Tra khoảng giá xe: tìm các tên xe khớp gần với tu_khoa, tra giá SONG SONG cho tối đa 5 bản,
    trả về khoảng giá thấp nhất - cao nhất thay vì đoán 1 bản cụ thể (chính xác hơn khi khách mô tả
    tên xe không đầy đủ)."""
    try:
        candidates = await _lay_danh_sach_xe_goi_y(hang_xe, nam_san_xuat, tu_khoa)
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.warning("Lỗi lấy danh sách xe gợi ý (%s/%s/%s): %s", hang_xe, nam_san_xuat, tu_khoa, e)
        return {"error": "Không tra được danh sách xe cho hãng/năm này"}

    if not candidates:
        return {"error": "Không tìm thấy mẫu xe nào khớp với mô tả"}

    top_candidates = candidates[:5]
    results = await asyncio.gather(
        *[tra_dinh_gia_xe(hang_xe, ten, nam_san_xuat) for ten in top_candidates]
    )

    gia_list = [r["gia_uoc_tinh_vnd"] for r in results if "gia_uoc_tinh_vnd" in r]

    if not gia_list:
        return {"error": "Không tra được giá cho các mẫu xe khớp"}

    if len(set(gia_list)) == 1:
        return {
            "hang_xe": hang_xe,
            "nam_san_xuat": nam_san_xuat,
            "gia_uoc_tinh_vnd": gia_list[0],
            "so_mau_xe_khop": len(gia_list),
        }

    return {
        "hang_xe": hang_xe,
        "nam_san_xuat": nam_san_xuat,
        "gia_thap_nhat_vnd": min(gia_list),
        "gia_cao_nhat_vnd": max(gia_list),
        "so_mau_xe_khop": len(gia_list),
    }


async def tra_dinh_gia_xe(hang_xe: str, ten_xe: str, nam_san_xuat: int) -> dict:
    url = "https://tima.vn/Valuation/ModalPrice"
    params = {
        "brand": hang_xe.lower().strip(),
        "year": nam_san_xuat,
        "vehicles": ten_xe.lower().strip(),
    }
    headers = _COMMON_HEADERS
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.get(url, params=params, headers=headers)
            resp.raise_for_status()

            # Endpoint trả về HTML fragment (để nhúng modal), không phải JSON.
            # Giá nằm trong <div class="result"><label>1,243,000,000 VNĐ</label></div>
            soup = BeautifulSoup(resp.text, "html.parser")
            result_div = soup.select_one("div.result label")

            if not result_div:
                logger.warning(
                    "Không tìm thấy div.result trong HTML trả về (%s/%s/%s)",
                    hang_xe, ten_xe, nam_san_xuat,
                )
                return {"error": "Không tìm thấy định giá cho xe này"}

            gia_text = result_div.get_text(strip=True)  # "1,243,000,000 VNĐ"
            match = re.search(r"[\d.,]+", gia_text)

            if not match:
                return {"error": "Không tìm thấy định giá cho xe này"}

            gia_so = int(match.group(0).replace(",", "").replace(".", ""))

            return {
                "hang_xe": hang_xe,
                "ten_xe": ten_xe,
                "nam_san_xuat": nam_san_xuat,
                "gia_uoc_tinh_vnd": gia_so,
            }
    except httpx.HTTPError as e:
        logger.warning("Lỗi tra định giá xe (%s/%s/%s): %s", hang_xe, ten_xe, nam_san_xuat, e)
        return {"error": "Không tra được định giá xe lúc này"}


# Map tên tool -> hàm thực thi tương ứng
TOOL_FUNCTIONS = {
    "tim_kiem_web": tim_kiem_web,
    "tra_nam_hop_le": tra_nam_hop_le,
    "tra_khoang_gia_xe": tra_khoang_gia_xe,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "tim_kiem_web",
            "description": (
                "Tìm kiếm nhanh trên mạng. Dùng khi cần xác định hãng xe từ tên xe khách nói "
                "(VD khách nói 'Vios' cần tìm hãng là gì), tra chi nhánh/PGD Tima, hoặc thông tin "
                "khác chưa có sẵn trong dữ liệu nội bộ."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Nội dung cần tìm kiếm"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tra_nam_hop_le",
            "description": (
                "Lấy danh sách năm sản xuất hợp lệ mà hệ thống định giá hỗ trợ cho 1 hãng xe. "
                "BẮT BUỘC gọi tool này trước tiên trong flow định giá xe, để xác nhận/chuẩn hoá "
                "năm sản xuất khách cung cấp có hợp lệ không."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hang_xe": {
                        "type": "string",
                        "description": "Hãng xe viết thường không dấu, VD: toyota, honda, cadillac",
                    },
                },
                "required": ["hang_xe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tra_khoang_gia_xe",
            "description": (
                "Tra khoảng giá xe ô tô đã qua sử dụng, dựa trên hãng, năm sản xuất, và mô tả tên xe "
                "của khách (không cần biết tên xe đầy đủ/chính xác). Tool tự tìm các mẫu xe khớp gần "
                "với mô tả và trả về khoảng giá thấp nhất - cao nhất trong số đó (hoặc 1 giá duy nhất "
                "nếu chỉ có 1 mẫu khớp). BẮT BUỘC gọi tool này SAU tra_nam_hop_le."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hang_xe": {
                        "type": "string",
                        "description": "Hãng xe viết thường không dấu, VD: toyota, honda, cadillac",
                    },
                    "nam_san_xuat": {
                        "type": "integer",
                        "description": "Năm sản xuất xe, đã xác nhận hợp lệ từ tra_nam_hop_le",
                    },
                    "tu_khoa": {
                        "type": "string",
                        "description": "Tên xe khách mô tả (không cần đầy đủ), VD: 'glc 300', 'vios'",
                    },
                },
                "required": ["hang_xe", "nam_san_xuat", "tu_khoa"],
            },
        },
    },
    # Thêm tool khác vào đây sau này, cùng lúc thêm hàm thực thi vào TOOL_FUNCTIONS ở trên
]


def _build_history(messages: List[Message]) -> List[dict]:
    """messages phải theo thứ tự cũ -> mới trước khi gọi hàm này."""
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in messages:
        role = "user" if m.sender_type == "customer" else "assistant"
        history.append({"role": role, "content": m.content})
    return history


async def _run_tool_call(tool_call) -> str:
    """Thực thi 1 tool call, trả về content dạng string để đưa vào message role=tool."""
    fn_name = tool_call.function.name
    fn = TOOL_FUNCTIONS.get(fn_name)

    if fn is None:
        logger.warning("Model gọi tool không tồn tại: %s", fn_name)
        return json.dumps({"error": f"Tool '{fn_name}' không tồn tại"}, ensure_ascii=False)

    try:
        fn_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        logger.warning("Không parse được arguments cho tool %s: %s", fn_name, tool_call.function.arguments)
        return json.dumps({"error": "Tham số tool không hợp lệ"}, ensure_ascii=False)

    # Lọc bỏ tham số model gửi thừa (ngoài schema đã khai báo) để tránh crash
    valid_params = set(inspect.signature(fn).parameters.keys())
    extra_keys = set(fn_args.keys()) - valid_params
    if extra_keys:
        logger.warning("Tool %s nhận tham số thừa, đã bỏ qua: %s", fn_name, extra_keys)
        fn_args = {k: v for k, v in fn_args.items() if k in valid_params}

    try:
        result = await fn(**fn_args)
    except TypeError as e:
        logger.warning("Tool %s gọi sai tham số (%s): %s", fn_name, fn_args, e)
        return json.dumps({"error": f"Tham số gọi tool '{fn_name}' không hợp lệ"}, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False)


async def _call_openai_with_tools(messages_payload: List[dict]) -> str:
    """Gọi OpenAI, tự xử lý vòng lặp tool_calls, trả về content text cuối cùng."""
    completion = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages_payload,
        tools=TOOLS,
        temperature=0.2,
    )
    response_message = completion.choices[0].message

    iterations = 0
    while response_message.tool_calls and iterations < MAX_TOOL_ITERATIONS:
        # Lưu lại message có tool_calls vào payload (bắt buộc theo format OpenAI)
        messages_payload.append(response_message.model_dump(exclude_none=True))

        for tool_call in response_message.tool_calls:
            tool_result_content = await _run_tool_call(tool_call)
            messages_payload.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result_content,
                }
            )

        completion = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages_payload,
            tools=TOOLS,
            temperature=0.4,
        )
        response_message = completion.choices[0].message
        iterations += 1

    if iterations >= MAX_TOOL_ITERATIONS and response_message.tool_calls:
        logger.warning("Đạt giới hạn tool call iterations, trả fallback")
        return FALLBACK_REPLY

    return response_message.content or FALLBACK_REPLY


async def handle_user_message(
        db: AsyncSession,
        conversation_id: int | None,
        external_conversation_id: str | None,
        sender_id: str,
        content: str,
        external_message_id: str | None = None,
        channel_account_id: int | None = None,
):
    # 1. Lấy hoặc tạo conversation
    if conversation_id:
        convo = await get_conversation(db, conversation_id=conversation_id)
        if not convo:
            raise ValueError(f"Conversation {conversation_id} not found")
    else:
        if not external_conversation_id:
            raise ValueError(
                "Cần external_conversation_id để tạo conversation mới"
            )
        convo = await upsert_conversation(
            db,
            ConversationCreate(
                external_conversation_id=external_conversation_id,
                channel_account_id=channel_account_id,
                status=1,
            ),
        )

    # 2. Lưu tin nhắn của user
    user_external_id = external_message_id or f"cus_{uuid.uuid4().hex}"
    user_msg = await upsert_message(
        db,
        MessageCreate(
            conversation_id=convo.id,
            external_message_id=user_external_id,
            sender_type="customer",
            sender_id=sender_id,
            message_direction=2,
            message_type="text",
            content=content,
            status=1
        ),
    )

    # 3. Lấy lịch sử hội thoại (20 tin gần nhất), đảo lại thành cũ -> mới
    _, history_messages = await list_messages(
        db, conversation_id=convo.id, limit=20, offset=0
    )
    history_messages = list(reversed(history_messages))

    # 4. Gọi OpenAI (có xử lý lỗi + tool calling)
    try:
        messages_payload = _build_history(history_messages)
        reply_text = await _call_openai_with_tools(messages_payload)
    except OpenAIError:
        logger.exception("OpenAI call failed for conversation_id=%s", convo.id)
        reply_text = FALLBACK_REPLY

    # 5. Lưu tin nhắn trả lời của bot
    bot_external_id = f"rl_{user_external_id}"
    bot_msg = await upsert_message(
        db,
        MessageCreate(
            conversation_id=convo.id,
            external_message_id=bot_external_id,
            sender_type="bot",
            sender_id="0",
            message_direction=1,
            message_type="text",
            content=reply_text,
            status=1
        ),
    )

    return convo, user_msg, bot_msg, reply_text