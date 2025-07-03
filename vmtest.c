/*
 * VMtest - System Measurements Tool (Pure Measurements Only)
 * Extracts timing, scheduling, cache, and memory measurements
 * Based on research from Lin et al. (2021) and other academic sources
 * 
 * This version collects only raw measurements without VM detection logic
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/utsname.h>
#include <errno.h>
#include <stdint.h>

#ifdef __linux__
#include <sched.h>
#include <sys/sysinfo.h>
#endif

#ifdef __APPLE__
#include <sys/sysctl.h>
#endif

// Constants
#define ITERATIONS 1000
#define THREAD_COUNT 4
#define CACHE_SIZE (1024 * 1024)  // 1MB
#define MAX_SAMPLES 10000

// Utility function to get high-resolution time in nanoseconds
static inline long long get_time_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

// Structure to hold system information
typedef struct {
    char platform[256];
    char hostname[256];
    char machine[256];
    int cpu_count;
    long total_memory;
    long cpu_freq_mhz;
} system_info_t;

// Structure to hold all measurements
typedef struct {
    // Basic timing measurements
    double timing_basic_mean;
    double timing_basic_variance;
    double timing_basic_cv;
    double timing_basic_skewness;
    double timing_basic_kurtosis;
    
    // Consecutive timing measurements
    double timing_consecutive_mean;
    double timing_consecutive_variance;
    double timing_consecutive_cv;
    double timing_consecutive_skewness;
    double timing_consecutive_kurtosis;
    
    // Thread scheduling measurements
    double scheduling_thread_mean;
    double scheduling_thread_variance;
    double scheduling_thread_cv;
    double scheduling_thread_skewness;
    double scheduling_thread_kurtosis;
    double physical_machine_index;
    
    // Multiprocessing measurements
    double scheduling_multiproc_mean;
    double scheduling_multiproc_variance;
    double scheduling_multiproc_cv;
    double scheduling_multiproc_skewness;
    double scheduling_multiproc_kurtosis;
    double multiproc_physical_machine_index;
    
    // Cache measurements
    double cache_access_ratio;
    double cache_miss_ratio;
    
    // Memory measurements
    double memory_address_entropy;
    
    // Composite measurements
    double overall_timing_cv;
    double overall_scheduling_cv;
} measurements_t;

// Global variables
system_info_t system_info = {0};
measurements_t measurements = {0};

// Statistical calculation functions
double calculate_mean(double *values, int count) {
    if (count == 0) return 0.0;
    double sum = 0.0;
    for (int i = 0; i < count; i++) {
        sum += values[i];
    }
    return sum / count;
}

double calculate_variance(double *values, int count) {
    if (count <= 1) return 0.0;
    
    double mean = calculate_mean(values, count);
    double sum_squared_diff = 0.0;
    
    for (int i = 0; i < count; i++) {
        double diff = values[i] - mean;
        sum_squared_diff += diff * diff;
    }
    
    return sum_squared_diff / (count - 1);
}

double calculate_coefficient_of_variation(double *values, int count) {
    if (count == 0) return 0.0;
    
    double mean = calculate_mean(values, count);
    if (mean == 0.0) return 0.0;
    
    double variance = calculate_variance(values, count);
    double std_dev = sqrt(variance);
    
    return std_dev / mean;
}

double calculate_skewness(double *values, int count) {
    if (count < 3) return 0.0;
    
    double mean = calculate_mean(values, count);
    double variance = calculate_variance(values, count);
    if (variance <= 0) return 0.0;
    
    double std_dev = sqrt(variance);
    double m3 = 0.0;
    
    for (int i = 0; i < count; i++) {
        double diff = values[i] - mean;
        m3 += diff * diff * diff;
    }
    m3 /= count;
    
    double skew = m3 / (std_dev * std_dev * std_dev);
    
    // Apply bias correction
    if (count > 2) {
        double adjustment = sqrt(count * (count - 1.0)) / (count - 2.0);
        skew *= adjustment;
    }
    
    return skew;
}

double calculate_kurtosis(double *values, int count) {
    if (count < 4) return 0.0;
    
    double mean = calculate_mean(values, count);
    double variance = calculate_variance(values, count);
    if (variance <= 0) return 0.0;
    
    double std_dev = sqrt(variance);
    double m4 = 0.0;
    
    for (int i = 0; i < count; i++) {
        double diff = values[i] - mean;
        m4 += diff * diff * diff * diff;
    }
    m4 /= count;
    
    double kurt = m4 / (variance * variance) - 3.0;  // Excess kurtosis
    
    // Apply bias correction
    if (count > 3) {
        double n = count;
        double adjustment = ((n - 1.0) * ((n + 1.0) * kurt + 6.0)) / ((n - 2.0) * (n - 3.0));
        kurt = adjustment;
    }
    
    return kurt;
}

double calculate_entropy(double *values, int count) {
    if (count == 0) return 0.0;
    
    // Find min and max
    double min_val = values[0];
    double max_val = values[0];
    for (int i = 1; i < count; i++) {
        if (values[i] < min_val) min_val = values[i];
        if (values[i] > max_val) max_val = values[i];
    }
    
    if (min_val == max_val) return 0.0;
    
    // Create histogram with 20 bins
    int bins = 20;
    int *hist = calloc(bins, sizeof(int));
    if (!hist) return 0.0;
    
    double bin_width = (max_val - min_val) / bins;
    
    // Fill histogram
    for (int i = 0; i < count; i++) {
        int bin_idx = (int)((values[i] - min_val) / bin_width);
        if (bin_idx >= bins) bin_idx = bins - 1;
        hist[bin_idx]++;
    }
    
    // Calculate entropy
    double entropy = 0.0;
    for (int i = 0; i < bins; i++) {
        if (hist[i] > 0) {
            double p = (double)hist[i] / count;
            entropy -= p * log2(p);
        }
    }
    
    free(hist);
    return entropy;
}

// Calculate raw Physical Machine Index (no logarithm)
double calculate_raw_pmi(double kurtosis, double skewness, double variance) {
    if (variance <= 0) return -100.0;
    return (kurtosis * skewness) / variance;
}

// System information gathering
void gather_system_info() {
    struct utsname uts;
    if (uname(&uts) == 0) {
        snprintf(system_info.platform, sizeof(system_info.platform), "%s %s", uts.sysname, uts.release);
        strncpy(system_info.hostname, uts.nodename, sizeof(system_info.hostname) - 1);
        strncpy(system_info.machine, uts.machine, sizeof(system_info.machine) - 1);
    }
    
    // Get CPU count
#ifdef __linux__
    system_info.cpu_count = get_nprocs();
    
    // Get memory info
    struct sysinfo si;
    if (sysinfo(&si) == 0) {
        system_info.total_memory = si.totalram * si.mem_unit;
    }
#elif defined(__APPLE__)
    size_t size = sizeof(system_info.cpu_count);
    sysctlbyname("hw.ncpu", &system_info.cpu_count, &size, NULL, 0);
    
    size_t mem_size = sizeof(system_info.total_memory);
    sysctlbyname("hw.memsize", &system_info.total_memory, &mem_size, NULL, 0);
#else
    system_info.cpu_count = 1;
    system_info.total_memory = 0;
#endif
    
    // Estimate CPU frequency (rough approximation)
    system_info.cpu_freq_mhz = 2000;  // Default assumption
}

// CPU workload function
void cpu_workload() {
    volatile long result = 0;
    for (int i = 0; i < 10000; i++) {
        result += i * i;
    }
}

// Basic timing measurements
void measure_basic_timing() {
    printf("Measuring basic timing patterns...\n");
    
    double *timings = malloc(ITERATIONS * sizeof(double));
    if (!timings) {
        fprintf(stderr, "Error: Failed to allocate memory for timings\n");
        return;
    }
    
    for (int i = 0; i < ITERATIONS; i++) {
        long long start = get_time_ns();
        cpu_workload();
        long long end = get_time_ns();
        timings[i] = (double)(end - start);
    }
    
    measurements.timing_basic_mean = calculate_mean(timings, ITERATIONS);
    measurements.timing_basic_variance = calculate_variance(timings, ITERATIONS);
    measurements.timing_basic_cv = calculate_coefficient_of_variation(timings, ITERATIONS);
    measurements.timing_basic_skewness = calculate_skewness(timings, ITERATIONS);
    measurements.timing_basic_kurtosis = calculate_kurtosis(timings, ITERATIONS);
    
    free(timings);
}

// Consecutive timing measurements
void measure_consecutive_timing() {
    printf("Measuring consecutive timing patterns...\n");
    
    double *timings = malloc(ITERATIONS * sizeof(double));
    if (!timings) {
        fprintf(stderr, "Error: Failed to allocate memory for consecutive timings\n");
        return;
    }
    
    for (int i = 0; i < ITERATIONS; i++) {
        long long start = get_time_ns();
        cpu_workload();
        cpu_workload();  // Two consecutive operations
        long long end = get_time_ns();
        timings[i] = (double)(end - start);
    }
    
    measurements.timing_consecutive_mean = calculate_mean(timings, ITERATIONS);
    measurements.timing_consecutive_variance = calculate_variance(timings, ITERATIONS);
    measurements.timing_consecutive_cv = calculate_coefficient_of_variation(timings, ITERATIONS);
    measurements.timing_consecutive_skewness = calculate_skewness(timings, ITERATIONS);
    measurements.timing_consecutive_kurtosis = calculate_kurtosis(timings, ITERATIONS);
    
    free(timings);
}

// Thread scheduling measurements
pthread_mutex_t thread_mutex = PTHREAD_MUTEX_INITIALIZER;
int thread_counter = 0;

void* thread_workload(void* arg) {
    volatile long result = 0;
    for (int i = 0; i < 5000; i++) {
        result += i * i;
    }
    
    pthread_mutex_lock(&thread_mutex);
    thread_counter++;
    pthread_mutex_unlock(&thread_mutex);
    
    return NULL;
}

void measure_thread_scheduling() {
    printf("Measuring thread scheduling patterns...\n");
    
    int num_tests = ITERATIONS / 10;
    double *timings = malloc(num_tests * sizeof(double));
    if (!timings) {
        fprintf(stderr, "Error: Failed to allocate memory for thread timings\n");
        return;
    }
    
    for (int test = 0; test < num_tests; test++) {
        pthread_t threads[THREAD_COUNT];
        thread_counter = 0;
        
        long long start = get_time_ns();
        
        // Create and start threads
        for (int i = 0; i < THREAD_COUNT; i++) {
            if (pthread_create(&threads[i], NULL, thread_workload, NULL) != 0) {
                fprintf(stderr, "Error: Failed to create thread\n");
                continue;
            }
        }
        
        // Wait for all threads
        for (int i = 0; i < THREAD_COUNT; i++) {
            pthread_join(threads[i], NULL);
        }
        
        long long end = get_time_ns();
        timings[test] = (double)(end - start);
    }
    
    measurements.scheduling_thread_mean = calculate_mean(timings, num_tests);
    measurements.scheduling_thread_variance = calculate_variance(timings, num_tests);
    measurements.scheduling_thread_cv = calculate_coefficient_of_variation(timings, num_tests);
    measurements.scheduling_thread_skewness = calculate_skewness(timings, num_tests);
    measurements.scheduling_thread_kurtosis = calculate_kurtosis(timings, num_tests);
    
    // Calculate raw PMI
    measurements.physical_machine_index = calculate_raw_pmi(
        measurements.scheduling_thread_kurtosis,
        measurements.scheduling_thread_skewness,
        measurements.scheduling_thread_variance
    );
    
    free(timings);
}

// Multiprocessing measurements
void measure_multiprocessing_scheduling() {
    printf("Measuring multiprocessing scheduling patterns...\n");
    
    int num_tests = ITERATIONS / 50;  // Fewer tests for multiprocessing
    double *timings = malloc(num_tests * sizeof(double));
    if (!timings) {
        fprintf(stderr, "Error: Failed to allocate memory for multiproc timings\n");
        return;
    }
    
    int proc_count = 0;
    
    for (int test = 0; test < num_tests; test++) {
        long long start = get_time_ns();
        
        pid_t pid = fork();
        if (pid == 0) {
            // Child process - do some work
            volatile double result = 0.0;
            for (int j = 0; j < 100000; j++) {
                result += sqrt(j) * sin(j) + cos(j * 0.1);
            }
            exit(0);
        } else if (pid > 0) {
            // Parent process - wait for child
            int status;
            waitpid(pid, &status, 0);
            
            long long end = get_time_ns();
            timings[proc_count++] = (double)(end - start);
        }
    }
    
    if (proc_count > 0) {
        measurements.scheduling_multiproc_mean = calculate_mean(timings, proc_count);
        measurements.scheduling_multiproc_variance = calculate_variance(timings, proc_count);
        measurements.scheduling_multiproc_cv = calculate_coefficient_of_variation(timings, proc_count);
        measurements.scheduling_multiproc_skewness = calculate_skewness(timings, proc_count);
        measurements.scheduling_multiproc_kurtosis = calculate_kurtosis(timings, proc_count);
        
        // Calculate raw PMI for multiprocessing
        measurements.multiproc_physical_machine_index = calculate_raw_pmi(
            measurements.scheduling_multiproc_kurtosis,
            measurements.scheduling_multiproc_skewness,
            measurements.scheduling_multiproc_variance
        );
    }
    
    free(timings);
}

// Cache behavior measurements
void measure_cache_behavior() {
    printf("Measuring cache behavior patterns...\n");
    
    // Allocate large array
    double *data = malloc(CACHE_SIZE * sizeof(double));
    if (!data) {
        fprintf(stderr, "Error: Failed to allocate memory for cache test\n");
        measurements.cache_access_ratio = 1.0;
        measurements.cache_miss_ratio = 0.0;
        return;
    }
    
    // Initialize with random values
    for (int i = 0; i < CACHE_SIZE; i++) {
        data[i] = (double)rand() / RAND_MAX;
    }
    
    // Cache-friendly access pattern
    double cache_friendly_times[100];
    for (int i = 0; i < 100; i++) {
        long long start = get_time_ns();
        double sum = 0.0;
        for (int j = 0; j < CACHE_SIZE; j++) {
            sum += data[j];
        }
        long long end = get_time_ns();
        cache_friendly_times[i] = (double)(end - start);
        
        // Prevent optimization
        if (sum == 0.0) printf("");
    }
    
    // Create random indices for cache-unfriendly access
    int *indices = malloc(CACHE_SIZE * sizeof(int));
    if (!indices) {
        free(data);
        return;
    }
    
    for (int i = 0; i < CACHE_SIZE; i++) {
        indices[i] = i;
    }
    
    // Shuffle indices (Fisher-Yates shuffle)
    for (int i = CACHE_SIZE - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        int temp = indices[i];
        indices[i] = indices[j];
        indices[j] = temp;
    }
    
    // Cache-unfriendly access pattern
    double cache_unfriendly_times[100];
    for (int i = 0; i < 100; i++) {
        long long start = get_time_ns();
        double sum = 0.0;
        for (int j = 0; j < CACHE_SIZE; j += 1000) {
            sum += data[indices[j]];
        }
        long long end = get_time_ns();
        cache_unfriendly_times[i] = (double)(end - start);
        
        // Prevent optimization
        if (sum == 0.0) printf("");
    }
    
    double cache_friendly_mean = calculate_mean(cache_friendly_times, 100);
    double cache_unfriendly_mean = calculate_mean(cache_unfriendly_times, 100);
    
    if (cache_friendly_mean > 0) {
        measurements.cache_access_ratio = cache_unfriendly_mean / cache_friendly_mean;
        measurements.cache_miss_ratio = (cache_unfriendly_mean - cache_friendly_mean) / cache_friendly_mean;
    } else {
        measurements.cache_access_ratio = 1.0;
        measurements.cache_miss_ratio = 0.0;
    }
    
    free(data);
    free(indices);
}

// Memory entropy measurements
void measure_memory_entropy() {
    printf("Measuring memory entropy patterns...\n");
    
    void **addresses = malloc(1000 * sizeof(void*));
    double *address_values = malloc(1000 * sizeof(double));
    
    if (!addresses || !address_values) {
        fprintf(stderr, "Error: Failed to allocate memory for entropy test\n");
        measurements.memory_address_entropy = 0.0;
        if (addresses) free(addresses);
        if (address_values) free(address_values);
        return;
    }
    
    // Collect addresses from multiple allocation patterns
    for (int i = 0; i < 1000; i++) {
        // Use different allocation sizes to get varied addresses
        size_t size = 1024 + (i * 16);
        addresses[i] = malloc(size);
        if (addresses[i]) {
            address_values[i] = (double)((uintptr_t)addresses[i]);
        } else {
            address_values[i] = 0.0;
        }
    }
    
    // Calculate entropy with improved method
    measurements.memory_address_entropy = calculate_entropy(address_values, 1000);
    
    // Ensure minimum entropy for bare metal systems
    if (measurements.memory_address_entropy < 1.0) {
        // Recalculate using address differences for better entropy
        double *diffs = malloc(999 * sizeof(double));
        if (diffs) {
            for (int i = 0; i < 999; i++) {
                diffs[i] = address_values[i+1] - address_values[i];
            }
            double diff_entropy = calculate_entropy(diffs, 999);
            measurements.memory_address_entropy = diff_entropy;
            free(diffs);
        }
    }
    
    // Clean up
    for (int i = 0; i < 1000; i++) {
        if (addresses[i]) free(addresses[i]);
    }
    free(addresses);
    free(address_values);
}

// Calculate composite measurements
void calculate_composite_measurements() {
    printf("Calculating composite measurements...\n");
    
    // Overall timing CV
    double timing_cv_sum = 0.0;
    int timing_cv_count = 0;
    
    if (measurements.timing_basic_cv > 0) {
        timing_cv_sum += measurements.timing_basic_cv;
        timing_cv_count++;
    }
    if (measurements.timing_consecutive_cv > 0) {
        timing_cv_sum += measurements.timing_consecutive_cv;
        timing_cv_count++;
    }
    
    measurements.overall_timing_cv = timing_cv_count > 0 ? timing_cv_sum / timing_cv_count : 0.0;
    
    // Overall scheduling CV
    double scheduling_cv_sum = 0.0;
    int scheduling_cv_count = 0;
    
    if (measurements.scheduling_thread_cv > 0) {
        scheduling_cv_sum += measurements.scheduling_thread_cv;
        scheduling_cv_count++;
    }
    if (measurements.scheduling_multiproc_cv > 0) {
        scheduling_cv_sum += measurements.scheduling_multiproc_cv;
        scheduling_cv_count++;
    }
    
    measurements.overall_scheduling_cv = scheduling_cv_count > 0 ? scheduling_cv_sum / scheduling_cv_count : 0.0;
}

// Print results in JSON format
void print_results_json() {
    printf("{\n");
    
    // System information
    printf("  \"system_info\": {\n");
    printf("    \"platform\": \"%s\",\n", system_info.platform);
    printf("    \"hostname\": \"%s\",\n", system_info.hostname);
    printf("    \"machine\": \"%s\",\n", system_info.machine);
    printf("    \"cpu_count\": %d,\n", system_info.cpu_count);
    printf("    \"total_memory\": %ld,\n", system_info.total_memory);
    printf("    \"cpu_freq_mhz\": %ld,\n", system_info.cpu_freq_mhz);
    printf("    \"timestamp\": %ld\n", time(NULL));
    printf("  },\n");
    
    // Pure measurements only
    printf("  \"measurements\": {\n");
    printf("    \"TIMING_BASIC_MEAN\": %.6f,\n", measurements.timing_basic_mean);
    printf("    \"TIMING_BASIC_VARIANCE\": %.6f,\n", measurements.timing_basic_variance);
    printf("    \"TIMING_BASIC_CV\": %.6f,\n", measurements.timing_basic_cv);
    printf("    \"TIMING_BASIC_SKEWNESS\": %.6f,\n", measurements.timing_basic_skewness);
    printf("    \"TIMING_BASIC_KURTOSIS\": %.6f,\n", measurements.timing_basic_kurtosis);
    printf("    \"TIMING_CONSECUTIVE_MEAN\": %.6f,\n", measurements.timing_consecutive_mean);
    printf("    \"TIMING_CONSECUTIVE_VARIANCE\": %.6f,\n", measurements.timing_consecutive_variance);
    printf("    \"TIMING_CONSECUTIVE_CV\": %.6f,\n", measurements.timing_consecutive_cv);
    printf("    \"TIMING_CONSECUTIVE_SKEWNESS\": %.6f,\n", measurements.timing_consecutive_skewness);
    printf("    \"TIMING_CONSECUTIVE_KURTOSIS\": %.6f,\n", measurements.timing_consecutive_kurtosis);
    printf("    \"SCHEDULING_THREAD_MEAN\": %.6f,\n", measurements.scheduling_thread_mean);
    printf("    \"SCHEDULING_THREAD_VARIANCE\": %.6f,\n", measurements.scheduling_thread_variance);
    printf("    \"SCHEDULING_THREAD_CV\": %.6f,\n", measurements.scheduling_thread_cv);
    printf("    \"SCHEDULING_THREAD_SKEWNESS\": %.6f,\n", measurements.scheduling_thread_skewness);
    printf("    \"SCHEDULING_THREAD_KURTOSIS\": %.6f,\n", measurements.scheduling_thread_kurtosis);
    printf("    \"PHYSICAL_MACHINE_INDEX\": %.12g,\n", measurements.physical_machine_index);
    printf("    \"SCHEDULING_MULTIPROC_MEAN\": %.6f,\n", measurements.scheduling_multiproc_mean);
    printf("    \"SCHEDULING_MULTIPROC_VARIANCE\": %.6f,\n", measurements.scheduling_multiproc_variance);
    printf("    \"SCHEDULING_MULTIPROC_CV\": %.6f,\n", measurements.scheduling_multiproc_cv);
    printf("    \"SCHEDULING_MULTIPROC_SKEWNESS\": %.6f,\n", measurements.scheduling_multiproc_skewness);
    printf("    \"SCHEDULING_MULTIPROC_KURTOSIS\": %.6f,\n", measurements.scheduling_multiproc_kurtosis);
    printf("    \"MULTIPROC_PHYSICAL_MACHINE_INDEX\": %.12g,\n", measurements.multiproc_physical_machine_index);
    printf("    \"CACHE_ACCESS_RATIO\": %.6f,\n", measurements.cache_access_ratio);
    printf("    \"CACHE_MISS_RATIO\": %.6f,\n", measurements.cache_miss_ratio);
    printf("    \"MEMORY_ADDRESS_ENTROPY\": %.6f,\n", measurements.memory_address_entropy);
    printf("    \"OVERALL_TIMING_CV\": %.6f,\n", measurements.overall_timing_cv);
    printf("    \"OVERALL_SCHEDULING_CV\": %.6f\n", measurements.overall_scheduling_cv);
    printf("  },\n");
    
    // Metadata
    printf("  \"timestamp\": \"%ld\",\n", time(NULL));
    printf("  \"language\": \"c\",\n");
    printf("  \"version\": \"1.0.0\"\n");
    printf("}\n");
}

// Main function
int main(int argc, char *argv[]) {
    printf("VMtest - System Measurements Tool\n");
    printf("=================================\n\n");
    
    // Parse command line arguments
    int iterations = ITERATIONS;
    if (argc > 1) {
        iterations = atoi(argv[1]);
        if (iterations <= 0) iterations = ITERATIONS;
    }
    
    // Initialize random seed
    srand(time(NULL));
    
    // Gather system information
    gather_system_info();
    
    printf("Starting measurements...\n");
    printf("Platform: %s\n", system_info.platform);
    printf("CPU count: %d\n", system_info.cpu_count);
    printf("Iterations: %d\n", iterations);
    printf("\n");
    
    // Run all measurements
    measure_basic_timing();
    measure_consecutive_timing();
    measure_thread_scheduling();
    measure_multiprocessing_scheduling();
    measure_cache_behavior();
    measure_memory_entropy();
    calculate_composite_measurements();
    
    printf("\nMeasurements complete!\n\n");
    
    // Output results
    print_results_json();
    
    return 0;
}
