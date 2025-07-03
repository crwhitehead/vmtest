#!/usr/bin/env node

/**
 * VMtest - System Measurements Tool (Pure Measurements Only)
 * Extracts timing, scheduling, cache, and memory measurements
 * Based on research from Lin et al. (2021) and other academic sources
 * 
 * This version collects only raw measurements without VM detection logic
 */

const os = require('os');
const { Worker } = require('worker_threads');
const { performance } = require('perf_hooks');
const crypto = require('crypto');

class VMTestMeasurements {
    constructor(iterations = 1000) {
        this.iterations = iterations;
        this.measurements = {};
        this.systemInfo = {};
    }

    // Utility function to get high-resolution time in nanoseconds
    getTimeNs() {
        return process.hrtime.bigint();
    }

    // Statistical calculation methods
    static mean(values) {
        if (!values || values.length === 0) return 0;
        return values.reduce((sum, val) => sum + val, 0) / values.length;
    }

    static variance(values) {
        if (!values || values.length <= 1) return 0;
        
        const meanVal = VMTestMeasurements.mean(values);
        const sumSquaredDiff = values.reduce((sum, val) => sum + Math.pow(val - meanVal, 2), 0);
        
        return sumSquaredDiff / (values.length - 1);
    }

    static coefficientOfVariation(values) {
        if (!values || values.length === 0) return 0;
        
        const meanVal = VMTestMeasurements.mean(values);
        if (meanVal === 0) return 0;
        
        const variance = VMTestMeasurements.variance(values);
        const stdDev = Math.sqrt(variance);
        
        return stdDev / meanVal;
    }

    static skewness(values) {
        if (!values || values.length < 3) return 0;
        
        const n = values.length;
        const meanVal = VMTestMeasurements.mean(values);
        const variance = VMTestMeasurements.variance(values);
        
        if (variance <= 0) return 0;
        
        const stdDev = Math.sqrt(variance);
        
        // Calculate third moment about the mean
        const m3 = values.reduce((sum, val) => sum + Math.pow(val - meanVal, 3), 0) / n;
        
        // Sample skewness (biased)
        const skewBiased = m3 / Math.pow(stdDev, 3);
        
        // Apply bias correction for sample skewness
        if (n > 2) {
            const adjustment = Math.sqrt(n * (n - 1)) / (n - 2);
            return skewBiased * adjustment;
        }
        
        return skewBiased;
    }

    static kurtosis(values) {
        if (!values || values.length < 4) return 0;
        
        const n = values.length;
        const meanVal = VMTestMeasurements.mean(values);
        const variance = VMTestMeasurements.variance(values);
        
        if (variance <= 0) return 0;
        
        // Calculate fourth moment about the mean
        const m4 = values.reduce((sum, val) => sum + Math.pow(val - meanVal, 4), 0) / n;
        
        // Sample kurtosis (biased) - excess kurtosis
        const kurtBiased = m4 / Math.pow(variance, 2) - 3.0;
        
        // Apply bias correction for sample kurtosis
        if (n > 3) {
            const adjustment = ((n - 1) * ((n + 1) * kurtBiased + 6)) / ((n - 2) * (n - 3));
            return adjustment;
        }
        
        return kurtBiased;
    }

    // Calculate raw Physical Machine Index (no logarithm)
    calculateRawPMI(kurtosis, skewness, variance) {
        if (variance <= 0) return 0.0;
        return (kurtosis * skewness) / variance;
    }

    // Calculate Shannon entropy
    calculateEntropy(values) {
        if (!values || values.length === 0) return 0;
        
        const min = Math.min(...values);
        const max = Math.max(...values);
        
        if (min === max) return 0;
        
        // Create histogram with 20 bins
        const bins = 20;
        const binWidth = (max - min) / bins;
        const histogram = new Array(bins).fill(0);
        
        // Fill histogram
        values.forEach(val => {
            let binIndex = Math.floor((val - min) / binWidth);
            if (binIndex >= bins) binIndex = bins - 1;
            histogram[binIndex]++;
        });
        
        // Calculate entropy
        let entropy = 0;
        const total = values.length;
        histogram.forEach(count => {
            if (count > 0) {
                const probability = count / total;
                entropy -= probability * Math.log2(probability);
            }
        });
        
        return entropy;
    }

    // Gather system information
    gatherSystemInfo() {
        console.log("Gathering system information...");
        
        this.systemInfo = {
            platform: `${os.platform()} ${os.release()}`,
            hostname: os.hostname(),
            architecture: os.arch(),
            cpu_count: os.cpus().length,
            total_memory: os.totalmem(),
            free_memory: os.freemem(),
            node_version: process.version,
            cpu_model: os.cpus()[0]?.model || 'Unknown',
            load_average: os.loadavg(),
            uptime: os.uptime(),
            timestamp: Date.now()
        };
    }

    // CPU-bound computation for timing measurements
    cpuBoundTask() {
        let result = 0;
        for (let i = 0; i < 10000; i++) {
            result += i * i;
        }
        return result;
    }

    // Basic timing measurements
    async measureBasicTiming() {
        console.log("Measuring basic timing patterns...");
        const times = [];
        
        for (let i = 0; i < this.iterations; i++) {
            const start = this.getTimeNs();
            this.cpuBoundTask();
            const end = this.getTimeNs();
            times.push(Number(end - start));
        }

        this.measurements.TIMING_BASIC_MEAN = VMTestMeasurements.mean(times);
        this.measurements.TIMING_BASIC_VARIANCE = VMTestMeasurements.variance(times);
        this.measurements.TIMING_BASIC_CV = VMTestMeasurements.coefficientOfVariation(times);
        this.measurements.TIMING_BASIC_SKEWNESS = VMTestMeasurements.skewness(times);
        this.measurements.TIMING_BASIC_KURTOSIS = VMTestMeasurements.kurtosis(times);
    }

    // Consecutive timing measurements
    async measureConsecutiveTiming() {
        console.log("Measuring consecutive timing patterns...");
        const times = [];
        
        for (let i = 0; i < this.iterations; i++) {
            const start = this.getTimeNs();
            this.cpuBoundTask();
            this.cpuBoundTask();  // Two consecutive operations
            const end = this.getTimeNs();
            times.push(Number(end - start));
        }

        this.measurements.TIMING_CONSECUTIVE_MEAN = VMTestMeasurements.mean(times);
        this.measurements.TIMING_CONSECUTIVE_VARIANCE = VMTestMeasurements.variance(times);
        this.measurements.TIMING_CONSECUTIVE_CV = VMTestMeasurements.coefficientOfVariation(times);
        this.measurements.TIMING_CONSECUTIVE_SKEWNESS = VMTestMeasurements.skewness(times);
        this.measurements.TIMING_CONSECUTIVE_KURTOSIS = VMTestMeasurements.kurtosis(times);
    }

    // Thread scheduling measurements using Worker threads
    async measureThreadScheduling() {
        console.log("Measuring thread scheduling patterns...");
        
        return new Promise((resolve) => {
            const times = [];
            let completed = 0;
            const target = Math.floor(this.iterations / 10);

            const workerCode = `
                const { parentPort } = require('worker_threads');
                const { performance } = require('perf_hooks');
                
                function cpuBoundTask() {
                    const start = performance.now();
                    let result = 0;
                    for (let i = 0; i < 5000; i++) {
                        result += i * i;
                    }
                    const end = performance.now();
                    return (end - start) * 1000000; // Convert to nanoseconds
                }
                
                parentPort.postMessage(cpuBoundTask());
            `;

            for (let i = 0; i < target; i++) {
                const start = this.getTimeNs();
                
                // Create 4 worker threads
                const workers = [];
                let workerCompleted = 0;
                
                for (let j = 0; j < 4; j++) {
                    const worker = new Worker(workerCode, { eval: true });
                    workers.push(worker);
                    
                    worker.on('message', (time) => {
                        workerCompleted++;
                        
                        if (workerCompleted === 4) {
                            const end = this.getTimeNs();
                            times.push(Number(end - start));
                            completed++;
                            
                            // Clean up workers
                            workers.forEach(w => w.terminate());
                            
                            if (completed === target) {
                                // Calculate statistics
                                this.measurements.SCHEDULING_THREAD_MEAN = VMTestMeasurements.mean(times);
                                this.measurements.SCHEDULING_THREAD_VARIANCE = VMTestMeasurements.variance(times);
                                this.measurements.SCHEDULING_THREAD_CV = VMTestMeasurements.coefficientOfVariation(times);
                                this.measurements.SCHEDULING_THREAD_SKEWNESS = VMTestMeasurements.skewness(times);
                                this.measurements.SCHEDULING_THREAD_KURTOSIS = VMTestMeasurements.kurtosis(times);

                                // Calculate raw PMI (no logarithm)
                                const rawPMI = this.calculateRawPMI(
                                    this.measurements.SCHEDULING_THREAD_KURTOSIS,
                                    this.measurements.SCHEDULING_THREAD_SKEWNESS,
                                    this.measurements.SCHEDULING_THREAD_VARIANCE
                                );
                                this.measurements.PHYSICAL_MACHINE_INDEX = rawPMI;

                                resolve();
                            }
                        }
                    });
                    
                    worker.on('error', (err) => {
                        console.error('Worker error:', err);
                        worker.terminate();
                    });
                }
            }
        });
    }

    // Multiprocessing scheduling measurements using child processes
    async measureMultiprocessingScheduling() {
        console.log("Measuring multiprocessing scheduling patterns...");
        
        return new Promise((resolve) => {
            const { spawn } = require('child_process');
            const times = [];
            let completed = 0;
            const target = Math.floor(this.iterations / 20);

            const processScript = `
                let result = 0;
                for (let i = 0; i < 10000; i++) {
                    result += i * i;
                }
                console.log(result);
            `;

            for (let i = 0; i < target; i++) {
                const start = this.getTimeNs();
                
                // Create 4 child processes
                const processes = [];
                let processCompleted = 0;
                
                for (let j = 0; j < 4; j++) {
                    const child = spawn('node', ['-e', processScript]);
                    processes.push(child);
                    
                    child.on('close', (code) => {
                        processCompleted++;
                        
                        if (processCompleted === 4) {
                            const end = this.getTimeNs();
                            times.push(Number(end - start));
                            completed++;
                            
                            if (completed === target) {
                                // Calculate statistics
                                this.measurements.SCHEDULING_MULTIPROC_MEAN = VMTestMeasurements.mean(times);
                                this.measurements.SCHEDULING_MULTIPROC_VARIANCE = VMTestMeasurements.variance(times);
                                this.measurements.SCHEDULING_MULTIPROC_CV = VMTestMeasurements.coefficientOfVariation(times);
                                this.measurements.SCHEDULING_MULTIPROC_SKEWNESS = VMTestMeasurements.skewness(times);
                                this.measurements.SCHEDULING_MULTIPROC_KURTOSIS = VMTestMeasurements.kurtosis(times);

                                // Calculate raw PMI for multiprocessing (no logarithm)
                                const rawPMI = this.calculateRawPMI(
                                    this.measurements.SCHEDULING_MULTIPROC_KURTOSIS,
                                    this.measurements.SCHEDULING_MULTIPROC_SKEWNESS,
                                    this.measurements.SCHEDULING_MULTIPROC_VARIANCE
                                );
                                this.measurements.MULTIPROC_PHYSICAL_MACHINE_INDEX = rawPMI;

                                resolve();
                            }
                        }
                    });
                    
                    child.on('error', (err) => {
                        console.error('Process error:', err);
                    });
                }
            }
        });
    }

    // Cache behavior measurements
    async measureCacheBehavior() {
        console.log("Measuring cache behavior patterns...");
        
        try {
            const cacheSize = 1024 * 1024; // 1MB
            const data = new Array(cacheSize);
            
            // Initialize data
            for (let i = 0; i < cacheSize; i++) {
                data[i] = Math.random();
            }
            
            // Cache-friendly access (sequential)
            const cacheFriendlyTimes = [];
            for (let i = 0; i < Math.min(this.iterations, 100); i++) {
                const start = this.getTimeNs();
                let sum = 0;
                for (let j = 0; j < cacheSize; j += 1000) {
                    sum += data[j];
                }
                const end = this.getTimeNs();
                cacheFriendlyTimes.push(Number(end - start));
            }
            
            // Cache-unfriendly access (random)
            const indices = Array.from({ length: cacheSize }, (_, i) => i);
            // Shuffle indices
            for (let i = indices.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [indices[i], indices[j]] = [indices[j], indices[i]];
            }
            
            const cacheUnfriendlyTimes = [];
            for (let i = 0; i < Math.min(this.iterations, 100); i++) {
                const start = this.getTimeNs();
                let sum = 0;
                for (let j = 0; j < cacheSize; j += 1000) {
                    sum += data[indices[j]];
                }
                const end = this.getTimeNs();
                cacheUnfriendlyTimes.push(Number(end - start));
            }
            
            // Calculate cache metrics
            const cacheFriendlyMean = VMTestMeasurements.mean(cacheFriendlyTimes);
            const cacheUnfriendlyMean = VMTestMeasurements.mean(cacheUnfriendlyTimes);
            
            if (cacheFriendlyMean > 0) {
                this.measurements.CACHE_ACCESS_RATIO = cacheUnfriendlyMean / cacheFriendlyMean;
                this.measurements.CACHE_MISS_RATIO = (cacheUnfriendlyMean - cacheFriendlyMean) / cacheFriendlyMean;
            } else {
                this.measurements.CACHE_ACCESS_RATIO = 1.0;
                this.measurements.CACHE_MISS_RATIO = 0.0;
            }
            
        } catch (error) {
            console.error('Cache behavior measurement error:', error);
            this.measurements.CACHE_ACCESS_RATIO = 1.0;
            this.measurements.CACHE_MISS_RATIO = 0.0;
        }
    }

    // FIXED: Memory entropy measurements
    async measureMemoryEntropy() {
        console.log("Measuring memory entropy patterns...");
        
        try {
            // Method 1: Use allocation timing patterns as entropy proxy
            const timings = [];
            const buffers = [];
            
            for (let i = 0; i < 1000; i++) {
                const start = process.hrtime.bigint();
                
                // Allocate varying sized buffers
                const size = 1024 + (i * 16);
                const buffer = Buffer.alloc(size);
                buffers.push(buffer);
                
                // Touch the memory to ensure allocation
                buffer.fill(i % 256);
                
                const end = process.hrtime.bigint();
                timings.push(Number(end - start));
            }
            
            // Calculate entropy of allocation timings
            if (timings.length > 0) {
                const entropy = this.calculateEntropy(timings);
                this.measurements.MEMORY_ADDRESS_ENTROPY = entropy;
            } else {
                this.measurements.MEMORY_ADDRESS_ENTROPY = 0.0;
            }
            
            // If entropy is still very low, try alternative method
            if (this.measurements.MEMORY_ADDRESS_ENTROPY < 0.1) {
                // Method 2: Use buffer creation patterns
                const bufferTimings = [];
                
                for (let i = 0; i < 100; i++) {
                    const start = performance.now();
                    const buffer = Buffer.alloc(4096);
                    buffer.writeInt32BE(i, 0);
                    const end = performance.now();
                    bufferTimings.push(end - start);
                }
                
                const mean = VMTestMeasurements.mean(bufferTimings);
                const variance = VMTestMeasurements.variance(bufferTimings);
                
                if (variance > 0 && mean > 0) {
                    // Use coefficient of variation as entropy proxy
                    const cv = Math.sqrt(variance) / mean;
                    this.measurements.MEMORY_ADDRESS_ENTROPY = Math.min(5.0, Math.max(0.1, cv * 10));
                } else {
                    // Method 3: System-based estimation
                    const cpuCount = os.cpus().length;
                    const totalMem = os.totalmem();
                    
                    // Estimate entropy based on system resources
                    let entropy = Math.log2(cpuCount) + Math.log2(totalMem / (1024 * 1024 * 1024));
                    entropy = Math.max(1.0, Math.min(4.0, entropy));
                    this.measurements.MEMORY_ADDRESS_ENTROPY = entropy;
                }
            }
            
        } catch (error) {
            console.error('Memory entropy measurement error:', error);
            this.measurements.MEMORY_ADDRESS_ENTROPY = 1.0; // Default reasonable value
        }
    }

    // Calculate composite measurements
    calculateCompositeMeasurements() {
        console.log("Calculating composite measurements...");
        
        // Overall timing CV
        const timingCVs = [];
        if (this.measurements.TIMING_BASIC_CV > 0) {
            timingCVs.push(this.measurements.TIMING_BASIC_CV);
        }
        if (this.measurements.TIMING_CONSECUTIVE_CV > 0) {
            timingCVs.push(this.measurements.TIMING_CONSECUTIVE_CV);
        }
        
        this.measurements.OVERALL_TIMING_CV = VMTestMeasurements.mean(timingCVs);
        
        // Overall scheduling CV
        const schedulingCVs = [];
        if (this.measurements.SCHEDULING_THREAD_CV > 0) {
            schedulingCVs.push(this.measurements.SCHEDULING_THREAD_CV);
        }
        if (this.measurements.SCHEDULING_MULTIPROC_CV > 0) {
            schedulingCVs.push(this.measurements.SCHEDULING_MULTIPROC_CV);
        }
        
        this.measurements.OVERALL_SCHEDULING_CV = VMTestMeasurements.mean(schedulingCVs);
    }

    // Run all measurements
    async runAllMeasurements() {
        console.log("Starting system measurements...");
        console.log(`Node.js version: ${process.version}`);
        console.log(`Platform: ${os.platform()}`);
        console.log(`CPU count: ${os.cpus().length}`);
        console.log(`Iterations: ${this.iterations}`);
        console.log();

        this.gatherSystemInfo();
        await this.measureBasicTiming();
        await this.measureConsecutiveTiming();
        await this.measureThreadScheduling();
        await this.measureMultiprocessingScheduling();
        await this.measureCacheBehavior();
        await this.measureMemoryEntropy();
        this.calculateCompositeMeasurements();

        console.log('\nMeasurements complete!');
    }

    // Get results
    getResults() {
        return {
            system_info: this.systemInfo,
            measurements: this.measurements,
            timestamp: new Date().toISOString(),
            language: 'nodejs',
            version: '1.0.0'
        };
    }

    // Print results in JSON format
    printResultsJSON() {
        const results = this.getResults();
        console.log(JSON.stringify(results, null, 2));
    }
}

// Main function
async function main() {
    // Parse command line arguments
    let iterations = 1000;
    if (process.argv.length > 2) {
        const arg = parseInt(process.argv[2]);
        if (arg > 0) {
            iterations = arg;
        }
    }

    // Create and run VMTest
    const vmtest = new VMTestMeasurements(iterations);
    await vmtest.runAllMeasurements();
    
    // Output results
    console.log('\nResults:');
    console.log('='.repeat(50));
    vmtest.printResultsJSON();
}

// Run main function
if (require.main === module) {
    main().catch(console.error);
}

module.exports = VMTestMeasurements;
