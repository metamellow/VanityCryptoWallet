// node generateWalletFromLibrary.js

const { ethers } = require("ethers");
const cluster = require('cluster');
const os = require('os');

// VARIABLES
const useHalfCores = true;
const useStartString = true;
const caseInsensitive = false;
const logFrequency = 1000;
const batchSize = 1000;

// WORDLIST
// Removed: BAD, DAD, 
const acceptableWords = [
    "AAAAA",
    "BBBBB", "BEEF", "B00B", "BABE",
    "CCCCC", "C0DE", "C0FFEE", "CODE", "CAFE",
    "DDDDD", "DEAD", "D00D",
    "EEEEE",
    "FFFFF", "F00D", "FEED", "FADE",
    "00000", "00420", "00069",
    "11111", "12345",
    "22222",
    "33333",
    "44444", "42069", "420420",
    "55555",
    "66666", "69420", "6969",
    "77777",
    "88888",
    "99999"
].map(word => caseInsensitive ? word.toLowerCase() : word);

const wordSet = new Set(acceptableWords);

const numCPUs = os.cpus().length;
const numWorkers = useHalfCores ? Math.ceil(numCPUs / 2) : numCPUs - 2;

if (cluster.isMaster) {
    console.log(`Master ${process.pid} is running with ${numWorkers} workers`);

    for (let i = 0; i < numWorkers; i++) {
        cluster.fork();
    }

    cluster.on('exit', (worker, code, signal) => {
        if (code === 0) {
            console.log(`Worker ${worker.process.pid} found the address and terminated.`);
            for (const id in cluster.workers) {
                cluster.workers[id].kill('SIGINT');
            }
        } else {
            console.log(`Worker ${worker.process.pid} died`);
        }
    });
} else {
    function spawnAddress() {
        let found = false;
        let attempts = 0;

        do {
            const batch = [];
            for (let i = 0; i < batchSize; i++) {
                const wallet = ethers.Wallet.createRandom();
                const address = caseInsensitive ? wallet.address.toLowerCase() : wallet.address;
                batch.push({ address, privateKey: wallet.privateKey });
            }

            for (const { address, privateKey } of batch) {
                attempts++;
                let match = false;

                if (useStartString) {
                    for (const word of wordSet) {
                        const addressStart = address.slice(2, 2 + word.length);
                        const addressEnd = address.slice(-word.length);
                        if (wordSet.has(addressStart) && wordSet.has(addressEnd)) {
                            match = true;
                            break;
                        }
                    }
                } else {
                    for (const word of wordSet) {
                        const adjustedEnd = 'a' + word;
                        if (address.endsWith(adjustedEnd)) {
                            match = true;
                            break;
                        }
                    }
                }

                if (match) {
                    found = true;
                    console.log(`Address: ${address}, Private Key: ${privateKey}, Attempts: ${attempts}`);
                    process.exit(0);
                }

                if (attempts % logFrequency === 0) {
                    console.log(`W${process.pid} Attempt ${attempts}: ${address}`);
                }
            }
        } while (!found);
    }

    process.on('SIGINT', () => {
        console.log('Terminating...');
        process.exit(0);
    });

    spawnAddress();
    console.log(`Worker ${process.pid} started`);
}
