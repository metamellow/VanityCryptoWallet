// node generateWalletFromLibrary.js

const { ethers } = require("ethers");
const cluster = require('cluster');
const os = require('os');

// VARIABLES
const useLowPower = false;
const useStartString = true;
const caseInsensitive = false;
const logFrequency = 1000;  // Increased for less frequent logging
const batchSize = 1000;

// WORDLIST
const acceptableWords = [
    "C00C1E", "C0FFEE", "B00BIE",
    "C0DE", "B00B", "DEAD", "CAFE", "D00D", "FACE", "BABE", "BEEF", "F00D", 
    // "ACE", "ICE", "BAD", "DAD",
].map(word => caseInsensitive ? word.toLowerCase() : word);

const wordSet = new Set(acceptableWords);

const numCPUs = os.cpus().length;
const numWorkers = useLowPower ? Math.ceil(numCPUs - (numCPUs - 4)) : numCPUs - 4;

if (cluster.isMaster) {
    console.log(`Master ${process.pid} is running with ${numWorkers} workers`);
    console.log(`Configuration:`);
    console.log(`  Low Power Mode: ${useLowPower}`);
    console.log(`  Batch Size: ${batchSize}`);
    console.log(`  Log Frequency: ${logFrequency}`);
    console.log(`  Use Start String: ${useStartString}`);
    console.log(`  Case Insensitive: ${caseInsensitive}`);

    let totalAttempts = 0;
    const startTime = Date.now();

    for (let i = 0; i < numWorkers; i++) {
        cluster.fork();
    }

    cluster.on('message', (worker, message) => {
        if (message.type === 'progress') {
            totalAttempts += message.attempts;
            const elapsedTime = (Date.now() - startTime) / 1000;
            const addressesPerSecond = totalAttempts / elapsedTime;
            console.log(`Processed ${totalAttempts} addresses... (${addressesPerSecond.toFixed(2)} addr/s)`);
        }
    });

    cluster.on('exit', (worker, code, signal) => {
        if (code === 0) {
            console.log(`Worker ${worker.process.pid} found the address and terminated.`);
            const endTime = Date.now();
            const totalTime = (endTime - startTime) / 1000;
            console.log(`\nTotal attempts: ${totalAttempts}`);
            console.log(`Total time: ${totalTime.toFixed(2)} seconds`);
            console.log(`Addresses checked per second: ${(totalAttempts / totalTime).toFixed(2)}`);
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
        const workerStartTime = Date.now();

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
                    const workerEndTime = Date.now();
                    const workerTotalTime = (workerEndTime - workerStartTime) / 1000;
                    console.log(`\nFound matching address: ${address}`);
                    console.log(`Private Key: ${privateKey}`);
                    console.log(`Seed Phrase: ${mnemonic}`);
                    console.log(`Attempts: ${attempts}`);
                    console.log(`Worker time: ${workerTotalTime.toFixed(2)} seconds`);
                    console.log(`Worker addresses per second: ${(attempts / workerTotalTime).toFixed(2)}`);
                    process.exit(0);
                }

                if (attempts % logFrequency === 0) {
                    process.send({ type: 'progress', attempts: logFrequency });
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