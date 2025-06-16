import os
import re
import logging
import tempfile
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest
import win32api
import win32file

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('usb_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cấu hình bảo mật
ALLOWED_DRIVES = ['D:', 'E:', 'F:', 'G:', 'H:', 'I:', 'J:', 'K:', 'L:', 'M:', 'N:', 'O:', 'P:']
DRIVE_PATTERN = re.compile(r'^[D-P]:$')

def validate_drive_letter(drive_letter):
    """Kiểm tra tính hợp lệ của ký tự ổ đĩa"""
    if not drive_letter:
        raise ValueError("Drive letter không được để trống")
    
    drive_letter = drive_letter.upper().strip()
    
    if not DRIVE_PATTERN.match(drive_letter):
        raise ValueError("Drive letter không hợp lệ. Chỉ cho phép D: đến P:")
    
    if drive_letter not in ALLOWED_DRIVES:
        raise ValueError(f"Drive {drive_letter} không được phép")
    
    return drive_letter

def is_removable_drive(drive_letter):
    """Kiểm tra xem ổ đĩa có phải là ổ di động không"""
    try:
        drive_type = win32file.GetDriveType(drive_letter + '\\')
        # DRIVE_REMOVABLE = 2, DRIVE_FIXED = 3
        return drive_type == 2
    except Exception as e:
        logger.error(f"Không thể kiểm tra loại ổ đĩa {drive_letter}: {e}")
        return False

def drive_exists(drive_letter):
    """Kiểm tra xem ổ đĩa có tồn tại không"""
    try:
        drives = win32api.GetLogicalDriveStrings()
        drive_list = [d.rstrip('\\') for d in drives.split('\x00') if d]
        return drive_letter in drive_list
    except Exception as e:
        logger.error(f"Không thể kiểm tra sự tồn tại của ổ đĩa {drive_letter}: {e}")
        return False

def safe_disconnect_usb(drive_letter):
    """Ngắt kết nối USB một cách an toàn"""
    try:
        # Tạo file script tạm thời an toàn
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            script_content = f"select volume {drive_letter}\nremove\nexit\n"
            temp_file.write(script_content)
            script_path = temp_file.name
        
        logger.info(f"Tạo script tạm thời: {script_path}")
        
        # Thực thi diskpart với timeout
        result = subprocess.run(
            ["diskpart", "/s", script_path],
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        
        logger.info(f"Diskpart output: {result.stdout}")
        
        return True, f"Drive {drive_letter} đã được ngắt kết nối thành công"
        
    except subprocess.TimeoutExpired:
        error_msg = f"Timeout khi ngắt kết nối {drive_letter}"
        logger.error(error_msg)
        return False, error_msg
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Lỗi diskpart cho {drive_letter}: {e.stderr}"
        logger.error(error_msg)
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Lỗi không xác định khi ngắt kết nối {drive_letter}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
        
    finally:
        # Xóa file script tạm thời
        try:
            if 'script_path' in locals():
                os.unlink(script_path)
                logger.info(f"Đã xóa script tạm thời: {script_path}")
        except Exception as e:
            logger.warning(f"Không thể xóa file tạm thời {script_path}: {e}")

@app.route('/disconnect_usb', methods=['POST'])
def disconnect_usb():
    """API endpoint để ngắt kết nối USB"""
    try:
        # Kiểm tra Content-Type
        if not request.is_json:
            raise BadRequest("Content-Type phải là application/json")
        
        data = request.get_json()
        if not data:
            raise BadRequest("Dữ liệu JSON không hợp lệ")
        
        drive_letter = data.get('drive')
        if not drive_letter:
            raise BadRequest("Thiếu tham số 'drive'")
        
        # Validate drive letter
        try:
            drive_letter = validate_drive_letter(drive_letter)
        except ValueError as e:
            logger.warning(f"Drive letter không hợp lệ: {e}")
            return jsonify({"error": str(e)}), 400
        
        # Kiểm tra ổ đĩa có tồn tại không
        if not drive_exists(drive_letter):
            error_msg = f"Drive {drive_letter} không tồn tại"
            logger.warning(error_msg)
            return jsonify({"error": error_msg}), 404
        
        # Kiểm tra có phải ổ di động không
        if not is_removable_drive(drive_letter):
            error_msg = f"Drive {drive_letter} không phải là ổ di động"
            logger.warning(error_msg)
            return jsonify({"error": error_msg}), 400
        
        # Thực hiện ngắt kết nối
        logger.info(f"Bắt đầu ngắt kết nối drive {drive_letter}")
        success, message = safe_disconnect_usb(drive_letter)
        
        if success:
            return jsonify({"status": "success", "message": message}), 200
        else:
            return jsonify({"error": message}), 500
            
    except BadRequest as e:
        logger.warning(f"Bad request: {e}")
        return jsonify({"error": str(e)}), 400
        
    except Exception as e:
        error_msg = f"Lỗi server không xác định: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": "Lỗi server nội bộ"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "USB Disconnect Service"}), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint không tồn tại"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Phương thức không được phép"}), 405

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Lỗi server nội bộ"}), 500

if __name__ == '__main__':
    logger.info("Khởi động USB Disconnect Service...")
    
    # Cấu hình production
    app.run(
        host='127.0.0.1',  # Chỉ cho phép kết nối local
        port=5001,
        debug=False,  # Tắt debug mode trong production
        threaded=True
    )
