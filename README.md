## 🛠️ Nếu gặp lỗi không thể cài đặt `llama-cpp-python` khi chạy `uv sync`

Khi thiết lập dự án trên môi trường **Windows**, lệnh `uv sync` hoặc `uv add llama-cpp-python` có thể thất bại do hệ thống thiếu trình biên dịch C++ hoặc gặp lỗi tìm kiếm đường dẫn cấu hình CMake (`CMAKE_C_COMPILER not set` hoặc `Generator could not find any instance of Visual Studio`).

Dưới đây là các bước xử lý:

### Cách 1: Cài đặt bộ trình biên dịch C++ chuẩn (Khuyên dùng)

Lỗi này xảy ra vì `llama-cpp-python` yêu cầu biên dịch mã nguồn thô sang mã máy. Hãy cài đặt bộ công cụ biên dịch chính thức từ Microsoft để dùng CMake.

1. Mở **PowerShell với quyền Quản trị viên** (Run as administrator).
2. Chạy lệnh gỡ sạch các cấu hình lỗi cũ (nếu có):
   ```powershell
   & "C:\Program Files (x86)\Microsoft Visual Studio\Installer\InstallCleanup.exe" -f
   ```
3. Chạy lệnh cài đặt bộ **Visual Studio Build Tools 2022** chuẩn hệ thống:
   ```powershell
   winget install --id Microsoft.VisualStudio.2022.BuildTools --override "--passive --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.CMake.Project"
   ```
4. Tắt hoàn toàn và mở lại Terminal để hệ thống cập nhật biến môi trường (`Environment Path`).
5. Kích hoạt môi trường ảo và đồng bộ lại dự án:
   ```powershell
   .venv\Scripts\activate
   uv sync
   ```
