#!/usr/bin/env node

/**
 * VMTEST Environment Measurements - Node.js Version
 * Extracts timing, scheduling, cache, and memory measurements to detect virtualization
 * Based on research from Lin et al. (2021) and other VM detection papers
 */

const cluster = require('cluster');
const os = require('os');
const process = require('process');
const crypto = require('crypto');
const { performance } = require('perf_hooks');
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');

class VMTestMeasurements {
    constructor(iterations = 1000) {
        this.iterations = iterations;
        this.measurements = {};
        this.systemInfo = {};
    }

    // High-resolution timer in nanoseconds
    getTimeNs() {
        const hrTime = process.hrtime();
        return hrTime[0] * 1000000000 + hrTime[1];
    }

    // Statistical calculation methods
    static mean(values) {
        if (!values || values.length === 0) return 0;
        return values.reduce((sum, val) => sum + val, 0) / values.length;
    }

    static variance(values, meanVal = null) {
        if (!values || values.length < 2) return 0;
        if (meanVal === null) meanVal = VMTestMeasurements.mean(values);
        const sumSquaredDiffs = values.reduce((sum, val) => sum + Math.pow(val - meanVal, 2), 0);
        return sumSquaredDiffs / (values.length - 1);
    }

    static standardDeviation(values, meanVal = null) {
        return Math.sqrt(VMTestMeasurements.variance(values, meanVal));
    }

    static coefficientOfVariation(values) {
        const meanVal = VMTestMeasurements.mean(values);
        if (meanVal === 0) return 0;
        const stdDev = VMTestMeasurements.standardDeviation(values, meanVal);
        return stdDev / meanVal;
    }

    static skewness(values) {
        if (!values || values.length < 3) return 0;
        const meanVal = VMTestMeasurements.mean(values);
        const stdDev = VMTestMeasurements.standardDeviation(values, meanVal);
        if (stdDev <= 0) return 0;

        const sumCubedDeviations = values.reduce((sum, val) => {
            const deviation = (val - meanVal) / stdDev;
            return sum + Math.pow(deviation, 3);
        }, 0);

        let skew = sumCubedDeviations / values.length;

        // Apply bias correction for small samples
        if (values.length > 2) {
            skew = skew * Math.sqrt(values.length * (values.length - 1)) / (values.length - 2);
        }

        // Bound checking
        return Math.max(-100, Math.min(100, skew));
    }

    static kurtosis(values) {
        if (!values || values.length < 4) return 0;
        const meanVal = VMTestMeasurements.mean(values);
        const stdDev = VMTestMeasurements.standardDeviation(values, meanVal);
        if (stdDev <= 0) return 0;

        const sumQuartedDeviations = values.reduce((sum, val) => {
            const deviation = (val - meanVal) / stdDev;
            return sum + Math.pow(deviation, 4);
        }, 0);

        let kurt = (sumQuartedDeviations / values.length) - 3.0; // Excess kurtosis

        // Apply bias correction for small samples
        if (values.length > 3) {
            const n = values.length;
            kurt = ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * kurt + 6);
        }

        // Bound checking
        return Math.max(-100, Math.min(100, kurt));
    }

    // CPU-bound computation for timing measurements
    cpuBoundTask() {
        const start = this.getTimeNs();
        
        // Computational work similar to C version
        let result = 0;
        for (let i = 0; i < 10000; i++) {
            result += Math.sqrt(i) * Math.sin(i) + Math.cos(i * 0.1);
        }
        
        const end = this.getTimeNs();
        return end - start;
    }

    // Memory-intensive task for cache testing
    cacheUnfriendlyAccess() {
        const start = this.getTimeNs();
        const size = 1024 * 1024; // 1MB
        const buffer = Buffer.alloc(size);
        
        // Random access pattern (cache-unfriendly)
        for (let i = 0; i < 1000; i++) {
            const offset = Math.floor(Math.random() * (size - 4));
            buffer.writeInt32BE(i, offset);
        }
        
        const end = this.getTimeNs();
        return end - start;
    }

    cacheFriendlyAccess() {
        const start = this.getTimeNs();
        const size = 1024 * 1024; // 1MB
        const buffer = Buffer.alloc(size);
        
        // Sequential access pattern (cache-friendly)
        for (let i = 0; i < size - 4; i += 4) {
            buffer.writeInt32BE(i, i);
        }
        
        const end = this.getTimeNs();
        return end - start;
    }

    // Memory address entropy calculation
    calculateMemoryEntropy() {
        const addresses = [];
        for (let i = 0; i < 1000; i++) {
            const buffer = Buffer.alloc(64);
            // Use buffer address as a proxy for memory address patterns
            addresses.push(buffer.byteOffset);
        }

        // Calculate Shannon entropy
        const addressCounts = {};
        addresses.forEach(addr => {
            const bucketAddr = Math.floor(addr / 4096); // 4KB buckets
            addressCounts[bucketAddr] = (addressCounts[bucketAddr] || 0) + 1;
        });

        let entropy = 0;
        const total = addresses.length;
        Object.values(addressCounts).forEach(count => {
            const probability = count / total;
            if (probability > 0) {
                entropy -= probability * Math.log2(probability);
            }
        });

        return entropy;
    }

    // Basic timing measurements
    async measureBasicTiming() {
        console.log("Measuring basic timing patterns...");
        const times = [];
        
        for (let i = 0; i < this.iterations; i++) {
            const execTime = this.cpuBoundTask();
            times.push(execTime);
        }

        const mean = VMTestMeasurements.mean(times);
        const variance = VMTestMeasurements.variance(times, mean);
        const cv = VMTestMeasurements.coefficientOfVariation(times);
        const skewness = VMTestMeasurements.skewness(times);
        const kurtosis = VMTestMeasurements.kurtosis(times);

        this.measurements.TIMING_BASIC_MEAN = mean;
        this.measurements.TIMING_BASIC_VARIANCE = variance;
        this.measurements.TIMING_BASIC_CV = cv;
        this.measurements.TIMING_BASIC_SKEWNESS = skewness;
        this.measurements.TIMING_BASIC_KURTOSIS = kurtosis;
    }

    // Consecutive timing measurements
    async measureConsecutiveTiming() {
        console.log("Measuring consecutive timing patterns...");
        const times = [];
        
        for (let i = 0; i < this.iterations; i++) {
            const start = this.getTimeNs();
            // Two consecutive operations
            this.cpuBoundTask();
            this.cpuBoundTask();
            const end = this.getTimeNs();
            times.push(end - start);
        }

        const mean = VMTestMeasurements.mean(times);
        const variance = VMTestMeasurements.variance(times, mean);
        const cv = VMTestMeasurements.coefficientOfVariation(times);
        const skewness = VMTestMeasurements.skewness(times);
        const kurtosis = VMTestMeasurements.kurtosis(times);

        this.measurements.TIMING_CONSECUTIVE_MEAN = mean;
        this.measurements.TIMING_CONSECUTIVE_VARIANCE = variance;
        this.measurements.TIMING_CONSECUTIVE_CV = cv;
        this.measurements.TIMING_CONSECUTIVE_SKEWNESS = skewness;
        this.measurements.TIMING_CONSECUTIVE_KURTOSIS = kurtosis;
    }

    // Thread scheduling measurements using Worker threads
    async measureThreadScheduling() {
        console.log("Measuring thread scheduling patterns...");
        
        return new Promise((resolve) => {
            const times = [];
            let completed = 0;
            const target = this.iterations/10;

            const workerCode = `
                const { parentPort, workerData } = require('worker_threads');
                const { performance } = require('perf_hooks');
                
                function cpuBoundTask() {
                    const start = performance.now();
                    let result = 0;
                    for (let i = 0; i < 10000; i++) {
                        result += Math.sqrt(i) * Math.sin(i) + Math.cos(i * 0.1);
                    }
                    const end = performance.now();
                    return (end - start) * 1000000; // Convert to nanoseconds
                }
                
                parentPort.postMessage(cpuBoundTask());
            `;

            for (let i = 0; i < target; i++) {
                const worker = new Worker(workerCode, { eval: true });
                
                worker.on('message', (time) => {
                    times.push(time);
                    completed++;
                    
                    if (completed === target) {
                        const mean = times.reduce((sum, val) => sum + val, 0) / times.length;
                        const variance = times.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / (times.length - 1);
                        const stdDev = Math.sqrt(variance);
                        const cv = stdDev / mean;
                        
                        // Calculate skewness
                        const skewness = times.reduce((sum, val) => {
                            const deviation = (val - mean) / stdDev;
                            return sum + Math.pow(deviation, 3);
                        }, 0) / times.length;
                        
                        // Calculate kurtosis
                        const kurtosis = (times.reduce((sum, val) => {
                            const deviation = (val - mean) / stdDev;
                            return sum + Math.pow(deviation, 4);
                        }, 0) / times.length) - 3.0;

                        // Physical Machine Index (PMI) calculation
                        const pmi = (skewness * kurtosis) / (cv * 100)

                        this.measurements.SCHEDULING_THREAD_MEAN = mean;
                        this.measurements.SCHEDULING_THREAD_VARIANCE = variance;
                        this.measurements.SCHEDULING_THREAD_CV = cv;
                        this.measurements.SCHEDULING_THREAD_SKEWNESS = skewness;
                        this.measurements.SCHEDULING_THREAD_KURTOSIS = kurtosis;
                        this.measurements.PHYSICAL_MACHINE_INDEX = pmi;
                        
                        resolve();
                    }
                });
                
                worker.on('error', (err) => {
                    console.error('Worker error:', err);
                    completed++;
                    if (completed === target) resolve();
                });
            }
        });
    }

    // Multiprocessing measurements using child processes
    async measureMultiprocessing() {
        console.log("Measuring multiprocessing patterns...");
        const { spawn } = require('child_process');
        const times = [];

        return new Promise((resolve) => {
            let completed = 0;
            const target = Math.min(this.iterations, 100); // Limit for performance

            for (let i = 0; i < target; i++) {
                const start = this.getTimeNs();
                
                const child = spawn('node', ['-e', `
                    let result = 0;
                    for (let i = 0; i < 10000; i++) {
                        result += Math.sqrt(i) * Math.sin(i) + Math.cos(i * 0.1);
                    }
                    process.exit(0);
                `]);

                child.on('close', () => {
                    const end = this.getTimeNs();
                    times.push(end - start);
                    completed++;

                    if (completed === target) {
                        const mean = VMTestMeasurements.mean(times);
                        const variance = VMTestMeasurements.variance(times, mean);
                        const cv = VMTestMeasurements.coefficientOfVariation(times);
                        const skewness = VMTestMeasurements.skewness(times);
                        const kurtosis = VMTestMeasurements.kurtosis(times);

                        const pmi = (skewness * kurtosis) / (cv * 100);

                        this.measurements.SCHEDULING_MULTIPROC_MEAN = mean;
                        this.measurements.SCHEDULING_MULTIPROC_VARIANCE = variance;
                        this.measurements.SCHEDULING_MULTIPROC_CV = cv;
                        this.measurements.SCHEDULING_MULTIPROC_SKEWNESS = skewness;
                        this.measurements.SCHEDULING_MULTIPROC_KURTOSIS = kurtosis;
                        this.measurements.MULTIPROC_PHYSICAL_MACHINE_INDEX = pmi;

                        resolve();
                    }
                });
            }
        });
    }

    // Cache behavior measurements
    async measureCacheBehavior() {
        console.log("Measuring cache behavior patterns...");
        const unfriendlyTimes = [];
        const friendlyTimes = [];

        for (let i = 0; i < Math.min(this.iterations, 100); i++) {
            unfriendlyTimes.push(this.cacheUnfriendlyAccess());
            friendlyTimes.push(this.cacheFriendlyAccess());
        }

        const unfriendlyMean = VMTestMeasurements.mean(unfriendlyTimes);
        const friendlyMean = VMTestMeasurements.mean(friendlyTimes);

        this.measurements.CACHE_ACCESS_RATIO = unfriendlyMean / friendlyMean;
        this.measurements.CACHE_MISS_RATIO = (unfriendlyMean - friendlyMean) / friendlyMean;
    }

    // Memory entropy measurement
    async measureMemoryEntropy() {
        console.log("Measuring memory address entropy...");
        this.measurements.MEMORY_ADDRESS_ENTROPY = this.calculateMemoryEntropy();
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
            uptime: os.uptime()
        };

        // Check for VM indicators
        const vmIndicators = {
            low_memory: this.systemInfo.total_memory < 2 * 1024 * 1024 * 1024, // < 2GB
            single_cpu: this.systemInfo.cpu_count === 1,
            vm_cpu_model: /virtual|qemu|kvm|xen|vmware/i.test(this.systemInfo.cpu_model)
        };

        this.systemInfo.vm_indicators = vmIndicators;
    }

    // Calculate overall VM likelihood
    calculateVMIndicators() {
        const indicators = {
            high_scheduling_variance: this.measurements.SCHEDULING_THREAD_CV > 0.15,
            low_pmi: this.measurements.PHYSICAL_MACHINE_INDEX < 1.0,
            high_timing_variance: this.measurements.TIMING_BASIC_CV > 0.1,
            abnormal_cache_ratio: this.measurements.CACHE_ACCESS_RATIO > 2.0,
            low_memory_entropy: this.measurements.MEMORY_ADDRESS_ENTROPY < 3.0
        };

        // Calculate likelihood score
        const weights = {
            high_scheduling_variance: 0.4,
            low_pmi: 0.3,
            high_timing_variance: 0.15,
            abnormal_cache_ratio: 0.1,
            low_memory_entropy: 0.05
        };

        let score = 0;
        Object.entries(indicators).forEach(([key, value]) => {
            if (value) score += weights[key] || 0;
        });

        indicators.vm_likelihood_score = score;
        indicators.likely_vm = score > 0.5;

        return indicators;
    }

    // Run all measurements
    async runAllMeasurements() {
        console.log("Starting VMtest measurements...");
        console.log(`Node.js version: ${process.version}`);
        console.log(`Platform: ${os.platform()} ${os.release()}`);
        console.log(`CPU count: ${os.cpus().length}`);
        console.log(`Memory: ${(os.totalmem() / 1024 / 1024 / 1024).toFixed(2)} GB`);
        console.log(`Iterations: ${this.iterations}`);
        console.log("");

        this.gatherSystemInfo();

        await this.measureBasicTiming();
        await this.measureConsecutiveTiming();
        await this.measureThreadScheduling();
        await this.measureMultiprocessing();
        await this.measureCacheBehavior();
        await this.measureMemoryEntropy();

        // Calculate overall coefficients of variation
        const timingCVs = [
            this.measurements.TIMING_BASIC_CV,
            this.measurements.TIMING_CONSECUTIVE_CV
        ];
        const schedulingCVs = [
            this.measurements.SCHEDULING_THREAD_CV,
            this.measurements.SCHEDULING_MULTIPROC_CV
        ];

        this.measurements.OVERALL_TIMING_CV = VMTestMeasurements.mean(timingCVs);
        this.measurements.OVERALL_SCHEDULING_CV = VMTestMeasurements.mean(schedulingCVs);

        const vmIndicators = this.calculateVMIndicators();

        return {
            system_info: this.systemInfo,
            measurements: this.measurements,
            vm_indicators: vmIndicators,
            timestamp: new Date().toISOString(),
            language: 'Node.js',
            version: '1.0.0'
        };
    }
}

// Main execution
async function main() {
    const iterations = process.argv[2] ? parseInt(process.argv[2]) : 1000;
    
    if (isNaN(iterations) || iterations < 1) {
        console.error("Usage: node vmtest.js [iterations]");
        console.error("Example: node vmtest.js 1000");
        process.exit(1);
    }

    const vmtest = new VMTestMeasurements(iterations);
    
    try {
        const results = await vmtest.runAllMeasurements();
        
        console.log("\n" + "=".repeat(50));
        console.log("VMTEST RESULTS");
        console.log("=".repeat(50));
        
        // Print formatted results
        console.log(JSON.stringify(results, null, 2));
        
        console.log("\n" + "=".repeat(50));
        console.log("VM DETECTION SUMMARY");
        console.log("=".repeat(50));
        
        const { vm_indicators } = results;
        console.log(`VM Likelihood Score: ${(vm_indicators.vm_likelihood_score * 100).toFixed(1)}%`);
        console.log(`Likely Virtual Machine: ${vm_indicators.likely_vm ? 'YES' : 'NO'}`);
        
        if (vm_indicators.likely_vm) {
            console.log("\nVM Indicators Detected:");
            Object.entries(vm_indicators).forEach(([key, value]) => {
                if (value === true && key !== 'likely_vm') {
                    console.log(`  - ${key.replace(/_/g, ' ')}`);
                }
            });
        }
        
    } catch (error) {
        console.error("Error running VMtest:", error);
        process.exit(1);
    }
}

// Only run main if this file is executed directly
if (require.main === module) {
    main().catch(console.error);
}

module.exports = VMTestMeasurements;
