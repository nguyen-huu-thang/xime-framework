from __future__ import annotations

from xime.core.exception.framework import XimeException


class RefDataError(XimeException):
    """Lỗi của kho tham chiếu liên tiến trình.

    Báo bằng **ngoại lệ** chứ không phải một kết cục trong kiểu trả về, cùng lý
    do đã chốt cho `Store`: quên bắt một ngoại lệ thì request hỏng và ai cũng
    thấy, còn quên một nhánh của kiểu trả về là hỏng **im lặng**.
    """


class RefDataNotReadyError(RefDataError):
    """`read_or_fail()` được gọi trước khi có ai publish bản nào.

    Tách riêng vì nó đòi một hành động khác hẳn: không phải đi sửa gì, mà là
    **đợi** - primary chưa kịp publish lần đầu. Đợi là một lời gọi riêng
    (`wait_ready`), đặt ở tầng khởi động, không đặt trên đường phục vụ.

    Tiền lệ: `EntityNotFoundError` của `CrudRepository.find_or_fail`.
    """


class RefDataTooLargeError(RefDataError):
    """Bản vừa publish không vừa trong `max_bytes` đã khai.

    ⚠ Vượt trần ở đây **nguy hơn ở bus**, và đó là lý do nó có lớp riêng: bus
    làm mất **một tin**, còn ở đây primary không publish được nghĩa là **cả cụm
    dùng bản cũ mãi mãi** - khoá JWT đã xoay mà mọi tiến trình vẫn verify bằng
    khoá cũ, và **không request nào lỗi** cho tới khi token ký bằng khoá mới
    xuất hiện.

    Bản **cũ được giữ nguyên**: một bản cũ đúng còn hơn một bản mới rách.
    """


class RefDataNotWriterError(RefDataError):
    """`publish()` gọi từ tiến trình không giữ quyền ghi.

    Cơ chế hai bản chỉ đúng với **đúng một người ghi**. Hai người cùng dựng bản
    mới vào ô trống là hỏng, và **hỏng im lặng** - nên đây là ngoại lệ chứ
    không phải một dòng log rồi bỏ qua. Cùng khuôn `nguoi_nhan` của bus.
    """


class RefDataTornError(RefDataError):
    """Đọc lặp lại quá trần mà vẫn không lấy được một bản nhất quán.

    ⭐ Trần tồn tại **không phải để xử lý ca thường**: có hai bản A/B nên người
    đọc và người ghi gần như không bao giờ đụng nhau, và lặp quá một vòng đã là
    chuyện hiếm. Nó tồn tại vì **không có trần thì một lỗi lạ biến thành request
    treo vô hạn, không log, không triệu chứng**. Có trần thì nó thành một ngoại
    lệ chỉ đúng chỗ.
    """


class RefDataClosedError(RefDataError):
    """Bảng được dùng sau khi arena đã đóng.

    Có lớp riêng vì nó đòi một hành động khác hẳn mọi lỗi kia: không phải sửa
    dữ liệu, không phải nâng trần, mà là **sửa vòng đời** - ai đó giữ một bảng
    sống lâu hơn vùng nhớ của nó.

    ⚠ Nó tồn tại **chỉ để thông báo nói đúng chỗ sai**. Không có nó thì lời gọi
    sau khi tắt cho một `ValueError: operation forbidden on released
    memoryview` - đúng loại lỗi không ai lần ra được nguyên nhân.
    """


class RefDataLayoutMismatch(RefDataError):
    """Vùng nhớ chung không mang đúng khuôn tiến trình này chờ đợi.

    ⚠⚠ **Tiền tố `RefData` là cố ý, đừng rút gọn lại thành `LayoutMismatch`.**
    Bus liên tiến trình có một lỗi cùng bản chất, và trước 0.8.0 **cả hai cùng
    tên**, cùng là lớp con trực tiếp của `Exception`, ở hai package công khai -
    nên nhập cả hai vào một module là một cái che mất cái kia, im lặng. Luật 03
    ở tầng từ vựng: một tên mang hai nghĩa.

    Bản cũ còn kế thừa thẳng `Exception`, nên `except RefDataError:` - lớp nền
    của chính package này - không bắt được nó.
    """
