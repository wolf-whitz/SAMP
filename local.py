# Run this if you are using this locally or even in cloud, This work both in colab as well, and will spin up the fastapi server + allocate a url automatically

import os
import subprocess
import signal
import time
import requests
import shutil
import sys
import psutil

base_dir = "/content" if os.path.exists("/content") else "/home"
print(f"Using base directory: {base_dir}")
os.chdir(base_dir)

if os.path.exists("SAMP"):
    print("SAMP folder found, using existing copy.")
else:
    print("SAMP folder not found, cloning repository...")
    subprocess.run(["git", "clone", "https://github.com/wolf-whitz/SAMP.git"], check=True)

os.chdir("SAMP")
print(f"Current directory: {os.getcwd()}")

requirements_file = "requirements.txt"
print("Checking required Python packages...")
with open(requirements_file) as f:
    packages = [line.strip() for line in f if line.strip() and not line.startswith("#")]

for pkg in packages:
    try:
        subprocess.run([sys.executable, "-m", "pip", "show", pkg], check=True, stdout=subprocess.DEVNULL)
        print(f"{pkg} already installed.")
    except subprocess.CalledProcessError:
        print(f"{pkg} not found, installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)

if shutil.which("cloudflared"):
    print("cloudflared already installed.")
else:
    print("Downloading cloudflared...")
    deb_file = "cloudflared-linux-amd64.deb"
    subprocess.run(["wget", "-q", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"], check=True)
    subprocess.run(["sudo", "dpkg", "-i", deb_file], check=True)

print("Checking for existing uvicorn processes...")
try:
    result = subprocess.run(["pgrep", "-f", "uvicorn"], capture_output=True, text=True)
    pids = [int(pid) for pid in result.stdout.strip().split("\n") if pid]
    for pid in pids:
        os.kill(pid, signal.SIGTERM)
    if pids:
        print(f"Killed existing uvicorn processes: {pids}")
    else:
        print("No uvicorn processes running.")
except Exception as e:
    print("Error checking uvicorn processes:", e)

try:
    import torch
    gpu_available = torch.cuda.is_available()
except ImportError:
    gpu_available = False

total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
print(f"Total system RAM: {total_ram_gb} GB")
if gpu_available:
    print(f"GPU detected: {torch.cuda.get_device_name(0)}")
    print("The model will use GPU acceleration for faster inference.")
else:
    print("No GPU detected, running on CPU.")
    print("Warning: Model responses may be slower on CPU.")
    print("Recommended: Ensure you have enough RAM available for processing.")

print("Starting uvicorn server...")
log_file = "uvicorn.log"
f = open(log_file, "w")
process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"],
    stdout=f,
    stderr=f
)

for i in range(20):
    try:
        r = requests.get("http://localhost:8000")
        if r.status_code == 200:
            print("FastAPI is live!")
            break
    except:
        print("Waiting for FastAPI...")
        time.sleep(1)
else:
    print("Warning: FastAPI may not have started properly.")

print("\nStarting Cloudflare Tunnel...")
print("You will see a public URL like https://xxxx.trycloudflare.com")
cf_process = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://localhost:8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

for line in cf_process.stdout:
    print(line, end="")
