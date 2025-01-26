# python gpu_wallet_generator.py

import sys
import time
import signal
import subprocess
import hashlib
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from mnemonic import Mnemonic

# Performance Tuning Variables
USE_LOW_POWER = False
BATCH_SIZE = 10000
CHUNK_SIZE = 1000  # Process in chunks of this size or less
SLEEP_TIME = 0.00001  # Sleep time in seconds
CPU_BUFFER = 4  # Number of CPU cores to leave as buffer

# Calculate CPU threads
total_cpus = multiprocessing.cpu_count()
CPU_THREADS = max(total_cpus - CPU_BUFFER, 1) if not USE_LOW_POWER else max(min(4, total_cpus), 1)

# Wallet Generation Configuration
USE_START_OR_END_STRING = False
USE_START_AND_END_STRING = True
CASE_INSENSITIVE = False

# Define acceptable words
WORDS = [
    "C0FFEE", "B00BIE",
    "C0DE", "B00B", "DEAD", "D00D", "FACE", "BABE", "BEEF", "F00D", 
    "69696969", "420420420",
]

# Required Python packages
REQUIRED_PACKAGES = ['cupy', 'numpy', 'coincurve', 'mnemonic']

# Apply low power mode if enabled
if USE_LOW_POWER:
    BATCH_SIZE = max(int(BATCH_SIZE * 0.2), 1)
    CHUNK_SIZE = max(int(CHUNK_SIZE * 0.2), 1)
    SLEEP_TIME = SLEEP_TIME * 5  # Increase sleep time in low power mode

# Derived variables
if CASE_INSENSITIVE:
    WORDS = [word.lower() for word in WORDS]
MAX_WORD_LENGTH = max(len(word) for word in WORDS)

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

def setup_check():
    print("Checking system requirements for GPU Wallet Generator...")

    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
        print("ERROR: Python 3.7+ is required.")
        return False

    # Check for CUDA
    cuda_available = check_command(["nvcc", "--version"])
    print(f"CUDA available: {'Yes' if cuda_available else 'No'}")
    if not cuda_available:
        print("ERROR: CUDA is not detected. Please install CUDA toolkit.")
        return False

    # Check for required Python packages
    missing_packages = []
    for package in REQUIRED_PACKAGES:
        installed = check_python_package(package)
        print(f"{package} installed: {'Yes' if installed else 'No'}")
        if not installed:
            missing_packages.append(package)

    if missing_packages:
        print("\nERROR: The following packages are missing:")
        for package in missing_packages:
            print(f"- {package}")
        print("\nPlease install them using:")
        print(f"pip install {' '.join(missing_packages)}")
        return False

    print("\nAll requirements are met. Proceeding with wallet generation.")
    return True

# Only import these if setup check passes
if setup_check():
    import cupy as cp
    import numpy as np
    import coincurve
else:
    sys.exit(1)

# Prepare word data for GPU
word_array = np.array([list(word.encode()) + [0] * (MAX_WORD_LENGTH - len(word)) for word in WORDS], dtype=np.uint8)
d_words = cp.asarray(word_array)

# CUDA kernel for checking if address matches criteria
check_address_kernel = cp.ElementwiseKernel(
    'raw uint8 addresses, raw uint8 words, int32 num_words, int32 word_length, bool use_start_or_end, bool use_start_and_end, bool case_insensitive',
    'int32 match',
    '''
    bool found_match = false;
    for (int w = 0; w < num_words; w++) {
        bool start_match = true;
        bool end_match = true;
        for (int j = 0; j < word_length; j++) {
            if (words[w * word_length + j] == 0) break;  // End of word
            char start_addr_char = addresses[i * 40 + j];
            char end_addr_char = addresses[i * 40 + (39 - j)];
            char word_char = words[w * word_length + j];
            if (case_insensitive) {
                start_addr_char = (start_addr_char >= 'A' && start_addr_char <= 'Z') ? start_addr_char + 32 : start_addr_char;
                end_addr_char = (end_addr_char >= 'A' && end_addr_char <= 'Z') ? end_addr_char + 32 : end_addr_char;
                word_char = (word_char >= 'A' && word_char <= 'Z') ? word_char + 32 : word_char;
            }
            if (start_addr_char != word_char) start_match = false;
            if (end_addr_char != word_char) end_match = false;
            if ((!use_start_or_end && !use_start_and_end) || (use_start_and_end && (!start_match && !end_match)) || (use_start_or_end && !start_match && !end_match)) {
                break;
            }
        }
        if ((use_start_or_end && (start_match || end_match)) || (use_start_and_end && start_match && end_match)) {
            found_match = true;
            break;
        }
    }
    match = found_match ? 1 : 0;
    ''',
    'check_address_kernel'
)

def checksum_encode(addr):
    out = ''
    addr = addr.hex()
    addr_hash = hashlib.sha3_256(addr.encode('ascii')).hexdigest()
    for i, c in enumerate(addr):
        if int(addr_hash[i], 16) >= 8:
            out += c.upper()
        else:
            out += c.lower()
    return '0x' + out

def generate_ethereum_address(private_key):
    public_key = coincurve.PublicKey.from_valid_secret(private_key).format(compressed=False)[1:]
    addr = hashlib.sha3_256(public_key).digest()[-20:]
    return checksum_encode(addr)

def verify_address(address, words, use_start_or_end, use_start_and_end, case_insensitive):
    if case_insensitive:
        address = address.lower()
        words = [word.lower() for word in words]
    address = address[2:]  # Remove '0x'
    
    if use_start_and_end:
        for start_word in words:
            for end_word in words:
                if address.startswith(start_word) and address.endswith(end_word):
                    return True
    elif use_start_or_end:
        for word in words:
            if address.startswith(word) or address.endswith(word):
                return True
    
    return False

def generate_addresses_batch(private_keys):
    return [generate_ethereum_address(pk.tobytes()) for pk in private_keys]

def generate_wallets_gpu():
    found = False
    total_attempts = 0
    start_time = time.time()
    mnemo = Mnemonic("english")

    try:
        with ThreadPoolExecutor(max_workers=CPU_THREADS) as executor:
            while not found:
                d_random = cp.random.randint(0, 256, size=(BATCH_SIZE, 32), dtype=cp.uint8)
                h_private_keys = cp.asnumpy(d_random)

                future_to_chunk = {executor.submit(generate_addresses_batch, h_private_keys[i:i+CHUNK_SIZE]): i 
                                   for i in range(0, BATCH_SIZE, CHUNK_SIZE)}
                
                addresses = []
                for future in as_completed(future_to_chunk):
                    addresses.extend(future.result())

                d_addresses = cp.asarray(np.array([list(addr[2:].encode()) for addr in addresses], dtype=np.uint8))
                d_match = cp.zeros(BATCH_SIZE, dtype=cp.int32)
                check_address_kernel(d_addresses, d_words, len(WORDS), MAX_WORD_LENGTH, USE_START_OR_END_STRING, USE_START_AND_END_STRING, CASE_INSENSITIVE, d_match)

                match_indices = cp.nonzero(d_match)[0]
                if len(match_indices) > 0:
                    found = True
                    match_index = match_indices[0].get()
                    private_key = h_private_keys[match_index]
                    address = addresses[match_index]
                    try:
                        seed_phrase = mnemo.to_mnemonic(private_key.tobytes())
                    except Exception as e:
                        print(f"Error generating seed phrase: {e}")
                        seed_phrase = "Unable to generate seed phrase"
                    print(f"\nFound matching address: {address}")
                    print(f"Private key: {private_key.tobytes().hex()}")
                    print(f"Seed phrase: {seed_phrase}")
                    if verify_address(address, WORDS, USE_START_OR_END_STRING, USE_START_AND_END_STRING, CASE_INSENSITIVE):
                        print(f"CPU verification passed. Start: {address[2:2+len(WORDS[0])]}, End: {address[-len(WORDS[1]):]}")
                    else:
                        print(f"CPU verification failed. Address: {address}")
                    break

                total_attempts += BATCH_SIZE

                if total_attempts % (BATCH_SIZE * 10) == 0:
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    addresses_per_second = total_attempts / elapsed_time
                    print(f"Processed {total_attempts} addresses... ({addresses_per_second:.2f} addr/s)")

                time.sleep(SLEEP_TIME)

    except KeyboardInterrupt:
        print("\nScript interrupted by user. Cleaning up...")
    finally:
        end_time = time.time()
        print(f"\nTotal attempts: {total_attempts}")
        print(f"Total time: {end_time - start_time:.2f} seconds")
        print(f"Addresses checked per second: {total_attempts / (end_time - start_time):.2f}")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda x, y: sys.exit(0))

    print("Starting GPU Wallet Generator. Press Ctrl+C to stop.")
    print(f"Configuration:")
    print(f"  Low Power Mode: {USE_LOW_POWER}")
    print(f"  Batch Size: {BATCH_SIZE}")
    print(f"  Chunk Size: {CHUNK_SIZE}")
    print(f"  Sleep Time: {SLEEP_TIME:.6f}s")
    print(f"  CPU Threads: {CPU_THREADS} (out of {total_cpus} available)")
    print(f"  Use Start OR End String: {USE_START_OR_END_STRING}")
    print(f"  Use Start AND End String: {USE_START_AND_END_STRING}")
    print(f"  Case Insensitive: {CASE_INSENSITIVE}")
    print(f"  Search Pattern: {WORDS}")
    generate_wallets_gpu()