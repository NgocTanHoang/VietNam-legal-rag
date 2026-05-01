# Bước 1: Sử dụng Python image bản nhẹ (slim) để giảm dung lượng file
FROM python:3.10-slim

# Bước 2: Thiết lập thư mục làm việc bên trong container
WORKDIR /app

# Bước 3: Cài đặt các thư viện hệ thống cần thiết (đặc biệt cho các thư viện Python cần biên dịch)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Bước 4: Copy file requirements.txt vào trước để tận dụng Docker Cache
# Giúp các lần build sau nhanh hơn nếu bạn không thay đổi thư viện
COPY requirements.txt .

# Bước 5: Cài đặt các thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Bước 6: Copy toàn bộ mã nguồn từ máy của bạn vào container
COPY . .

# Bước 7: Thiết lập biến môi trường để Python không tạo file .pyc và log được in ra ngay lập tức
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Bước 8: Mở cổng 8000 (cổng mặc định của FastAPI)
EXPOSE 8000

# Bước 9: Lệnh để chạy ứng dụng khi container khởi động
# Sử dụng uvicorn để chạy FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]