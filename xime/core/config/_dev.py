"""`xime.dev` - MỘT công tắc cho mọi bề mặt chỉ dành cho môi trường phát triển.

One switch, one question: *is this a development environment?* Everything the
framework only serves to developers hangs off this single answer, so an operator
never has to find and flip a list of them one by one, and never has to remember
which ones exist.
Một công tắc, một câu hỏi: *đây có phải môi trường phát triển không?* Mọi thứ
framework chỉ phục vụ cho người phát triển đều treo vào đúng câu trả lời này, nên
người vận hành không phải đi tìm và gạt từng cái, cũng không phải nhớ có những cái
nào.

    # resources/application-local.yml
    xime:
      dev: true

**Mặc định TẮT, muốn thì phải bật lên.** A development-only surface that ships
enabled is one nobody remembers to turn off, because nothing goes wrong when they
forget - the cost lands somewhere else, later, on someone else.
**Mặc định TẮT, muốn thì phải bật lên.** Một bề mặt chỉ dành cho dev mà lại xuất
xưởng ở trạng thái bật là thứ không ai nhớ tắt, vì quên thì chẳng có gì hỏng cả -
cái giá rơi vào chỗ khác, muộn hơn, và vào người khác.

### Vì sao là YAML chứ không phải một hàm `configure_*`

Phép phân loại của `rules/config-discovery.md`: *người vận hành có ĐỦ THÔNG TIN để
chọn giá trị này không?* Ở đây câu trả lời rõ ràng là **có** - họ là bên duy nhất
biết máy này đang chạy vai gì. Cùng nhóm với `server.ssl`, khác nhóm với những
quyết định kiến trúc mà chỉ người viết ứng dụng mới trả lời được.

### ⚠ Vì sao KHÔNG suy ra từ tên profile

`XIME_ENV`/`APP_ENV` chọn *file* nào được nạp, và tên profile là do ứng dụng tự
đặt: `local`, `dev`, `sandbox`, `staging`, `qa`, hay một cái tên nội bộ nào đó.
Suy từ tên ra thì framework phải giữ một danh sách tên "được coi là dev", và cái
danh sách đó **sai với mọi người không dùng đúng từ vựng của nó** - im lặng, và
theo chiều nguy: một profile tên `development-2` không khớp danh sách sẽ trông
hệt như production đối với một phép dò, còn một profile tên `dev-mirror-of-prod`
thì ngược lại. Một khoá tường minh không có chỗ nào để đoán sai.
"""

from __future__ import annotations

from xime.core.config.runtime import RuntimeConfig

__all__ = ["DEV_KEY", "is_dev_mode"]

#: Khoá duy nhất trả lời câu hỏi này. Đổi tên nó là đổi API công khai.
DEV_KEY = "xime.dev"


def is_dev_mode(config: RuntimeConfig | None) -> bool:
    """True khi ứng dụng khai `xime.dev: true`.

    Anything that is not a real RuntimeConfig answers **False**, and that is the
    safe direction on purpose: *"I could not read a configuration"* must never
    come out as *"development, go ahead and expose things"*. It is the same
    fail-closed rule the security layer follows when an identity is missing.
    Thứ gì không phải RuntimeConfig thật thì trả **False**, và đó là chiều an toàn
    có chủ ý: *"tôi không đọc được cấu hình"* không bao giờ được ra thành *"đang ở
    dev, cứ mở ra đi"*. Cùng luật fail-closed mà tầng bảo mật đang theo khi thiếu
    danh tính.

    Giá trị không phải boolean nhận dạng được thì `get_bool` **nổ lúc khởi động**
    chứ không đoán - viết `xime.dev: "false"` mà nhận về True là đúng thứ cờ này
    tồn tại để tránh.
    """
    if not isinstance(config, RuntimeConfig):
        return False
    return config.get_bool(DEV_KEY, False)
