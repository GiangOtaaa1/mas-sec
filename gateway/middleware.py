import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Cấu hình logging bảo mật
logging.basicConfig(level=logging.INFO, format="[SECURITY AUDIT] %(asctime)s - %(message)s")
logger = logging.getLogger("GatewayAudit")

class SecurityAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host
        path = request.url.path
        method = request.method

        # Chặn hoặc ghi log các request đáng ngờ
        logger.info(f"Incoming Request | IP: {client_ip} | Method: {method} | Path: {path}")

        response = await call_next(request)

        process_time = time.time() - start_time
        logger.info(f"Response Status: {response.status_code} | Duration: {process_time:.4f}s")

        # Thêm header bảo mật phản hồi
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response