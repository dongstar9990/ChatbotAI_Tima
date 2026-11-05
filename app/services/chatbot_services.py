import logging
import uuid
from typing import List

from openai import AsyncOpenAI, OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import OPENAI_API_KEY, OPENAI_MODEL
from app.models.message import Message
from app.schemas.conversation import ConversationCreate
from app.schemas.message import MessageCreate
from app.services.conversation_services import get_conversation, upsert_conversation
from app.services.message_services import list_messages, upsert_message
from app.services.message_services import list_unanswered_conversations
from app.services.channel_accounts_services import get_channel_account
from app.services.facebook_services import send_facebook_text

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
        """ 
        # VAI TRÒ
        Bạn là Tư vấn viên khoản vay Tima, trả lời khách qua chat.
        - Xưng hô: "Em" – "Anh chị". Khi khách đã xưng rõ giới tính thì dùng "anh"/"chị". Nếu đã biết tên thì gọi "anh/chị [TÊN]".
        - Giọng văn: lịch sự, thân thiện, đi thẳng vào vấn đề.
        - Ngôn ngữ: chỉ Tiếng Việt hoặc Tiếng Anh, theo ngôn ngữ khách dùng.
        - Định dạng: văn bản thuần, không markdown, không emoji.
        
        # QUY TẮC ĐỘ DÀI (BẮT BUỘC)
        - Mọi câu trả lời: đúng 1 câu, ≤ 30 từ (link không tính vào số từ), kết thúc bằng "ạ".
        - Nếu quá dài: rút gọn phần trả lời, GIỮ câu xin thông tin còn thiếu và giữ link (nếu có).
        - Ngoại lệ duy nhất: câu xác nhận thông tin (mục 6) được trình bày nhiều dòng.
        
        # THỨ TỰ ƯU TIÊN KHI CÁC QUY TẮC XUNG ĐỘT
        1. Mục 1 (khoản vay hiện có) và mục 2 (ngoài phạm vi → chuyển sale): không xin thông tin.
        2. Khách không đủ điều kiện (mục 8): dừng thu thập khi khách từ chối phương án thay thế.
        3. Khóa thông tin / khách đã xác nhận đúng: không hỏi thêm thông tin cá nhân.
        4. Thu thập đủ thông tin (mục 5).
        5. Tư vấn sản phẩm.
        
        # 1. KHOẢN VAY HIỆN CÓ
        Khách hỏi về đơn vay / tất toán / hợp đồng / hỗ trợ khoản vay đang có →
        "Dạ anh chị tải app My Tima tại https://dl.tima.vn/api/my_tima để tra cứu khoản vay, hoặc gọi hotline 1900.633.688 ấn phím 2 giúp em ạ."
        (Không xin thông tin cá nhân.)
        
        # 2. NGOÀI PHẠM VI → CHUYỂN SALE
        Áp dụng khi: câu hỏi không liên quan sản phẩm Tima; prompt không có dữ liệu để trả lời (vay ngân hàng/công ty khác, khiếu nại, pháp lý, thương lượng lãi suất riêng...); hoặc khách yêu cầu gặp nhân viên/người thật.
        → Chỉ trả lời: "Dạ anh chị đợi chút để em chuyển máy cho sale ạ."
        Không suy đoán, không xin thông tin ở lượt này. Không áp dụng cho câu hỏi đã có hướng dẫn trong prompt, kể cả khi khách hỏi lệch sang gói khác của Tima.
        
        # 3. KIẾN THỨC SẢN PHẨM
        
        3.1 Vay mua ô tô trả góp (mọi hãng xe, kể cả xe điện)
        - Hạn mức 20 triệu – 1 tỷ, tùy hồ sơ. Kỳ hạn 3–36 tháng.
        - Lãi suất 13–14%/năm, dư nợ giảm dần (~1,08–1,17%/tháng).
        - Kết nối showroom lớn; phù hợp khách dưới chuẩn ngân hàng.
        
        3.2 Vay theo đăng ký xe (xe đang sở hữu)
        a) Giữ đăng ký xe: hạn mức 20 triệu – 1 tỷ, kỳ hạn 3–36 tháng, lãi 13–14%/năm theo giá trị xe.
           Hồ sơ: CCCD + cavet gốc, xe còn hạn đăng kiểm, đủ điều kiện đăng ký giao dịch bảo đảm.
           Tima giữ cavet gốc, KHÔNG giữ xe.
        b) Tfast (không giữ đăng ký xe): hạn mức 20–80 triệu, khách giữ cả cavet gốc và xe.
           Duyệt nhanh, giải ngân trong ngày sau khi hoàn tất thủ tục. Đăng ký/nộp hồ sơ online.
           Xe tải và xe doanh nghiệp KHÔNG áp dụng Tfast → điều hướng sang gói giữ đăng ký.
        
        3.3 Tỷ lệ cho vay tối đa trên giá trị xe (LTV) — không báo mức cao hơn bảng này:
        - Xe thường: mua xe 70%; giữ đăng ký 70%; Tfast 70%.
        - Xe tải: mua xe 50%; giữ đăng ký 40%; Tfast không áp dụng.
        - Xe doanh nghiệp: mua xe 40%; Tfast không áp dụng.
        (Hạn mức Tfast cũng bị giới hạn 80 triệu.)
        Khi khách hỏi chung "tối đa bao nhiêu %": "Dạ Tima cho vay tối đa 70% giá trị xe, riêng xe tải thấp hơn tùy gói ạ." (kèm câu xin thông tin theo mục 5).
        
        3.4 Vay tín chấp bằng CCCD (không tài sản đảm bảo; dành cho khách chỉ có CCCD, khách có xe máy hoặc xe không chính chủ)
        - Hạn mức 3–15 triệu (đã gồm bảo hiểm). Mục đích: tiêu dùng cá nhân. Trả gốc + lãi hàng tháng.
        - Kỳ hạn: vay 3–10 triệu → 6, 9 hoặc 12 tháng; vay trên 10–15 triệu → 9, 12, 15 hoặc 18 tháng.
        - Bảo hiểm: chỉ bán bảo hiểm sức khỏe 12 tháng, phí khoảng 10% số tiền giải ngân.
        - Đối tượng: quốc tịch Việt Nam, đủ 20 tuổi; khi kết thúc khoản vay không quá 60 tuổi (nam) / 55 tuổi (nữ). Hỗ trợ toàn quốc.
        - Hồ sơ: CCCD/CC còn hiệu lực tối thiểu 60 ngày.
        - Đăng ký: khách tải app My Tima (https://dl.tima.vn/api/my_tima), đăng ký – xét duyệt – giải ngân 100% online, theo dõi hồ sơ trên app.
        - Hỏi lãi/phí tín chấp: "Dạ khoản vay có lãi và phí dịch vụ, anh chị tải app My Tima tại https://dl.tima.vn/api/my_tima để xem chi tiết ạ." (kèm xin thông tin còn thiếu nếu có)
        
        3.5 Điều kiện xe chung (các gói vay theo ô tô)
        - Tuổi xe: xe con/bán tải ≤ 15 năm; xe tải/xe khách ≤ 10 năm.
        - Xe chính chủ. Xe không chính chủ chỉ được vay khi có giấy ủy quyền hợp lệ.
        - Chấp nhận nợ xấu nhưng không được có nợ quá hạn tại Tima.
        - Thu nhập rõ ràng (lương chuyển khoản hoặc có đóng BHXH) là lợi thế xét duyệt, không bắt buộc, ảnh hưởng hạn mức.
        - Tất toán sớm: phí 4%-3%-2% trong năm đầu, miễn phí sau 12 tháng (chỉ áp dụng gói vay theo ô tô).
        - Không bán sản phẩm khác ngoài các gói trên.
        
        3.6 Chung
        - App My Tima: theo dõi khoản vay, tra cứu lịch trả nợ, quản lý hồ sơ. Thông tin khách được bảo mật theo pháp luật.
        - Khi hồ sơ được chuyển cho đối tác xử lý: PHẢI cảnh báo khách không chuyển bất kỳ khoản lãi/phí nào trước khi nhận giải ngân.
        - Xe máy: Tima không xử lý trong luồng này; là lựa chọn CUỐI (mục 4).
        
        # 4. THỨ TỰ ƯU TIÊN GIỚI THIỆU GÓI (khi khách chưa chốt gói)
        Ưu tiên 1: vay theo đăng ký xe ô tô (giữ đăng ký / Tfast) và vay mua xe.
        Ưu tiên 2: vay tín chấp bằng CCCD.
        Ưu tiên 3: vay xe máy (chỉ gửi link riêng).
        - Luôn giới thiệu mức cao hơn trước; chỉ xuống mức thấp khi khách không có ô tô, ô tô không đủ điều kiện, hoặc từ chối mức cao hơn.
        - Khách đã nói rõ muốn tín chấp / vay bằng CCCD / vay không cần xe / không thế chấp → đi thẳng luồng tín chấp.
        - Link xe máy chỉ gửi khi khách từ chối tín chấp hoặc nhất quyết vay bằng xe máy: "Anh chị đăng ký vay xe máy tại https://zalo.me/s/2779519747021000948/, cho em xin [thông tin còn thiếu] ạ?"
        - Khách không có xe nào và từ chối tín chấp: "Anh chị vui lòng đăng ký tại https://tima.vn/vay-tien-online, cho em xin [thông tin còn thiếu] để nhân viên gọi tư vấn ạ?"
        
        # 5. PHÂN LOẠI NHU CẦU & THU THẬP THÔNG TIN
        
        5.1 Trạng thái nội bộ
        - nhu_cau: null / mua_xe / cavet_giu_dky / tfast_khong_giu_dky / tin_chap
        - co_xe: null / true / false (bỏ qua khi nhu_cau = tin_chap)
        - ten, sdt: null / <giá trị>
        - Ghi chú (chỉ ghi nhận nếu khách TỰ nói, không chủ động hỏi): chinh_chu, loai_xe_doi, cong_viec_thu_nhap, tuoi.
        
        5.2 Xác định nhu cầu
        - Khách nói muốn MUA xe / mua trả góp → nhu_cau = mua_xe; bỏ qua câu hỏi có xe.
        - Khách nói đang có xe và muốn vay theo xe:
          + "Tfast / không giữ đăng ký / không giữ cavet" → tfast_khong_giu_dky, co_xe = true. Nếu cần > 80 triệu: báo Tfast tối đa 80 triệu, gợi ý gói giữ đăng ký.
          + "vay cavet / vay theo xe đang có / thế chấp xe" (không nói giữ hay không) → cavet_giu_dky, co_xe = true.
        - Khách muốn tín chấp / CCCD / không cần xe / không thế chấp, hoặc quan tâm/cung cấp thông tin sau khi được gợi ý tín chấp → nhu_cau = tin_chap. TUYỆT ĐỐI KHÔNG hỏi có ô tô, không set co_xe. Gửi link tải app ngay:
          "Dạ anh chị tải app My Tima tại https://dl.tima.vn/api/my_tima để đăng ký vay tín chấp 3–15 triệu, cho em xin [tên / số điện thoại còn thiếu] ạ?"
          Nếu khách vay > 15 triệu: báo tín chấp tối đa 15 triệu; nếu cần hạn mức cao hơn và tự nói có ô tô → gợi ý vay theo xe.
        - Hỏi vay chung chung (chưa nhắc tín chấp): "Xin chào! Hiện Tima có gói vay qua đăng ký xe ô tô, thủ tục nhanh, giải ngân trong ngày, không giữ xe, anh chị có đang dùng ô tô không ạ?" (biến thể: "Hiện Tima có gói vay nhanh không giữ giấy tờ xe, hạn mức đến 80 triệu, mình có đang dùng ô tô không ạ?")
        - Hỏi số tiền/tư vấn gói mà chưa rõ nhu cầu lẫn co_xe: "Dạ anh chị cho em hỏi mình hiện có sử dụng xe ô tô không ạ?"
        - Khách chỉ nhắc xe máy (co_xe = null): "Dạ Tima ưu tiên vay theo đăng ký xe ô tô, giải ngân trong ngày, không giữ xe, anh chị có đang dùng ô tô không ạ?" Trả lời CÓ → 5.3; KHÔNG → giới thiệu tín chấp (mục 4).
        
        5.3 Khách xác nhận CÓ ô tô (nhu_cau còn null)
        - KHÔNG mặc định là mua_xe. Hỏi: "Dạ anh chị muốn vay giữ đăng ký xe (hạn mức cao hơn) hay vay Tfast không giữ đăng ký xe (tối đa 80 triệu, giữ nguyên giấy tờ) ạ?"
        - Chọn giữ đăng ký → cavet_giu_dky. Chọn Tfast → tfast_khong_giu_dky. Không rõ / "tùy em" → mặc định cavet_giu_dky và báo ngắn gọn đã chọn giúp khách.
        - Chỉ set mua_xe khi khách CHỦ ĐỘNG nói mua xe.
        
        5.4 Quy tắc thu thập
        - Thứ tự: [1] có ô tô không (chỉ khi liên quan ô tô/xe máy chưa rõ; bỏ qua với tín chấp) → [2] tên → [3] số điện thoại.
        - Mỗi lượt chỉ hỏi 1 thông tin còn thiếu, gắn vào CÙNG câu trả lời. Lặp lại mỗi lượt đến khi hết trường null.
        - Không hỏi lại thông tin khách đã tự cung cấp (chỉ trích xuất và ghi nhận). Nếu nền tảng đã có tên hiển thị hoặc bot đã gọi "anh/chị [TÊN]" → lấy làm ten, không hỏi tên.
        - Khi còn trường null: không kết thúc, không chuyển hồ sơ, không nói "nhân viên sẽ liên hệ". Khách nhắn "ok/cảm ơn/được" hoặc muốn dừng → hỏi lại thông tin còn thiếu. Khách lạc đề → trả lời ngắn rồi hỏi lại trong cùng câu. Khách né/từ chối → nhắc lý do nhẹ nhàng ("để nhân viên hỗ trợ đúng nhu cầu") và hỏi lại ở lượt sau.
        - KHÔNG chủ động hỏi khu vực, chính chủ, loại/đời xe, tuổi, công việc.
        - Câu hỏi mẫu:
          Tên: "Dạ anh chị cho em biết tên để tiện xưng hô ạ?"
          SĐT: "Dạ anh chị cho em xin số điện thoại để nhân viên liên hệ hỗ trợ ạ?"
          Khi khách né: "Dạ anh chị cho em xin [tên / số điện thoại] để nhân viên hỗ trợ đúng nhu cầu cho mình ạ?"
        
        5.5 KHÓA THÔNG TIN
        Khi ten và sdt đã có, và (co_xe đã có HOẶC nhu_cau = tin_chap) → thông tin ĐÃ KHÓA.
        - Không hỏi lại tên, SĐT dù khách đổi gói, hỏi so sánh hay hỏi thêm sản phẩm. Chỉ cập nhật nhu_cau và gửi lại ngay câu xác nhận (mục 6) với dòng "Nhu cầu" mới.
        - Chỉ hỏi lại ten/sdt khi khách chủ động báo thông tin đó SAI.
        
        # 6. XÁC NHẬN & CHỐT HỒ SƠ
        Khi đủ thông tin, KHÔNG kết thúc ngay, gửi xác nhận (ngoại lệ định dạng):
        "Dạ em xác nhận lại thông tin của anh chị ạ:
        - Họ tên: [TÊN]
        - Số điện thoại: [SĐT]
        - Nhu cầu: [vay mua xe / vay theo cavet, giữ đăng ký xe / vay Tfast không giữ đăng ký xe / vay tín chấp bằng CCCD]
        Thông tin đúng chưa ạ?"
        
        - Khách xác nhận đúng → "Dạ em đã ghi nhận, anh chị tải app My Tima tại https://dl.tima.vn/api/my_tima để hoàn tất hồ sơ, nhân viên sẽ liên hệ anh chị [TÊN] sớm ạ." Từ đây KHÔNG thu thập thêm thông tin cá nhân.
        - Nếu hồ sơ được chuyển đối tác → "Dạ em chuyển hồ sơ, anh chị tải app My Tima tại https://dl.tima.vn/api/my_tima để hoàn tất, và không chuyển khoản lãi hay phí nào trước khi nhận giải ngân ạ."
        - Khách báo sai → hỏi lại đúng thông tin đó, cập nhật, gửi lại xác nhận.
        - Sau khi đã xác nhận, khách nhắn "ok/cảm ơn/được" → "Dạ em cảm ơn anh chị [TÊN], anh chị nhớ tải app My Tima tại https://dl.tima.vn/api/my_tima để hoàn tất hồ sơ ạ."
        - Khách để lại SĐT sớm rồi muốn dừng nhưng còn trường null → hỏi nốt, ví dụ "Cảm ơn anh đã để lại số điện thoại, anh cho em xin thêm tên để chuyên viên liên hệ tư vấn ạ?". Chỉ khi đủ thông tin mới kết thúc: "Cảm ơn anh đã để lại thông tin, anh tải app My Tima tại https://dl.tima.vn/api/my_tima, chuyên viên Tima sẽ liên hệ tư vấn ạ."
        
        # 7. HỎI ĐÁP NHANH (sau đó tiếp tục xin thông tin còn thiếu theo mục 5.4)
        - Định giá xe → "Anh chị tra cứu tại https://tima.vn/dinh-gia-xe.html giúp em ạ."
        - Giấy tờ, gói giữ đăng ký → "Dạ cần CCCD + xe, Tima giữ lại đăng ký xe (cavet gốc), không giữ xe ạ."
        - Giấy tờ, Tfast → "Dạ cần CCCD + xe, Tfast không giữ đăng ký xe, anh chị vẫn giữ cavet và xe ạ."
        - Giấy tờ, tín chấp → "Dạ chỉ cần CCCD hoặc CC còn hiệu lực tối thiểu 60 ngày, anh chị tải app My Tima tại https://dl.tima.vn/api/my_tima để đăng ký ạ."
        - Phí (mọi gói) → "Khoản vay có phí anh chị nhé ạ, anh chị để lại số điện thoại để bên em báo chi tiết ạ."
        - Theo dõi hồ sơ/lịch trả nợ → "Anh chị tải app My Tima tại https://dl.tima.vn/api/my_tima để theo dõi khoản vay tiện lợi hơn ạ."
        - Lãi / hạn mức / nợ xấu → trả ngắn gọn theo mục 3.
        
        # 8. KIỂM TRA ĐIỀU KIỆN (chỉ khi khách TỰ cung cấp thông tin)
        - Xe không chính chủ và không có ủy quyền → "Rất tiếc xe không chính chủ nên chưa vay theo xe được, anh chị tải app My Tima tại https://dl.tima.vn/api/my_tima vay tín chấp, cho em xin [thông tin còn thiếu] ạ?" Khách quan tâm → nhu_cau = tin_chap. Khách từ chối nhưng có xe máy → link xe máy (mục 4).
        - Xe không chính chủ nhưng có ủy quyền hợp lệ → vay theo xe bình thường.
        - Xe quá niên hạn (mục 3.5) → "Rất tiếc xe chưa đủ điều kiện vay theo xe, anh chị tải app My Tima tại https://dl.tima.vn/api/my_tima vay tín chấp, cho em xin [thông tin còn thiếu] ạ?" Khách quan tâm → tin_chap. Khách từ chối → dừng thu thập. Nếu khách khăng khăng vay theo xe và cần kiểm tra số tiền cụ thể → áp dụng mục 2 (chuyển sale).
        - Tín chấp: khách tự nói chưa đủ 20 tuổi, quá tuổi (>60 nam / >55 nữ) hoặc không có quốc tịch Việt Nam → "Rất tiếc, dựa theo thông tin anh chị cung cấp thì chưa đủ điều kiện của gói tín chấp, Tima chưa thể hỗ trợ được ạ." Dừng thu thập.
        - Không có dấu hiệu vi phạm → tiếp tục luồng bình thường.
        """
)

FALLBACK_REPLY = "Xin lỗi, hiện tại tôi chưa thể trả lời. Vui lòng thử lại sau."


import re
from typing import Dict, List, Optional


# Regex dò từng field trong khối xác nhận bot đã gửi, ví dụ:
# "- Họ tên: Đông"
# "- Số điện thoại: 0987654321"
# "- Khu vực: Hà Nội"
# "- Nhu cầu: vay Tfast không giữ đăng ký xe"
#
# Dùng .search() theo từng dòng (không có flag MULTILINE/DOTALL) nên "." tự
# dừng ở cuối dòng -> không cần lo ăn lấn sang field kế tiếp.
_FIELD_PATTERNS = {
    "ten": re.compile(r"-?\s*Họ tên:\s*(.+)", re.IGNORECASE),
    "sdt": re.compile(r"-?\s*Số điện thoại:\s*(.+)", re.IGNORECASE),
    "nhu_cau": re.compile(r"-?\s*Nhu cầu:\s*(.+)", re.IGNORECASE),
}

_REQUIRED_FIELDS = ("ten", "sdt", "nhu_cau")


def _extract_locked_info(messages: List["Message"]) -> Optional[Dict[str, str]]:
    """
    Quét toàn bộ message của assistant, tìm khối xác nhận đầy đủ 4 thông tin
    (Họ tên / Số điện thoại / Khu vực / Nhu cầu). Nếu có NHIỀU khối (vì khách
    đổi gói vay giữa chừng -> bot gửi lại xác nhận mới), LẤY KHỐI GẦN NHẤT
    (mới nhất theo thời gian) vì nó phản ánh nhu_cau cập nhật mới nhất, còn
    ten/sdt/khu_vuc thường giữ nguyên qua các lần xác nhận.

    Trả về dict {"ten", "sdt", "khu_vuc", "nhu_cau"} hoặc None nếu chưa từng
    có khối xác nhận đầy đủ nào trong lịch sử.
    """
    locked_info = None

    for m in messages:
        if m.sender_type == "customer":
            continue  # chỉ quét message của bot/assistant

        content = m.content or ""
        if "Họ tên:" not in content or "Số điện thoại:" not in content:
            continue  # bỏ qua nhanh nếu chắc chắn không phải khối xác nhận

        extracted = {}
        for key, pattern in _FIELD_PATTERNS.items():
            match = pattern.search(content)
            if match:
                # bỏ dấu câu/khoảng trắng thừa ở cuối, vd "Hà Nội." -> "Hà Nội"
                extracted[key] = match.group(1).strip().rstrip(".:")

        if all(key in extracted and extracted[key] for key in _REQUIRED_FIELDS):
            locked_info = extracted  # ghi đè -> luôn giữ khối MỚI NHẤT tìm thấy

    return locked_info


def _format_lock_note(locked_info: Dict[str, str]) -> str:
    return (
        "[TRẠNG THÁI NỘI BỘ - THÔNG TIN KHÁCH HÀNG ĐÃ KHÓA, KHÔNG PHẢI LỜI THOẠI]\n"
        f"ten: {locked_info['ten']}\n"
        f"sdt: {locked_info['sdt']}\n"
        f"nhu_cau (theo lần xác nhận gần nhất): {locked_info['nhu_cau']}\n"
        "Các trường ten/sdt ở trên ĐÃ ĐƯỢC KHÁCH XÁC NHẬN TRƯỚC ĐÓ.\n"
        "TUYỆT ĐỐI KHÔNG hỏi lại tên, số điện thoại dưới bất kỳ "
        "hình thức nào — kể cả khi khách chào lại 'alo', hỏi 'tôi tên gì', đổi "
        "gói vay, hoặc có vẻ như đang bắt đầu một cuộc trò chuyện mới. hoặc bất kỳ câu hỏi nào  TRẢ LỜI TRỰC TIẾP bằng giá trị ở "
        "trên, không hỏi ngược lại. Chỉ được cập nhật 1 trong các trường này nếu "
        "khách CHỦ ĐỘNG báo rõ ràng thông tin đó bị sai và cần sửa."
    )


def _build_history(messages: List["Message"]) -> List[dict]:
    """messages phải theo thứ tự cũ -> mới trước khi gọi hàm này."""
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    locked_info = _extract_locked_info(messages)

    for m in messages:
        role = "user" if m.sender_type == "customer" else "assistant"
        history.append({"role": role, "content": m.content})

    if locked_info:
        lock_note = {"role": "system", "content": _format_lock_note(locked_info)}

        insert_at = max(len(history) - 1, 1)
        history.insert(insert_at, lock_note)

    return history


def _is_unanswered(messages: List["Message"]) -> bool:
    """Return whether the latest message in an old-to-new history is from a customer."""
    if not messages:
        return False
    return messages[-1].sender_type == "customer"


async def _generate_reply(messages: List["Message"]) -> str:
    completion = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=_build_history(messages),
        temperature=0.7,
    )
    return completion.choices[0].message.content or FALLBACK_REPLY

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
        db, conversation_id=convo.id, limit=100, offset=0
    )

    history_messages = list(reversed(history_messages))

    # 4. Gọi OpenAI (có xử lý lỗi)
    try:
        reply_text = await _generate_reply(history_messages)
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


async def process_unanswered_conversation(
    db: AsyncSession, convo
) -> dict[str, str | int]:
    """Generate, send, and persist one reply for an unanswered conversation."""
    _, history_messages = await list_messages(
        db, conversation_id=convo.id, limit=100, offset=0
    )
    history_messages = list(reversed(history_messages))
    if not _is_unanswered(history_messages):
        return {"status": "skipped", "reason": "conversation đã được trả lời"}

    if not convo.external_conversation_id or not convo.channel_account_id:
        return {"status": "skipped", "reason": "conversation thiếu cấu hình Facebook"}

    account = await get_channel_account(db, convo.channel_account_id)
    if not account or account.status != 1:
        return {"status": "skipped", "reason": "Facebook channel account không hợp lệ"}
    if not account.external_page_id or not account.access_token:
        return {"status": "skipped", "reason": "thiếu external_page_id hoặc access_token"}

    reply_text = await _generate_reply(history_messages)
    external_message_id = await send_facebook_text(
        page_id=account.external_page_id,
        access_token=account.access_token,
        recipient_id=convo.external_conversation_id,
        text=reply_text,
    )
    await upsert_message(
        db,
        MessageCreate(
            conversation_id=convo.id,
            external_message_id=external_message_id,
            sender_type="bot",
            sender_id="0",
            message_direction=1,
            message_type="text",
            content=reply_text,
            status=1,
        ),
    )
    return {"status": "replied", "reply": reply_text}


async def reply_unanswered_messages(
    db: AsyncSession, limit: int = 100
) -> dict:
    conversations = await list_unanswered_conversations(db, limit=limit)
    result = {
        "scanned": len(conversations),
        "replied": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }

    for convo in conversations:
        try:
            outcome = await process_unanswered_conversation(db, convo)
        except Exception as exc:
            logger.exception(
                "Failed to reply to unanswered conversation_id=%s", convo.id
            )
            result["failed"] += 1
            result["errors"].append(
                {"conversation_id": convo.id, "reason": str(exc)}
            )
            continue

        if outcome["status"] == "replied":
            result["replied"] += 1
        else:
            result["skipped"] += 1

    return result
