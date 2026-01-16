# Web Cloner Pro - Công cụ Clone Website & Landing Page

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

Web Cloner Pro là công cụ mạnh mẽ giúp tải toàn bộ mã nguồn website (HTML, CSS, JS, Images, Fonts, Media) về máy tính để chạy offline hoặc deploy lên server riêng. Đặc biệt tối ưu cho việc clone các Landing Page (LadiPage) và thay thế form submission.

## 🚀 Tính năng nổi bật

- **Clone toàn diện**: Tải sạch sẽ index.html và toàn bộ tài nguyên tĩnh (css, js, images, fonts, video).
- **Offline Mode**: Tự động sửa lại đường dẫn trong HTML/CSS để website chạy mượt mà không cần internet.
- **Clean Source**:
  - Loại bỏ các mã theo dõi (tracking), pixel facebook/google không cần thiết.
  - Loại bỏ preconnect/dns-prefetch tới server gốc.
  - Tự động thay thế các link CDN bằng file local.
- **Form Handler**: Tự động inject script để override form của LadiPage, gửi dữ liệu về API riêng (Cloudflare Workers, Telegram, Google Sheets...) thay vì server LadiPage.
- **Giao diện đồ họa (GUI)**: Dễ sử dụng, không cần gõ lệnh.
- **Thông minh**: Tự động đặt tên thư mục theo domain, tự động xử lý độ sâu (depth).

## 🛠 Cài đặt

### Yêu cầu
- Python 3.8 trở lên
- pip

### Cài đặt thư viện
```bash
pip install requests beautifulsoup4
# Nếu muốn build exe
pip install pyinstaller
```

## 📖 Hướng dẫn sử dụng

### Cách 1: Dùng giao diện (Khuyên dùng)
Chạy file giao diện:
```bash
python web_cloner_ui.py
```
1. Nhập **URL Website** cần clone.
2. Chọn **Thư mục Output** (Tool sẽ tự tạo thư mục con theo tên miền).
3. Chọn **Độ sâu** (Mặc định là 4 để lấy kỹ resource).
4. Bấm **BẮT ĐẦU CLONE**.

### Cách 2: Dùng dòng lệnh (Cho developer)
```bash
python web_cloner.py https://example.com -o my_folder -d 4
```

### Cách 3: Dùng file EXE (Cho khách hàng)
Chỉ cần mở file `WebClonerPro.exe` và sử dụng như Cách 1.

## 📦 Build file EXE (Cho Developer)

Để đóng gói thành file `.exe` chạy trên Windows không cần cài Python:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "WebClonerPro" --hidden-import "bs4" --hidden-import "requests" web_cloner_ui.py
```
File kết quả sẽ nằm trong thư mục `dist/WebClonerPro.exe`.

## ⚙️ Cấu hình Form Handler (Nâng cao)

File `check_ladicdn.py` và `cloned_site/js/custom-form-handler.js` chứa logic xử lý form.
Để đổi API endpoint nhận dữ liệu, sửa file `js/custom-form-handler.js` trong thư mục output sau khi clone:

```javascript
const ENDPOINT_URL = 'https://your-api-endpoint.com/submit';
```

## 📝 Changelog

- **v1.0.0**: Release đầu tiên.
- **v1.1.0**: Thêm GUI, fix lỗi CDN LadiPage, thêm Custom Form Handler.
- **v1.2.0**: Auto-name folder, tăng depth mặc định lên 4.

## 🤝 Đóng góp

Mọi đóng góp (Pull Request) đều được hoan nghênh.
Vui lòng mở Issue nếu bạn gặp lỗi.

---
*Developed by [Your Name]*
