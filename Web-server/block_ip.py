from flask import Flask, request
import subprocess

app = Flask(__name__)


@app.route('/', methods=['POST'])
def block_ip():
    data = request.get_json()
    print("Received data", data)
    ip = data.get('detected_ip')
    
    if ip:
         #Block bang iptable
       subprocess.call(['sudo', './block_ip.sh', ip])
       print(f'Blocked ip: {ip}')
       return{'status': 'success', 'blocked ip': ip}, 200
    return{'status': 'fail', 'reason': 'no ip provided'}, 400


if __name__== '__main__':
   app.run(host='0.0.0.0', port=5000)
