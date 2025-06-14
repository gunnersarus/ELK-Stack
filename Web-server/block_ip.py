from flask import Flask, request, jsonify
import subprocess
import logging
import ipaddress
import os
from datetime import datetime

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('security.log'),
        logging.StreamHandler()
    ]
)

def validate_ip(ip_str):
    """Validate IP address format"""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False

def is_private_ip(ip_str):
    """Check if IP is private/local"""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False

@app.route('/security/block', methods=['POST'])
def block_threat():
    """Block detected malicious IP addresses"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        detected_ip = data.get('detected_ip')
        threat_type = data.get('threat_type', 'unknown')
        severity = data.get('severity', 'medium')
        
        if not detected_ip:
            logging.warning("Block request received without IP address")
            return jsonify({'status': 'error', 'message': 'No IP provided'}), 400
        
        # Validate IP format
        if not validate_ip(detected_ip):
            logging.warning(f"Invalid IP format received: {detected_ip}")
            return jsonify({'status': 'error', 'message': 'Invalid IP format'}), 400
        
        # Prevent blocking private/local IPs
        if is_private_ip(detected_ip):
            logging.warning(f"Attempt to block private IP: {detected_ip}")
            return jsonify({'status': 'error', 'message': 'Cannot block private IP'}), 400
        
        # Log security event
        logging.info(f"🛡️  SECURITY ALERT: Blocking IP {detected_ip} - Threat: {threat_type} - Severity: {severity}")
        
        # Execute blocking script with error handling
        script_path = './block_ip.sh'
        if not os.path.exists(script_path):
            logging.error("Block script not found")
            return jsonify({'status': 'error', 'message': 'Block script not available'}), 500
        
        try:
            result = subprocess.run(
                ['sudo', script_path, detected_ip], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode == 0:
                logging.info(f"✅ Successfully blocked IP: {detected_ip}")
                return jsonify({
                    'status': 'success', 
                    'blocked_ip': detected_ip,
                    'threat_type': threat_type,
                    'timestamp': datetime.now().isoformat()
                }), 200
            else:
                logging.error(f"Failed to block IP {detected_ip}: {result.stderr}")
                return jsonify({'status': 'error', 'message': 'Block operation failed'}), 500
                
        except subprocess.TimeoutExpired:
            logging.error(f"Timeout while blocking IP: {detected_ip}")
            return jsonify({'status': 'error', 'message': 'Block operation timed out'}), 500
        except Exception as e:
            logging.error(f"Exception during block operation: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Internal error'}), 500
            
    except Exception as e:
        logging.error(f"Unexpected error in block_threat: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@app.route('/security/status', methods=['GET'])
def security_status():
    """Get security service status"""
    return jsonify({
        'status': 'active',
        'service': 'IP Blocking Service',
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    logging.info("🚀 Starting Security IP Blocking Service...")
    app.run(host='0.0.0.0', port=5000, debug=False)
