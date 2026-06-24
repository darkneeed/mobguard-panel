import paramiko
import json

def run_ssh_command(cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("77.91.85.216", username="root", password="6fRFE_7!3@56aXZ")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    ssh.close()
    return out, err

py_cmd = """
import sys
sys.path.append('/app')
from api.context import build_container
container = build_container()
case = container.store.get_review_case(2995)
import json
print(json.dumps(case, indent=2, default=str))
"""

import base64
b64_py = base64.b64encode(py_cmd.encode('utf-8')).decode('utf-8')
out_py, err_py = run_ssh_command(f"docker exec mobguard-api python -c \"import base64; exec(base64.b64decode('{b64_py}').decode('utf-8'))\"")
print("=== API DATA ===")
print(out_py)
if err_py:
    print("=== API ERR ===")
    print(err_py)

