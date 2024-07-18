// node generateWalletFromLibrary.js

const { ethers } = require("ethers");
const cluster = require('cluster');
const os = require('os');

// VARIABLES
const useLowPower = true;
const useStartString = true;
const caseInsensitive = false;
const logFrequency = 10000;
const batchSize = 10000;

// WORDLIST
const acceptableWords = [
    "C00C1E", "C00CEE", "C00CE", "C00C",

    // "C0FFEE", "BEEF", "beef", "B00B", "BABE", "babe", "C0DE", "DEAD", "dead", "D00D", "F00D", "FEED",
    // "AAAAA", "aaaaa", "BBBBB", "bbbbb", "CCCCC", "ccccc", "DDDDD", "ddddd", "EEEEE", "eeeee", "FFFFF", "fffff",
    // "00000", "11111", "22222", "33333", "44444", "55555", "66666", "77777", "88888", "99999",
    // "AAAA", "aaaa", "BBBB", "bbbb", "CCCC", "cccc", "DDDD", "dddd", "EEEE", "eeee", "FFFF", "ffff",
    // "0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888", "9999",
    // "AA", "aa", "BB", "bb", "CC", "cc", "DD", "dd", "EE", "ee", "FF", "ff",
    // "00", "11", "22", "33", "44", "55", "66", "77", "88", "99",
].map(word => caseInsensitive ? word.toLowerCase() : word);

const wordSet = new Set(acceptableWords);

const numCPUs = os.cpus().length;
const numWorkers = useLowPower ? Math.ceil(numCPUs - (numCPUs - 4)) : numCPUs - 2;

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
                batch.push({ address, privateKey: wallet.privateKey, mnemonic: wallet.mnemonic.phrase });
            }

            for (const { address, privateKey, mnemonic } of batch) {
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
                    console.log(`Address: ${address}, Private Key: ${privateKey}, Seed Phrase: ${mnemonic}, Attempts: ${attempts}`);
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
