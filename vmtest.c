/*
# Compile with optimization and threading support
gcc -O2 -march=native -pthread -lm vm_detection.c -o vm_detection

# Run and capture output for ML processing
./vm_detection > vm_detection_data.txt

*/


#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>
#include <pthread.h>
#include <math.h>

#ifdef _WIN32
#include <windows.h>
#include <intrin.h>
#else
#include <x86intrin.h>
#include <sys/time.h>
#endif

// ============================================================================
// CONFIGURATION CONSTANTS - Adjust these to control test duration/accuracy
// ============================================================================

// RDTSC Timing Tests
#define RDTSC_ITERATIONS 10000
#define RDTSC_BENCHMARK_OPS 1000

// Thread Scheduling Tests  
#define THREAD_ITERATIONS 5000
#define THREAD_COUNT 8
#define THREAD_WORK_CYCLES 10000

// Cache Behavior Tests
#define CACHE_ITERATIONS 5000
#define CACHE_MEMORY_SIZE (8 * 1024 * 1024)  // 8MB
#define CACHE_LINE_SIZE 64

// Memory Allocation Tests
#define MEMORY_ITERATIONS 2000
#define MEMORY_ALLOCATION_SIZE 4096
#define MEMORY_PATTERN_SIZE 1000

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

// High precision timing
static inline uint64_t get_timestamp(void) {
#ifdef _WIN32
    return __rdtsc();
#else
    return __rdtsc();
#endif
}

// Get wall clock time in nanoseconds
uint64_t get_wall_time_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

// Statistical calculation functions
double calculate_mean(uint64_t* values, int count) {
    uint64_t sum = 0;
    for (int i = 0; i < count; i++) {
        sum += values[i];
    }
    return (double)sum / count;
}

double calculate_variance(uint64_t* values, int count, double mean) {
    double sum_sq_diff = 0.0;
    for (int i = 0; i < count; i++) {
        double diff = values[i] - mean;
        sum_sq_diff += diff * diff;
    }
    return sum_sq_diff / count;
}

double calculate_skewness(uint64_t* values, int count, double mean, double variance) {
    double sum_cubed_diff = 0.0;
    double std_dev = sqrt(variance);
    
    for (int i = 0; i < count; i++) {
        double norm_diff = (values[i] - mean) / std_dev;
        sum_cubed_diff += norm_diff * norm_diff * norm_diff;
    }
    return sum_cubed_diff / count;
}

double calculate_kurtosis(uint64_t* values, int count, double mean, double variance) {
    double sum_fourth_diff = 0.0;
    double std_dev = sqrt(variance);
    
    for (int i = 0; i < count; i++) {
        double norm_diff = (values[i] - mean) / std_dev;
        double fourth_power = norm_diff * norm_diff * norm_diff * norm_diff;
        sum_fourth_diff += fourth_power;
    }
    return (sum_fourth_diff / count) - 3.0; // Excess kurtosis
}

// ============================================================================
// 1. RDTSC TIMING ANALYSIS
// ============================================================================

typedef struct {
    uint64_t* raw_timings;
    uint64_t* consecutive_diffs;
    uint64_t* vm_exit_timings;
    double mean_timing;
    double variance;
    double coefficient_variation;
    double skewness;
    double kurtosis;
    uint64_t min_timing;
    uint64_t max_timing;
    uint64_t benchmark_time;
} rdtsc_results_t;

void test_rdtsc_basic_timing(rdtsc_results_t* results) {
    printf("=== RDTSC Basic Timing Analysis ===\n");
    
    results->raw_timings = malloc(RDTSC_ITERATIONS * sizeof(uint64_t));
    results->consecutive_diffs = malloc(RDTSC_ITERATIONS * sizeof(uint64_t));
    results->vm_exit_timings = malloc(RDTSC_ITERATIONS * sizeof(uint64_t));
    
    // Benchmark: Simple operations timing
    uint64_t bench_start = get_timestamp();
    volatile int dummy = 0;
    for (int i = 0; i < RDTSC_BENCHMARK_OPS; i++) {
        dummy += i;
        __asm__ volatile ("nop");
    }
    uint64_t bench_end = get_timestamp();
    results->benchmark_time = bench_end - bench_start;
    
    // Test 1: Basic RDTSC timing
    for (int i = 0; i < RDTSC_ITERATIONS; i++) {
        uint64_t start = get_timestamp();
        __asm__ volatile ("nop"); // Minimal operation
        uint64_t end = get_timestamp();
        results->raw_timings[i] = end - start;
    }
    
    // Test 2: Consecutive RDTSC calls (VM overhead detection)
    for (int i = 0; i < RDTSC_ITERATIONS; i++) {
        uint64_t t1 = get_timestamp();
        uint64_t t2 = get_timestamp();
        results->consecutive_diffs[i] = t2 - t1;
    }
    
    // Test 3: Potential VM-exit triggering operations
    for (int i = 0; i < RDTSC_ITERATIONS; i++) {
        uint64_t start = get_timestamp();
        
        // CPUID instruction (may trigger VM exit)
        uint32_t eax, ebx, ecx, edx;
        __asm__ volatile ("cpuid"
            : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
            : "a"(0)
        );
        
        uint64_t end = get_timestamp();
        results->vm_exit_timings[i] = end - start;
    }
    
    // Calculate statistics for raw timings
    results->mean_timing = calculate_mean(results->raw_timings, RDTSC_ITERATIONS);
    results->variance = calculate_variance(results->raw_timings, RDTSC_ITERATIONS, results->mean_timing);
    results->coefficient_variation = sqrt(results->variance) / results->mean_timing;
    results->skewness = calculate_skewness(results->raw_timings, RDTSC_ITERATIONS, results->mean_timing, results->variance);
    results->kurtosis = calculate_kurtosis(results->raw_timings, RDTSC_ITERATIONS, results->mean_timing, results->variance);
    
    // Find min/max
    results->min_timing = results->raw_timings[0];
    results->max_timing = results->raw_timings[0];
    for (int i = 1; i < RDTSC_ITERATIONS; i++) {
        if (results->raw_timings[i] < results->min_timing) results->min_timing = results->raw_timings[i];
        if (results->raw_timings[i] > results->max_timing) results->max_timing = results->raw_timings[i];
    }
    
    // Output results
    printf("RDTSC_BENCHMARK_CYCLES: %lu\n", results->benchmark_time);
    printf("RDTSC_MEAN_TIMING: %.2f\n", results->mean_timing);
    printf("RDTSC_VARIANCE: %.2f\n", results->variance);
    printf("RDTSC_COEFFICIENT_VARIATION: %.6f\n", results->coefficient_variation);
    printf("RDTSC_SKEWNESS: %.6f\n", results->skewness);
    printf("RDTSC_KURTOSIS: %.6f\n", results->kurtosis);
    printf("RDTSC_MIN_TIMING: %lu\n", results->min_timing);
    printf("RDTSC_MAX_TIMING: %lu\n", results->max_timing);
    printf("RDTSC_RANGE: %lu\n", results->max_timing - results->min_timing);
    
    // Consecutive RDTSC statistics
    double consec_mean = calculate_mean(results->consecutive_diffs, RDTSC_ITERATIONS);
    double consec_var = calculate_variance(results->consecutive_diffs, RDTSC_ITERATIONS, consec_mean);
    printf("RDTSC_CONSECUTIVE_MEAN: %.2f\n", consec_mean);
    printf("RDTSC_CONSECUTIVE_VARIANCE: %.2f\n", consec_var);
    
    // VM-exit timing statistics
    double vmexit_mean = calculate_mean(results->vm_exit_timings, RDTSC_ITERATIONS);
    double vmexit_var = calculate_variance(results->vm_exit_timings, RDTSC_ITERATIONS, vmexit_mean);
    printf("RDTSC_VMEXIT_MEAN: %.2f\n", vmexit_mean);
    printf("RDTSC_VMEXIT_VARIANCE: %.2f\n", vmexit_var);
    printf("RDTSC_VMEXIT_RATIO: %.6f\n", vmexit_mean / results->mean_timing);
    printf("\n");
}

// ============================================================================
// 2. THREAD SCHEDULING ANALYSIS
// ============================================================================

typedef struct {
    int thread_id;
    uint64_t* execution_times;
    volatile int* sync_counter;
    pthread_barrier_t* barrier;
} thread_data_t;

typedef struct {
    uint64_t* all_execution_times;
    double mean_execution;
    double variance;
    double coefficient_variation;
    double skewness;
    double kurtosis;
    uint64_t benchmark_time;
    int total_samples;
} scheduling_results_t;

void* worker_thread(void* arg) {
    thread_data_t* data = (thread_data_t*)arg;
    
    for (int i = 0; i < THREAD_ITERATIONS; i++) {
        // Wait for all threads to be ready
        pthread_barrier_wait(data->barrier);
        
        uint64_t start = get_timestamp();
        
        // CPU-bound work
        volatile int work = 0;
        for (int j = 0; j < THREAD_WORK_CYCLES; j++) {
            work += j * data->thread_id;
        }
        
        // Brief yield to encourage scheduling
        sched_yield();
        
        uint64_t end = get_timestamp();
        data->execution_times[i] = end - start;
        
        // Increment sync counter
        __sync_fetch_and_add(data->sync_counter, 1);
    }
    
    return NULL;
}

void test_thread_scheduling(scheduling_results_t* results) {
    printf("=== Thread Scheduling Analysis ===\n");
    
    pthread_t threads[THREAD_COUNT];
    thread_data_t thread_data[THREAD_COUNT];
    pthread_barrier_t barrier;
    volatile int sync_counter = 0;
    
    // Initialize barrier
    pthread_barrier_init(&barrier, NULL, THREAD_COUNT);
    
    // Allocate memory for results
    results->total_samples = THREAD_COUNT * THREAD_ITERATIONS;
    results->all_execution_times = malloc(results->total_samples * sizeof(uint64_t));
    
    // Benchmark: Single-threaded equivalent work
    uint64_t bench_start = get_timestamp();
    volatile int work = 0;
    for (int i = 0; i < THREAD_WORK_CYCLES; i++) {
        work += i;
    }
    uint64_t bench_end = get_timestamp();
    results->benchmark_time = bench_end - bench_start;
    
    // Setup thread data
    for (int i = 0; i < THREAD_COUNT; i++) {
        thread_data[i].thread_id = i;
        thread_data[i].execution_times = malloc(THREAD_ITERATIONS * sizeof(uint64_t));
        thread_data[i].sync_counter = &sync_counter;
        thread_data[i].barrier = &barrier;
    }
    
    // Create and run threads
    for (int i = 0; i < THREAD_COUNT; i++) {
        pthread_create(&threads[i], NULL, worker_thread, &thread_data[i]);
    }
    
    // Wait for all threads to complete
    for (int i = 0; i < THREAD_COUNT; i++) {
        pthread_join(threads[i], NULL);
    }
    
    // Collect all timing data
    int idx = 0;
    for (int i = 0; i < THREAD_COUNT; i++) {
        for (int j = 0; j < THREAD_ITERATIONS; j++) {
            results->all_execution_times[idx++] = thread_data[i].execution_times[j];
        }
    }
    
    // Calculate statistics
    results->mean_execution = calculate_mean(results->all_execution_times, results->total_samples);
    results->variance = calculate_variance(results->all_execution_times, results->total_samples, results->mean_execution);
    results->coefficient_variation = sqrt(results->variance) / results->mean_execution;
    results->skewness = calculate_skewness(results->all_execution_times, results->total_samples, results->mean_execution, results->variance);
    results->kurtosis = calculate_kurtosis(results->all_execution_times, results->total_samples, results->mean_execution, results->variance);
    
    // Output results
    printf("THREAD_BENCHMARK_CYCLES: %lu\n", results->benchmark_time);
    printf("THREAD_MEAN_EXECUTION: %.2f\n", results->mean_execution);
    printf("THREAD_VARIANCE: %.2f\n", results->variance);
    printf("THREAD_COEFFICIENT_VARIATION: %.6f\n", results->coefficient_variation);
    printf("THREAD_SKEWNESS: %.6f\n", results->skewness);
    printf("THREAD_KURTOSIS: %.6f\n", results->kurtosis);
    printf("THREAD_TOTAL_SAMPLES: %d\n", results->total_samples);
    printf("THREAD_OVERHEAD_RATIO: %.6f\n", results->mean_execution / results->benchmark_time);
    printf("\n");
    
    // Cleanup
    for (int i = 0; i < THREAD_COUNT; i++) {
        free(thread_data[i].execution_times);
    }
    pthread_barrier_destroy(&barrier);
}

// ============================================================================
// 3. CACHE BEHAVIOR ANALYSIS
// ============================================================================

typedef struct {
    uint64_t* cache_miss_times;
    uint64_t* cache_hit_times;
    uint64_t* flush_times;
    double cache_miss_mean;
    double cache_hit_mean;
    double cache_ratio;
    double flush_variance;
    uint64_t benchmark_time;
} cache_results_t;

void test_cache_behavior(cache_results_t* results) {
    printf("=== Cache Behavior Analysis ===\n");
    
    results->cache_miss_times = malloc(CACHE_ITERATIONS * sizeof(uint64_t));
    results->cache_hit_times = malloc(CACHE_ITERATIONS * sizeof(uint64_t));
    results->flush_times = malloc(CACHE_ITERATIONS * sizeof(uint64_t));
    
    // Allocate large memory buffer for cache testing
    volatile char* cache_buffer = malloc(CACHE_MEMORY_SIZE);
    if (!cache_buffer) {
        printf("Failed to allocate cache test buffer\n");
        return;
    }
    
    // Benchmark: Basic memory access
    uint64_t bench_start = get_timestamp();
    for (int i = 0; i < 1000; i++) {
        cache_buffer[i * CACHE_LINE_SIZE] = i;
    }
    uint64_t bench_end = get_timestamp();
    results->benchmark_time = bench_end - bench_start;
    
    // Test 1: Cache miss timing (first access to cache lines)
    for (int i = 0; i < CACHE_ITERATIONS; i++) {
        int offset = (i * CACHE_LINE_SIZE) % CACHE_MEMORY_SIZE;
        
        // Ensure cache line is not present
        __builtin___clear_cache((char*)&cache_buffer[offset], (char*)&cache_buffer[offset + CACHE_LINE_SIZE]);
        
        uint64_t start = get_timestamp();
        volatile char dummy = cache_buffer[offset]; // Force cache miss
        uint64_t end = get_timestamp();
        
        results->cache_miss_times[i] = end - start;
    }
    
    // Test 2: Cache hit timing (second access to same cache lines)
    for (int i = 0; i < CACHE_ITERATIONS; i++) {
        int offset = (i * CACHE_LINE_SIZE) % CACHE_MEMORY_SIZE;
        
        // Prime the cache
        volatile char prime = cache_buffer[offset];
        
        uint64_t start = get_timestamp();
        volatile char dummy = cache_buffer[offset]; // Should be cache hit
        uint64_t end = get_timestamp();
        
        results->cache_hit_times[i] = end - start;
    }
    
    // Test 3: Cache flush timing (VM behavior difference)
    for (int i = 0; i < CACHE_ITERATIONS; i++) {
        uint64_t start = get_timestamp();
        
        // Attempt to flush cache
        __builtin___clear_cache((char*)cache_buffer, (char*)cache_buffer + CACHE_MEMORY_SIZE);
        
        uint64_t end = get_timestamp();
        results->flush_times[i] = end - start;
    }
    
    // Calculate statistics
    results->cache_miss_mean = calculate_mean(results->cache_miss_times, CACHE_ITERATIONS);
    results->cache_hit_mean = calculate_mean(results->cache_hit_times, CACHE_ITERATIONS);
    results->cache_ratio = results->cache_miss_mean / results->cache_hit_mean;
    results->flush_variance = calculate_variance(results->flush_times, CACHE_ITERATIONS, 
                                               calculate_mean(results->flush_times, CACHE_ITERATIONS));
    
    // Output results
    printf("CACHE_BENCHMARK_CYCLES: %lu\n", results->benchmark_time);
    printf("CACHE_MISS_MEAN: %.2f\n", results->cache_miss_mean);
    printf("CACHE_HIT_MEAN: %.2f\n", results->cache_hit_mean);
    printf("CACHE_MISS_HIT_RATIO: %.6f\n", results->cache_ratio);
    printf("CACHE_FLUSH_VARIANCE: %.2f\n", results->flush_variance);
    printf("CACHE_ACCESS_PATTERN: %.6f\n", results->cache_miss_mean / results->benchmark_time);
    printf("\n");
    
    free((void*)cache_buffer);
}

// ============================================================================
// 4. MEMORY ALLOCATION PATTERN ANALYSIS
// ============================================================================

typedef struct {
    uint64_t* allocation_times;
    uint64_t* deallocation_times;
    uint64_t* reallocation_times;
    uintptr_t* allocation_addresses;
    double allocation_mean;
    double address_entropy;
    double fragmentation_index;
    uint64_t benchmark_time;
} memory_results_t;

void test_memory_allocation_patterns(memory_results_t* results) {
    printf("=== Memory Allocation Pattern Analysis ===\n");
    
    results->allocation_times = malloc(MEMORY_ITERATIONS * sizeof(uint64_t));
    results->deallocation_times = malloc(MEMORY_ITERATIONS * sizeof(uint64_t));
    results->reallocation_times = malloc(MEMORY_ITERATIONS * sizeof(uint64_t));
    results->allocation_addresses = malloc(MEMORY_ITERATIONS * sizeof(uintptr_t));
    
    void** allocated_ptrs = malloc(MEMORY_ITERATIONS * sizeof(void*));
    
    // Benchmark: Simple allocation/deallocation
    uint64_t bench_start = get_timestamp();
    void* bench_ptr = malloc(MEMORY_ALLOCATION_SIZE);
    free(bench_ptr);
    uint64_t bench_end = get_timestamp();
    results->benchmark_time = bench_end - bench_start;
    
    // Test 1: Allocation timing and address patterns
    for (int i = 0; i < MEMORY_ITERATIONS; i++) {
        uint64_t start = get_timestamp();
        allocated_ptrs[i] = malloc(MEMORY_ALLOCATION_SIZE);
        uint64_t end = get_timestamp();
        
        results->allocation_times[i] = end - start;
        results->allocation_addresses[i] = (uintptr_t)allocated_ptrs[i];
    }
    
    // Test 2: Deallocation timing
    for (int i = 0; i < MEMORY_ITERATIONS; i++) {
        uint64_t start = get_timestamp();
        free(allocated_ptrs[i]);
        uint64_t end = get_timestamp();
        
        results->deallocation_times[i] = end - start;
    }
    
    // Test 3: Reallocation patterns
    for (int i = 0; i < MEMORY_ITERATIONS; i++) {
        void* ptr = malloc(MEMORY_ALLOCATION_SIZE);
        
        uint64_t start = get_timestamp();
        ptr = realloc(ptr, MEMORY_ALLOCATION_SIZE * 2);
        uint64_t end = get_timestamp();
        
        results->reallocation_times[i] = end - start;
        free(ptr);
    }
    
    // Calculate statistics
    results->allocation_mean = calculate_mean(results->allocation_times, MEMORY_ITERATIONS);
    
    // Calculate address entropy (measure of address space randomization)
    uint64_t address_variance = 0;
    uintptr_t min_addr = results->allocation_addresses[0];
    uintptr_t max_addr = results->allocation_addresses[0];
    
    for (int i = 1; i < MEMORY_ITERATIONS; i++) {
        if (results->allocation_addresses[i] < min_addr) min_addr = results->allocation_addresses[i];
        if (results->allocation_addresses[i] > max_addr) max_addr = results->allocation_addresses[i];
    }
    
    results->address_entropy = (double)(max_addr - min_addr) / MEMORY_ITERATIONS;
    
    // Calculate fragmentation index (address distribution pattern)
    double addr_gaps_sum = 0;
    for (int i = 1; i < MEMORY_ITERATIONS; i++) {
        addr_gaps_sum += abs((long)(results->allocation_addresses[i] - results->allocation_addresses[i-1]));
    }
    results->fragmentation_index = addr_gaps_sum / MEMORY_ITERATIONS;
    
    // Output results
    printf("MEMORY_BENCHMARK_CYCLES: %lu\n", results->benchmark_time);
    printf("MEMORY_ALLOCATION_MEAN: %.2f\n", results->allocation_mean);
    printf("MEMORY_DEALLOCATION_MEAN: %.2f\n", calculate_mean(results->deallocation_times, MEMORY_ITERATIONS));
    printf("MEMORY_REALLOCATION_MEAN: %.2f\n", calculate_mean(results->reallocation_times, MEMORY_ITERATIONS));
    printf("MEMORY_ADDRESS_ENTROPY: %.2f\n", results->address_entropy);
    printf("MEMORY_FRAGMENTATION_INDEX: %.2f\n", results->fragmentation_index);
    printf("MEMORY_ADDRESS_RANGE: %lu\n", max_addr - min_addr);
    printf("MEMORY_ALLOCATION_VARIANCE: %.2f\n", calculate_variance(results->allocation_times, MEMORY_ITERATIONS, results->allocation_mean));
    printf("\n");
    
    free(allocated_ptrs);
}

// ============================================================================
// MAIN FUNCTION
// ============================================================================

int main(int argc, char* argv[]) {
    printf("=== VM Detection Data Collection - C Implementation ===\n");
    printf("Test Configuration:\n");
    printf("RDTSC_ITERATIONS: %d\n", RDTSC_ITERATIONS);
    printf("THREAD_ITERATIONS: %d\n", THREAD_ITERATIONS);
    printf("THREAD_COUNT: %d\n", THREAD_COUNT);
    printf("CACHE_ITERATIONS: %d\n", CACHE_ITERATIONS);
    printf("MEMORY_ITERATIONS: %d\n", MEMORY_ITERATIONS);
    printf("\n");
    
    // Initialize results structures
    rdtsc_results_t rdtsc_results = {0};
    scheduling_results_t scheduling_results = {0};
    cache_results_t cache_results = {0};
    memory_results_t memory_results = {0};
    
    // Run all tests
    test_rdtsc_basic_timing(&rdtsc_results);
    test_thread_scheduling(&scheduling_results);
    test_cache_behavior(&cache_results);
    test_memory_allocation_patterns(&memory_results);
    
    // Output summary for ML processing
    printf("=== SUMMARY FOR ML CLASSIFICATION ===\n");
    printf("OVERALL_RDTSC_CV: %.6f\n", rdtsc_results.coefficient_variation);
    printf("OVERALL_THREAD_CV: %.6f\n", scheduling_results.coefficient_variation);
    printf("OVERALL_CACHE_RATIO: %.6f\n", cache_results.cache_ratio);
    printf("OVERALL_MEMORY_ENTROPY: %.2f\n", memory_results.address_entropy);
    printf("DETECTION_CONFIDENCE: %.6f\n", 
           (rdtsc_results.coefficient_variation + scheduling_results.coefficient_variation) / 2.0);
    
    // Cleanup
    free(rdtsc_results.raw_timings);
    free(rdtsc_results.consecutive_diffs);
    free(rdtsc_results.vm_exit_timings);
    free(scheduling_results.all_execution_times);
    free(cache_results.cache_miss_times);
    free(cache_results.cache_hit_times);
    free(cache_results.flush_times);
    free(memory_results.allocation_times);
    free(memory_results.deallocation_times);
    free(memory_results.reallocation_times);
    free(memory_results.allocation_addresses);
    
    return 0;
}
