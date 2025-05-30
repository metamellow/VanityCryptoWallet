import asyncio
import json
import multiprocessing
import secrets
from typing import List, Dict
from fastapi import FastAPI, WebSocket
from eth_account import Account
import uvicorn
from concurrent.futures import ProcessPoolExecutor
import time

app = FastAPI()
Account.enable_unaudited_hdwallet_features()

def generate_wallet():
    """Generate a random Ethereum wallet"""
    private_key = secrets.token_bytes(32)
    account = Account.from_key(private_key)
    mnemonic = Account.create().key_path
    return account.address, mnemonic

def check_address(address: str, patterns: List[str], start_end_only: bool, uppercase_only: bool) -> bool:
    """Check if address matches any of the patterns"""
    check_address = address if uppercase_only else address.lower()
    
    for pattern in patterns:
        check_pattern = pattern if uppercase_only else pattern.lower()
        if start_end_only:
            start = check_address[2:2 + len(check_pattern)]
            end = check_address[-len(check_pattern):]
            if start == check_pattern and end == check_pattern:
                return True
        elif check_pattern in check_address:
            return True
    return False

async def wallet_generator(patterns: List[str], start_end_only: bool, uppercase_only: bool):
    """Generate wallets and check for matches"""
    attempts = 0
    last_report_time = time.time()
    attempts_this_second = 0
    
    while True:
        attempts += 1
        attempts_this_second += 1
        current_time = time.time()
        
        address, mnemonic = generate_wallet()
        
        if check_address(address, patterns, start_end_only, uppercase_only):
            return {
                "found": True,
                "address": address,
                "mnemonic": mnemonic,
                "attempts": attempts
            }
            
        if current_time - last_report_time >= 1:
            yield {
                "attempts": attempts_this_second,
                "total": attempts
            }
            last_report_time = current_time
            attempts_this_second = 0

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        try:
            data = await websocket.receive_text()
            params = json.loads(data)
            
            patterns = params["patterns"]
            start_end_only = params["startEndOnly"]
            uppercase_only = params["uppercaseOnly"]
            num_workers = params["numWorkers"]
            
            async for result in wallet_generator(patterns, start_end_only, uppercase_only):
                if await websocket.send_json(result):
                    if "found" in result:
                        break
                        
        except Exception as e:
            print(f"Error: {e}")
            await websocket.close()
            break

if __name__ == "__main__":
    uvicorn.run("wallet_generator:app", host="0.0.0.0", port=8000, reload=True) 