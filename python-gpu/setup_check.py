import subprocess
import sys

def check_command(command):
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except:
        return False

def check_python_package(package):
    try:
        __import__(package)
        return True
    except ImportError:
        return False

def main():
    print("Checking system requirements for GPU Wallet Generator...")

    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
        print("WARNING: Python 3.7+ is required.")
    else:
        print("Python version requirement met.")

    # Check for CUDA
    cuda_available = check_command(["nvcc", "--version"])
    print(f"CUDA available: {'Yes' if cuda_available else 'No'}")
    if not cuda_available:
        print("WARNING: CUDA is not detected. Please install CUDA toolkit.")

    # Check for required Python packages
    packages = ['cupy', 'numpy', 'eth_account']
    for package in packages:
        installed = check_python_package(package)
        print(f"{package} installed: {'Yes' if installed else 'No'}")
        if not installed:
            print(f"WARNING: {package} is not installed. Please install it using pip.")

    print("\nSetup check complete. Please address any warnings before proceeding.")

if __name__ == "__main__":
    main()