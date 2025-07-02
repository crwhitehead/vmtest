
#include <time.h>
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

#ifdef __linux__
#include <sched.h>
#include <sys/sysinfo.h>
#endif

#ifdef __APPLE__
#include <sys/sysctl.h>
#endif

#define ITERATIONS 1000
#define THREAD_COUNT 4
#define CACHE_SIZE (1024 * 1024)  // 1MB
// Utility function to get high-resolution time in nanoseconds
static inline long long get_time_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}// Structure to hold system information
typedef struct {
    char platform[256];
    char hostname[256];
    char kernel_version[256];
    char machine[256];
    int cpu_count;
    long total_memory;
    long cpu_freq_mhz;
} system_info_t;

// Global system info
system_info_t system_info = {0};/*
 * VMTEST Environment Measurements - C Version
 * Extracts timing, scheduling, cache, and memory measurements to detect virtualization
 * Based on research from Lin et al. (2021) and other VM detection papers
 */

// Structure to hold all measurements
typedef struct {
    double timing_basic_mean;
    double timing_basic_variance;
    double timing_basic_cv;
    double timing_basic_skewness;
    double timing_basic_kurtosis;
    
    double scheduling_thread_mean;
    double scheduling_thread_variance;
    double scheduling_thread_cv;
    double scheduling_thread_skewness;
    double scheduling_thread_kurtosis;
    double physical_machine_index;
    
    double scheduling_multiproc_mean;
    double scheduling_multiproc_variance;
    double scheduling_multiproc_cv;
    
    double timing_consecutive_mean;
    double timing_consecutive_variance;
    double timing_consecutive_cv;
    
    double cache_access_ratio;
    double cache_miss_ratio;
    
    double memory_address_entropy;
    
    double overall_timing_cv;
    double overall_scheduling_cv;
} vmtest_measurements_t;

// Global measurements structure
vmtest_measurements_t measurements = {0};

// Get CPU information from /proc/cpuinfo (Linux)
#ifdef __linux__
long get_cpu_freq_linux() {
    FILE *fp = fopen("/proc/cpuinfo", "r");
    if (!fp) return 0;
    
    char line[256];
    long freq_mhz = 0;
    
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "cpu MHz", 7) == 0) {
            char *colon = strchr(line, ':');
            if (colon) {
                freq_mhz = (long)atof(colon + 1);
                break;
            }
        }
    }
    
    fclose(fp);
    return freq_mhz;
}

// Get CPU model from /proc/cpuinfo (Linux)
void get_cpu_model_linux(char *buffer, size_t size) {
    FILE *fp = fopen("/proc/cpuinfo", "r");
    if (!fp) {
        strncpy(buffer, "Unknown", size);
        return;
    }
    
    char line[256];
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "model name", 10) == 0) {
            char *colon = strchr(line, ':');
            if (colon) {
                // Skip whitespace after colon
                colon++;
                while (*colon == ' ' || *colon == '\t') colon++;
                
                // Remove newline
                char *newline = strchr(colon, '\n');
                if (newline) *newline = '\0';
                
                strncpy(buffer, colon, size);
                buffer[size-1] = '\0';
                break;
            }
        }
    }
    
    fclose(fp);
}
#endif

// Gather system information
void gather_system_info() {
    printf("Gathering system information...\n");
    
    // Get basic system info using uname
    struct utsname uts;
    if (uname(&uts) == 0) {
        snprintf(system_info.platform, sizeof(system_info.platform), 
                 "%s %s", uts.sysname, uts.release);
        strncpy(system_info.hostname, uts.nodename, sizeof(system_info.hostname));
        strncpy(system_info.kernel_version, uts.version, sizeof(system_info.kernel_version));
        strncpy(system_info.machine, uts.machine, sizeof(system_info.machine));
    }
    
    // Get CPU count
    system_info.cpu_count = sysconf(_SC_NPROCESSORS_ONLN);
    
    // Get memory information
#ifdef __linux__
    struct sysinfo si;
    if (sysinfo(&si) == 0) {
        system_info.total_memory = si.totalram;
    }
    
    // Get CPU frequency
    system_info.cpu_freq_mhz = get_cpu_freq_linux();
    
#elif defined(__APPLE__)
    // macOS specific code
    size_t size = sizeof(system_info.total_memory);
    sysctlbyname("hw.memsize", &system_info.total_memory, &size, NULL, 0);
    
    size_t freq_size = sizeof(system_info.cpu_freq_mhz);
    uint64_t freq;
    if (sysctlbyname("hw.cpufrequency", &freq, &freq_size, NULL, 0) == 0) {
        system_info.cpu_freq_mhz = freq / 1000000;  // Convert Hz to MHz
    }
#else
    // Generic fallback
    long pages = sysconf(_SC_PHYS_PAGES);
    long page_size = sysconf(_SC_PAGE_SIZE);
    if (pages > 0 && page_size > 0) {
        system_info.total_memory = pages * page_size;
    }
#endif
}

// Print system information
void print_system_info() {
    printf("\n==================================================\n");
    printf("SYSTEM INFORMATION\n");
    printf("==================================================\n");
    
    printf("Platform: %s\n", system_info.platform);
    printf("Hostname: %s\n", system_info.hostname);
    printf("Machine: %s\n", system_info.machine);
    printf("CPU Count: %d\n", system_info.cpu_count);
    
    if (system_info.total_memory > 0) {
        printf("Total Memory: %.2f GB\n", system_info.total_memory / (1024.0 * 1024.0 * 1024.0));
    }
    
    if (system_info.cpu_freq_mhz > 0) {
        printf("CPU Frequency: %ld MHz\n", system_info.cpu_freq_mhz);
    }
    
#ifdef __linux__
    // Additional Linux-specific information
    char cpu_model[256] = {0};
    get_cpu_model_linux(cpu_model, sizeof(cpu_model));
    if (strlen(cpu_model) > 0) {
        printf("CPU Model: %s\n", cpu_model);
    }
    
    // Check for common virtualization indicators
    printf("\nVirtualization Hints:\n");
    
    // Check /proc/cpuinfo for hypervisor flag
    FILE *fp = fopen("/proc/cpuinfo", "r");
    if (fp) {
        char line[256];
        int found_hypervisor = 0;
        while (fgets(line, sizeof(line), fp)) {
            if (strstr(line, "hypervisor")) {
                found_hypervisor = 1;
                break;
            }
        }
        fclose(fp);
        printf("  Hypervisor flag in /proc/cpuinfo: %s\n", 
               found_hypervisor ? "Yes (VM likely)" : "No");
    }
    
    // Check for common VM files
    if (access("/proc/vz", F_OK) == 0) {
        printf("  OpenVZ detected: /proc/vz exists\n");
    }
    if (access("/proc/xen", F_OK) == 0) {
        printf("  Xen detected: /proc/xen exists\n");
    }
    
    // Check DMI/SMBIOS info if available
    fp = fopen("/sys/devices/virtual/dmi/id/sys_vendor", "r");
    if (fp) {
        char vendor[256] = {0};
        if (fgets(vendor, sizeof(vendor), fp)) {
            // Remove newline
            vendor[strcspn(vendor, "\n")] = 0;
            printf("  System Vendor: %s\n", vendor);
            
            // Check for known VM vendors
            if (strstr(vendor, "VMware") || strstr(vendor, "VirtualBox") || 
                strstr(vendor, "QEMU") || strstr(vendor, "Xen") ||
                strstr(vendor, "Microsoft Corporation") || strstr(vendor, "innotek")) {
                printf("  --> Known VM vendor detected!\n");
            }
        }
        fclose(fp);
    }
    
    fp = fopen("/sys/devices/virtual/dmi/id/product_name", "r");
    if (fp) {
        char product[256] = {0};
        if (fgets(product, sizeof(product), fp)) {
            product[strcspn(product, "\n")] = 0;
            printf("  Product Name: %s\n", product);
        }
        fclose(fp);
    }
#endif
    
    time_t now = time(NULL);
    printf("\nTimestamp: %s", ctime(&now));
}

// Statistical functions
double calculate_mean(double *values, int count) {
    if (count == 0) return 0.0;
    double sum = 0.0;
    for (int i = 0; i < count; i++) {
        sum += values[i];
    }
    return sum / count;
}

double calculate_variance(double *values, int count, double mean) {
    if (count < 2) return 0.0;
    double sum = 0.0;
    for (int i = 0; i < count; i++) {
        double diff = values[i] - mean;
        sum += diff * diff;
    }
    return sum / (count - 1);
}

double calculate_std_dev(double variance) {
    return sqrt(variance);
}

double calculate_cv(double std_dev, double mean) {
    if (mean == 0.0) return 0.0;
    return std_dev / mean;
}

double calculate_skewness(double *values, int count, double mean, double std_dev) {
    if (count < 3 || std_dev == 0.0) return 0.0;
    
    double sum = 0.0;
    for (int i = 0; i < count; i++) {
        double diff = values[i] - mean;
        sum += pow(diff, 3);
    }
    
    double skew = (sum / count) / pow(std_dev, 3);
    
    // Apply bias correction
    if (count > 2) {
        skew = skew * sqrt(count * (count - 1)) / (count - 2);
    }
    
    return skew;
}

double calculate_kurtosis(double *values, int count, double mean, double std_dev) {
    if (count < 4 || std_dev == 0.0) return 0.0;
    
    double sum = 0.0;
    for (int i = 0; i < count; i++) {
        double diff = values[i] - mean;
        sum += pow(diff, 4);
    }
    
    double kurt = (sum / count) / pow(std_dev, 4) - 3.0;  // Excess kurtosis
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

// CPU workload function
void cpu_workload() {
    volatile long result = 0;
    for (int i = 0; i < 10000; i++) {
        result += i * i;
    }
}

// Measure basic timing
void measure_timing_basic() {
    printf("1. Basic timing measurements...\n");
    
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
    
    double mean = calculate_mean(timings, ITERATIONS);
    double variance = calculate_variance(timings, ITERATIONS, mean);
    double std_dev = calculate_std_dev(variance);
    
    measurements.timing_basic_mean = mean;
    measurements.timing_basic_variance = variance;
    measurements.timing_basic_cv = calculate_cv(std_dev, mean);
    measurements.timing_basic_skewness = calculate_skewness(timings, ITERATIONS, mean, std_dev);
    measurements.timing_basic_kurtosis = calculate_kurtosis(timings, ITERATIONS, mean, std_dev);
    
    free(timings);
}

// Thread workload with synchronization
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

// Measure thread scheduling
void measure_thread_scheduling() {
    printf("2. Thread scheduling measurements...\n");
    
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
    
    double mean = calculate_mean(timings, num_tests);
    double variance = calculate_variance(timings, num_tests, mean);
    double std_dev = calculate_std_dev(variance);
    
    measurements.scheduling_thread_mean = mean;
    measurements.scheduling_thread_variance = variance;
    measurements.scheduling_thread_cv = calculate_cv(std_dev, mean);
    measurements.scheduling_thread_skewness = calculate_skewness(timings, num_tests, mean, std_dev);
    measurements.scheduling_thread_kurtosis = calculate_kurtosis(timings, num_tests, mean, std_dev);
    
    // Calculate Physical Machine Index (PMI)
    if (variance > 0) {
        double numerator = measurements.scheduling_thread_kurtosis * measurements.scheduling_thread_skewness;
        if (numerator > 0) {
            measurements.physical_machine_index = log10(numerator / variance);
        } else {
            measurements.physical_machine_index = -10.0;  // Very low value indicates VM
        }
    }
    
    free(timings);
}

// Process workload for multiprocessing test
void process_workload() {
    volatile long result = 0;
    for (int i = 0; i < 10000; i++) {
        result += i * i;
    }
}

// Measure multiprocessing scheduling
void measure_multiprocessing_scheduling() {
    printf("3. Multiprocessing scheduling measurements...\n");
    
    int num_tests = ITERATIONS / 20;
    double *timings = malloc(num_tests * sizeof(double));
    if (!timings) {
        fprintf(stderr, "Error: Failed to allocate memory for process timings\n");
        return;
    }
    
    for (int test = 0; test < num_tests; test++) {
        long long start = get_time_ns();
        
        for (int i = 0; i < THREAD_COUNT; i++) {
            pid_t pid = fork();
            if (pid == 0) {
                // Child process
                process_workload();
                exit(0);
            } else if (pid < 0) {
                fprintf(stderr, "Error: Failed to fork process\n");
            }
        }
        
        // Wait for all child processes
        for (int i = 0; i < THREAD_COUNT; i++) {
            wait(NULL);
        }
        
        long long end = get_time_ns();
        timings[test] = (double)(end - start);
    }
    
    double mean = calculate_mean(timings, num_tests);
    double variance = calculate_variance(timings, num_tests, mean);
    double std_dev = calculate_std_dev(variance);
    
    measurements.scheduling_multiproc_mean = mean;
    measurements.scheduling_multiproc_variance = variance;
    measurements.scheduling_multiproc_cv = calculate_cv(std_dev, mean);
    
    free(timings);
}

// Measure consecutive timing
void measure_consecutive_timing() {
    printf("4. Consecutive timing measurements...\n");
    
    int num_tests = ITERATIONS / 2;
    double *timings = malloc(num_tests * sizeof(double));
    if (!timings) {
        fprintf(stderr, "Error: Failed to allocate memory for consecutive timings\n");
        return;
    }
    
    for (int test = 0; test < num_tests; test++) {
        double times[10];
        
        for (int i = 0; i < 10; i++) {
            long long start = get_time_ns();
            // Simple operation
            volatile long sum = 0;
            for (int j = 0; j < 1000; j++) {
                sum += j;
            }
            long long end = get_time_ns();
            times[i] = (double)(end - start);
        }
        
        timings[test] = calculate_mean(times, 10);
    }
    
    double mean = calculate_mean(timings, num_tests);
    double variance = calculate_variance(timings, num_tests, mean);
    double std_dev = calculate_std_dev(variance);
    
    measurements.timing_consecutive_mean = mean;
    measurements.timing_consecutive_variance = variance;
    measurements.timing_consecutive_cv = calculate_cv(std_dev, mean);
    
    free(timings);
}

// Measure cache behavior
void measure_cache_behavior() {
    printf("5. Cache behavior measurements...\n");
    
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

// Measure memory entropy
void measure_memory_entropy() {
    printf("6. Memory entropy measurements...\n");
    
    void *addresses[100];
    double diffs[99];
    
    // Allocate multiple buffers and record addresses
    for (int i = 0; i < 100; i++) {
        addresses[i] = malloc(4096);
        if (!addresses[i]) {
            fprintf(stderr, "Error: Failed to allocate memory for entropy test\n");
            // Clean up
            for (int j = 0; j < i; j++) {
                free(addresses[j]);
            }
            measurements.memory_address_entropy = 0.0;
            return;
        }
    }
    
    // Calculate differences between consecutive allocations
    for (int i = 0; i < 99; i++) {
        diffs[i] = (double)((char*)addresses[i+1] - (char*)addresses[i]);
    }
    
    measurements.memory_address_entropy = calculate_entropy(diffs, 99);
    
    // Clean up
    for (int i = 0; i < 100; i++) {
        free(addresses[i]);
    }
}

// Calculate overall metrics
void calculate_overall_metrics() {
    printf("7. Calculating overall metrics...\n");
    
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

// Analyze VM indicators
void analyze_vm_indicators() {
    printf("\nVM Indicators Analysis:\n");
    printf("==================================================\n");
    
    int vm_indicators = 0;
    int total_indicators = 0;
    
    // High scheduling variance indicates VM
    if (measurements.scheduling_thread_cv > 0.15) {
        printf("[VM] High scheduling variance: %.4f > 0.15\n", measurements.scheduling_thread_cv);
        vm_indicators++;
    } else {
        printf("[OK] Normal scheduling variance: %.4f <= 0.15\n", measurements.scheduling_thread_cv);
    }
    total_indicators++;
    
    // Low PMI indicates VM
    if (measurements.physical_machine_index < 1.0) {
        printf("[VM] Low Physical Machine Index: %.4f < 1.0\n", measurements.physical_machine_index);
        vm_indicators++;
    } else {
        printf("[OK] Normal Physical Machine Index: %.4f >= 1.0\n", measurements.physical_machine_index);
    }
    total_indicators++;
    
    // High cache miss ratio indicates VM
    if (measurements.cache_miss_ratio > 0.5) {
        printf("[VM] High cache miss ratio: %.4f > 0.5\n", measurements.cache_miss_ratio);
        vm_indicators++;
    } else {
        printf("[OK] Normal cache miss ratio: %.4f <= 0.5\n", measurements.cache_miss_ratio);
    }
    total_indicators++;
    
    // Low memory entropy indicates VM
    if (measurements.memory_address_entropy < 2.0) {
        printf("[VM] Low memory entropy: %.4f < 2.0\n", measurements.memory_address_entropy);
        vm_indicators++;
    } else {
        printf("[OK] Normal memory entropy: %.4f >= 2.0\n", measurements.memory_address_entropy);
    }
    total_indicators++;
    
    double vm_likelihood = (double)vm_indicators / total_indicators;
    printf("\nVM Likelihood Score: %.2f (%d/%d indicators)\n", vm_likelihood, vm_indicators, total_indicators);
    
    if (vm_likelihood > 0.5) {
        printf("Result: LIKELY RUNNING IN VIRTUAL MACHINE\n");
    } else {
        printf("Result: LIKELY RUNNING ON PHYSICAL MACHINE\n");
    }
}

// Print all measurements
void print_measurements() {
    printf("\n==================================================\n");
    printf("VMTEST MEASUREMENT RESULTS\n");
    printf("==================================================\n");
    
    printf("\nTiming Basic Measurements:\n");
    printf("  Mean: %.2f ns\n", measurements.timing_basic_mean);
    printf("  Variance: %.2f\n", measurements.timing_basic_variance);
    printf("  CV: %.4f\n", measurements.timing_basic_cv);
    printf("  Skewness: %.4f\n", measurements.timing_basic_skewness);
    printf("  Kurtosis: %.4f\n", measurements.timing_basic_kurtosis);
    
    printf("\nThread Scheduling Measurements:\n");
    printf("  Mean: %.2f ns\n", measurements.scheduling_thread_mean);
    printf("  Variance: %.2f\n", measurements.scheduling_thread_variance);
    printf("  CV: %.4f\n", measurements.scheduling_thread_cv);
    printf("  Skewness: %.4f\n", measurements.scheduling_thread_skewness);
    printf("  Kurtosis: %.4f\n", measurements.scheduling_thread_kurtosis);
    printf("  Physical Machine Index: %.4f\n", measurements.physical_machine_index);
    
    printf("\nMultiprocessing Scheduling Measurements:\n");
    printf("  Mean: %.2f ns\n", measurements.scheduling_multiproc_mean);
    printf("  Variance: %.2f\n", measurements.scheduling_multiproc_variance);
    printf("  CV: %.4f\n", measurements.scheduling_multiproc_cv);
    
    printf("\nConsecutive Timing Measurements:\n");
    printf("  Mean: %.2f ns\n", measurements.timing_consecutive_mean);
    printf("  Variance: %.2f\n", measurements.timing_consecutive_variance);
    printf("  CV: %.4f\n", measurements.timing_consecutive_cv);
    
    printf("\nCache Behavior Measurements:\n");
    printf("  Access Ratio: %.4f\n", measurements.cache_access_ratio);
    printf("  Miss Ratio: %.4f\n", measurements.cache_miss_ratio);
    
    printf("\nMemory Measurements:\n");
    printf("  Address Entropy: %.4f\n", measurements.memory_address_entropy);
    
    printf("\nOverall Metrics:\n");
    printf("  Overall Timing CV: %.4f\n", measurements.overall_timing_cv);
    printf("  Overall Scheduling CV: %.4f\n", measurements.overall_scheduling_cv);
}

// Save results to JSON file
void save_results_json(const char *filename) {
    FILE *fp = fopen(filename, "w");
    if (!fp) {
        fprintf(stderr, "Error: Could not open file %s for writing\n", filename);
        return;
    }
    
    fprintf(fp, "{\n");
    
    // System information
    fprintf(fp, "  \"system_info\": {\n");
    fprintf(fp, "    \"platform\": \"%s\",\n", system_info.platform);
    fprintf(fp, "    \"hostname\": \"%s\",\n", system_info.hostname);
    fprintf(fp, "    \"machine\": \"%s\",\n", system_info.machine);
    fprintf(fp, "    \"cpu_count\": %d,\n", system_info.cpu_count);
    fprintf(fp, "    \"total_memory\": %ld,\n", system_info.total_memory);
    fprintf(fp, "    \"cpu_freq_mhz\": %ld,\n", system_info.cpu_freq_mhz);
    fprintf(fp, "    \"timestamp\": %ld\n", time(NULL));
    fprintf(fp, "  },\n");
    
    // Measurements
    fprintf(fp, "  \"measurements\": {\n");
    fprintf(fp, "    \"TIMING_BASIC_MEAN\": %.6f,\n", measurements.timing_basic_mean);
    fprintf(fp, "    \"TIMING_BASIC_VARIANCE\": %.6f,\n", measurements.timing_basic_variance);
    fprintf(fp, "    \"TIMING_BASIC_CV\": %.6f,\n", measurements.timing_basic_cv);
    fprintf(fp, "    \"TIMING_BASIC_SKEWNESS\": %.6f,\n", measurements.timing_basic_skewness);
    fprintf(fp, "    \"TIMING_BASIC_KURTOSIS\": %.6f,\n", measurements.timing_basic_kurtosis);
    fprintf(fp, "    \"SCHEDULING_THREAD_MEAN\": %.6f,\n", measurements.scheduling_thread_mean);
    fprintf(fp, "    \"SCHEDULING_THREAD_VARIANCE\": %.6f,\n", measurements.scheduling_thread_variance);
    fprintf(fp, "    \"SCHEDULING_THREAD_CV\": %.6f,\n", measurements.scheduling_thread_cv);
    fprintf(fp, "    \"SCHEDULING_THREAD_SKEWNESS\": %.6f,\n", measurements.scheduling_thread_skewness);
    fprintf(fp, "    \"SCHEDULING_THREAD_KURTOSIS\": %.6f,\n", measurements.scheduling_thread_kurtosis);
    fprintf(fp, "    \"PHYSICAL_MACHINE_INDEX\": %.6f,\n", measurements.physical_machine_index);
    fprintf(fp, "    \"SCHEDULING_MULTIPROC_MEAN\": %.6f,\n", measurements.scheduling_multiproc_mean);
    fprintf(fp, "    \"SCHEDULING_MULTIPROC_VARIANCE\": %.6f,\n", measurements.scheduling_multiproc_variance);
    fprintf(fp, "    \"SCHEDULING_MULTIPROC_CV\": %.6f,\n", measurements.scheduling_multiproc_cv);
    fprintf(fp, "    \"TIMING_CONSECUTIVE_MEAN\": %.6f,\n", measurements.timing_consecutive_mean);
    fprintf(fp, "    \"TIMING_CONSECUTIVE_VARIANCE\": %.6f,\n", measurements.timing_consecutive_variance);
    fprintf(fp, "    \"TIMING_CONSECUTIVE_CV\": %.6f,\n", measurements.timing_consecutive_cv);
    fprintf(fp, "    \"CACHE_ACCESS_RATIO\": %.6f,\n", measurements.cache_access_ratio);
    fprintf(fp, "    \"CACHE_MISS_RATIO\": %.6f,\n", measurements.cache_miss_ratio);
    fprintf(fp, "    \"MEMORY_ADDRESS_ENTROPY\": %.6f,\n", measurements.memory_address_entropy);
    fprintf(fp, "    \"OVERALL_TIMING_CV\": %.6f,\n", measurements.overall_timing_cv);
    fprintf(fp, "    \"OVERALL_SCHEDULING_CV\": %.6f\n", measurements.overall_scheduling_cv);
    fprintf(fp, "  }\n");
    fprintf(fp, "}\n");
    
    fclose(fp);
    printf("\nResults saved to: %s\n", filename);
}

int main(int argc, char *argv[]) {
    printf("VMTEST - Virtual Machine Detection Tool\n");
    printf("======================================\n\n");
    
    // Gather system information first
    gather_system_info();
    print_system_info();
    
    printf("\nStarting VMTEST measurements...\n");
    
    // Initialize random seed
    srand(time(NULL));
    
    // Run all measurements
    measure_timing_basic();
    measure_thread_scheduling();
    measure_multiprocessing_scheduling();
    measure_consecutive_timing();
    measure_cache_behavior();
    measure_memory_entropy();
    calculate_overall_metrics();
    
    printf("\nMeasurements complete!\n");
    
    // Print results
    print_measurements();
    
    // Analyze VM indicators
    analyze_vm_indicators();
    
    // Save to JSON file
    char filename[256];
    snprintf(filename, sizeof(filename), "vmtest_results_%ld.json", time(NULL));
    save_results_json(filename);
    
    return 0;
}
