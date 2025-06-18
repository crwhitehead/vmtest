#!/usr/bin/env python3
"""
VM Detection Data Collection - Python Implementation
Leverages multiprocessing, memory analysis, and system introspection for VM detection
"""

import time
import statistics
import multiprocessing as mp
import threading
import ctypes
import platform
import os
import sys
import gc
import math
import numpy as np
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import psutil
import mmap
import tempfile
from threading import Barrier
import tracemalloc

# ============================================================================
# CONFIGURATION CONSTANTS - Adjust these to control test duration/accuracy
# ============================================================================

# Timing Analysis
TIMING_ITERATIONS = 10000
TIMING_BENCHMARK_OPS = 1000

# Thread/Process Scheduling Tests
SCHEDULING_ITERATIONS = 5000
PROCESS_COUNT = mp.cpu_count()
THREAD_COUNT = 8
WORK_CYCLES = 10000

# Memory Analysis Tests
MEMORY_ITERATIONS = 2000
MEMORY_ALLOCATION_SIZE = 4096
MEMORY_PATTERN_SIZE = 1000000  # 1MB

# Cache Simulation Tests
CACHE_ITERATIONS = 5000
CACHE_MEMORY_SIZE = 8 * 1024 * 1024  # 8MB

# I/O and System Tests
IO_ITERATIONS = 1000
SYSTEM_ITERATIONS = 500

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_high_precision_time():
    """Get highest precision time available"""
    return time.perf_counter_ns()

def calculate_statistics(values):
    """Calculate comprehensive statistics for a list of values"""
    if not values:
        return {}
    
    mean_val = statistics.mean(values)
    variance = statistics.variance(values) if len(values) > 1 else 0
    std_dev = math.sqrt(variance)
    
    stats = {
        'mean': mean_val,
        'variance': variance,
        'std_dev': std_dev,
        'coefficient_variation': std_dev / mean_val if mean_val != 0 else 0,
        'min': min(values),
        'max': max(values),
        'range': max(values) - min(values),
        'median': statistics.median(values)
    }
    
    # Calculate skewness and kurtosis
    if len(values) > 2 and std_dev > 0:
        n = len(values)
        skewness = sum(((x - mean_val) / std_dev) ** 3 for x in values) / n
        kurtosis = sum(((x - mean_val) / std_dev) ** 4 for x in values) / n - 3
        stats['skewness'] = skewness
        stats['kurtosis'] = kurtosis
    else:
        stats['skewness'] = 0
        stats['kurtosis'] = 0
    
    return stats

def benchmark_operation(operation, iterations=TIMING_BENCHMARK_OPS):
    """Benchmark a simple operation for normalization"""
    start = get_high_precision_time()
    for _ in range(iterations):
        operation()
    end = get_high_precision_time()
    return end - start

# ============================================================================
# 1. TIMING ANALYSIS (RDTSC equivalent in Python)
# ============================================================================

class TimingAnalyzer:
    def __init__(self):
        self.results = {}
    
    def test_basic_timing(self):
        """Test basic timing precision and overhead"""
        print("=== Python Timing Analysis ===")
        
        # Benchmark: Simple operation timing
        def simple_op():
            x = 1 + 1
        
        benchmark_time = benchmark_operation(simple_op)
        
        # Test 1: Basic timing overhead
        basic_timings = []
        for _ in range(TIMING_ITERATIONS):
            start = get_high_precision_time()
            # Minimal operation
            x = 1
            end = get_high_precision_time()
            basic_timings.append(end - start)
        
        # Test 2: Function call timing
        def dummy_function():
            pass
        
        function_timings = []
        for _ in range(TIMING_ITERATIONS):
            start = get_high_precision_time()
            dummy_function()
            end = get_high_precision_time()
            function_timings.append(end - start)
        
        # Test 3: System call timing (equivalent to potential VM exits)
        syscall_timings = []
        for _ in range(TIMING_ITERATIONS):
            start = get_high_precision_time()
            os.getpid()  # System call
            end = get_high_precision_time()
            syscall_timings.append(end - start)
        
        # Test 4: Time.sleep precision (scheduler interaction)
        sleep_timings = []
        sleep_duration = 0.001  # 1ms
        for _ in range(min(TIMING_ITERATIONS // 10, 1000)):  # Fewer iterations for sleep
            start = get_high_precision_time()
            time.sleep(sleep_duration)
            end = get_high_precision_time()
            actual_sleep = end - start
            sleep_timings.append(actual_sleep)
        
        # Calculate statistics
        basic_stats = calculate_statistics(basic_timings)
        function_stats = calculate_statistics(function_timings)
        syscall_stats = calculate_statistics(syscall_timings)
        sleep_stats = calculate_statistics(sleep_timings)
        
        # Output results
        print(f"TIMING_BENCHMARK_NS: {benchmark_time}")
        print(f"TIMING_BASIC_MEAN: {basic_stats['mean']:.2f}")
        print(f"TIMING_BASIC_VARIANCE: {basic_stats['variance']:.2f}")
        print(f"TIMING_BASIC_CV: {basic_stats['coefficient_variation']:.6f}")
        print(f"TIMING_BASIC_SKEWNESS: {basic_stats['skewness']:.6f}")
        print(f"TIMING_BASIC_KURTOSIS: {basic_stats['kurtosis']:.6f}")
        
        print(f"TIMING_FUNCTION_MEAN: {function_stats['mean']:.2f}")
        print(f"TIMING_FUNCTION_CV: {function_stats['coefficient_variation']:.6f}")
        
        print(f"TIMING_SYSCALL_MEAN: {syscall_stats['mean']:.2f}")
        print(f"TIMING_SYSCALL_VARIANCE: {syscall_stats['variance']:.2f}")
        print(f"TIMING_SYSCALL_CV: {syscall_stats['coefficient_variation']:.6f}")
        
        print(f"TIMING_SLEEP_MEAN: {sleep_stats['mean']:.2f}")
        print(f"TIMING_SLEEP_VARIANCE: {sleep_stats['variance']:.2f}")
        print(f"TIMING_SLEEP_ACCURACY: {sleep_stats['mean'] / (sleep_duration * 1e9):.6f}")
        
        print(f"TIMING_SYSCALL_RATIO: {syscall_stats['mean'] / basic_stats['mean']:.6f}")
        print()
        
        self.results.update({
            'basic_cv': basic_stats['coefficient_variation'],
            'syscall_ratio': syscall_stats['mean'] / basic_stats['mean'],
            'sleep_accuracy': sleep_stats['mean'] / (sleep_duration * 1e9)
        })

# ============================================================================
# 2. MULTIPROCESSING SCHEDULING ANALYSIS
# ============================================================================

def cpu_bound_worker(process_id, iterations, work_cycles):
    """CPU-bound worker function for multiprocessing"""
    execution_times = []
    
    for i in range(iterations):
        start = get_high_precision_time()
        
        # CPU-intensive work
        result = 0
        for j in range(work_cycles):
            result += j * process_id
        
        end = get_high_precision_time()
        execution_times.append(end - start)
    
    return execution_times

def thread_worker(thread_id, barrier, results_list, iterations, work_cycles):
    """Thread worker for GIL analysis"""
    thread_times = []
    
    for i in range(iterations):
        # Wait for all threads
        barrier.wait()
        
        start = get_high_precision_time()
        
        # Python computation (affected by GIL)
        result = sum(j * thread_id for j in range(work_cycles))
        
        end = get_high_precision_time()
        thread_times.append(end - start)
    
    results_list.extend(thread_times)

class SchedulingAnalyzer:
    def __init__(self):
        self.results = {}
    
    def test_multiprocessing_scheduling(self):
        """Test true parallel processing scheduling"""
        print("=== Multiprocessing Scheduling Analysis ===")
        
        # Benchmark single-process execution
        benchmark_time = benchmark_operation(
            lambda: sum(range(WORK_CYCLES)), 
            iterations=10
        )
        
        # Test multiprocessing scheduling
        with ProcessPoolExecutor(max_workers=PROCESS_COUNT) as executor:
            futures = []
            
            # Submit work to all processes
            iterations_per_process = SCHEDULING_ITERATIONS // PROCESS_COUNT
            for process_id in range(PROCESS_COUNT):
                future = executor.submit(
                    cpu_bound_worker, 
                    process_id, 
                    iterations_per_process, 
                    WORK_CYCLES
                )
                futures.append(future)
            
            # Collect results
            all_times = []
            for future in futures:
                process_times = future.result()
                all_times.extend(process_times)
        
        # Calculate statistics
        mp_stats = calculate_statistics(all_times)
        
        print(f"MULTIPROC_BENCHMARK_NS: {benchmark_time}")
        print(f"MULTIPROC_MEAN: {mp_stats['mean']:.2f}")
        print(f"MULTIPROC_VARIANCE: {mp_stats['variance']:.2f}")
        print(f"MULTIPROC_CV: {mp_stats['coefficient_variation']:.6f}")
        print(f"MULTIPROC_SKEWNESS: {mp_stats['skewness']:.6f}")
        print(f"MULTIPROC_KURTOSIS: {mp_stats['kurtosis']:.6f}")
        print(f"MULTIPROC_PROCESS_COUNT: {PROCESS_COUNT}")
        print(f"MULTIPROC_TOTAL_SAMPLES: {len(all_times)}")
        print(f"MULTIPROC_OVERHEAD_RATIO: {mp_stats['mean'] / (benchmark_time / 10):.6f}")
        print()
        
        self.results['multiproc_cv'] = mp_stats['coefficient_variation']
    
    def test_gil_threading_analysis(self):
        """Test GIL behavior and thread scheduling"""
        print("=== GIL Threading Analysis ===")
        
        # Test threading with GIL contention
        barrier = Barrier(THREAD_COUNT)
        thread_results = []
        threads = []
        
        # Create and start threads
        iterations_per_thread = SCHEDULING_ITERATIONS // THREAD_COUNT
        for thread_id in range(THREAD_COUNT):
            thread = threading.Thread(
                target=thread_worker,
                args=(thread_id, barrier, thread_results, iterations_per_thread, WORK_CYCLES)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Calculate statistics
        gil_stats = calculate_statistics(thread_results)
        
        print(f"GIL_MEAN: {gil_stats['mean']:.2f}")
        print(f"GIL_VARIANCE: {gil_stats['variance']:.2f}")
        print(f"GIL_CV: {gil_stats['coefficient_variation']:.6f}")
        print(f"GIL_SKEWNESS: {gil_stats['skewness']:.6f}")
        print(f"GIL_KURTOSIS: {gil_stats['kurtosis']:.6f}")
        print(f"GIL_THREAD_COUNT: {THREAD_COUNT}")
        print(f"GIL_TOTAL_SAMPLES: {len(thread_results)}")
        print()
        
        self.results['gil_cv'] = gil_stats['coefficient_variation']

# ============================================================================
# 3. MEMORY BEHAVIOR ANALYSIS
# ============================================================================

class MemoryAnalyzer:
    def __init__(self):
        self.results = {}
    
    def test_garbage_collection_patterns(self):
        """Analyze garbage collection timing patterns"""
        print("=== Garbage Collection Analysis ===")
        
        # Enable detailed memory tracking
        tracemalloc.start()
        
        # Benchmark: Simple allocation
        def simple_alloc():
            return [0] * 1000
        
        benchmark_time = benchmark_operation(simple_alloc, iterations=100)
        
        # Test 1: Allocation timing
        allocation_times = []
        allocated_objects = []
        
        for _ in range(MEMORY_ITERATIONS):
            start = get_high_precision_time()
            obj = [i for i in range(MEMORY_PATTERN_SIZE // 1000)]  # Create list
            end = get_high_precision_time()
            
            allocation_times.append(end - start)
            allocated_objects.append(obj)
        
        # Test 2: Garbage collection timing
        gc_times = []
        for _ in range(min(MEMORY_ITERATIONS // 10, 100)):
            start = get_high_precision_time()
            collected = gc.collect()
            end = get_high_precision_time()
            gc_times.append(end - start)
        
        # Test 3: Memory deallocation patterns
        dealloc_times = []
        for obj in allocated_objects[:len(allocated_objects)//2]:
            start = get_high_precision_time()
            del obj
            end = get_high_precision_time()
            dealloc_times.append(end - start)
        
        # Clean up remaining objects
        allocated_objects.clear()
        
        # Get memory statistics
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Calculate statistics
        alloc_stats = calculate_statistics(allocation_times)
        gc_stats = calculate_statistics(gc_times) if gc_times else {'mean': 0, 'variance': 0, 'coefficient_variation': 0}
        dealloc_stats = calculate_statistics(dealloc_times)
        
        print(f"MEMORY_BENCHMARK_NS: {benchmark_time}")
        print(f"MEMORY_ALLOC_MEAN: {alloc_stats['mean']:.2f}")
        print(f"MEMORY_ALLOC_VARIANCE: {alloc_stats['variance']:.2f}")
        print(f"MEMORY_ALLOC_CV: {alloc_stats['coefficient_variation']:.6f}")
        print(f"MEMORY_GC_MEAN: {gc_stats['mean']:.2f}")
        print(f"MEMORY_GC_VARIANCE: {gc_stats['variance']:.2f}")
        print(f"MEMORY_DEALLOC_MEAN: {dealloc_stats['mean']:.2f}")
        print(f"MEMORY_PEAK_USAGE: {peak}")
        print(f"MEMORY_CURRENT_USAGE: {current}")
        print()
        
        self.results.update({
            'alloc_cv': alloc_stats['coefficient_variation'],
            'gc_mean': gc_stats['mean'],
            'peak_memory': peak
        })
    
    def test_memory_mapping_patterns(self):
        """Test memory mapping and virtual memory behavior"""
        print("=== Memory Mapping Analysis ===")
        
        mmap_times = []
        munmap_times = []
        
        # Create temporary files for memory mapping
        temp_files = []
        
        for i in range(min(MEMORY_ITERATIONS // 10, 100)):
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.write(b'0' * MEMORY_ALLOCATION_SIZE)
            temp_file.flush()
            temp_files.append(temp_file)
            
            # Test memory mapping
            start = get_high_precision_time()
            with open(temp_file.name, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), MEMORY_ALLOCATION_SIZE)
                end = get_high_precision_time()
                mmap_times.append(end - start)
                
                # Test unmapping
                start = get_high_precision_time()
                mm.close()
                end = get_high_precision_time()
                munmap_times.append(end - start)
        
        # Cleanup
        for temp_file in temp_files:
            temp_file.close()
            os.unlink(temp_file.name)
        
        # Calculate statistics
        mmap_stats = calculate_statistics(mmap_times)
        munmap_stats = calculate_statistics(munmap_times)
        
        print(f"MMAP_MEAN: {mmap_stats['mean']:.2f}")
        print(f"MMAP_VARIANCE: {mmap_stats['variance']:.2f}")
        print(f"MMAP_CV: {mmap_stats['coefficient_variation']:.6f}")
        print(f"MUNMAP_MEAN: {munmap_stats['mean']:.2f}")
        print(f"MUNMAP_CV: {munmap_stats['coefficient_variation']:.6f}")
        print()
        
        self.results.update({
            'mmap_cv': mmap_stats['coefficient_variation'],
            'munmap_cv': munmap_stats['coefficient_variation']
        })

# ============================================================================
# 4. CACHE SIMULATION AND MEMORY ACCESS PATTERNS
# ============================================================================

class CacheAnalyzer:
    def __init__(self):
        self.results = {}
    
    def test_memory_access_patterns(self):
        """Simulate cache behavior through memory access patterns"""
        print("=== Memory Access Pattern Analysis ===")
        
        # Create large array for cache simulation
        cache_array = np.zeros(CACHE_MEMORY_SIZE // 8, dtype=np.int64)
        
        # Benchmark: Sequential access
        def sequential_access():
            for i in range(0, len(cache_array), 1000):
                cache_array[i] += 1
        
        benchmark_time = benchmark_operation(sequential_access, iterations=10)
        
        # Test 1: Sequential vs Random access timing
        sequential_times = []
        random_times = []
        
        for _ in range(CACHE_ITERATIONS):
            # Sequential access
            start = get_high_precision_time()
            for i in range(0, min(len(cache_array), 10000), 8):  # Cache line simulation
                cache_array[i] += 1
            end = get_high_precision_time()
            sequential_times.append(end - start)
            
            # Random access
            indices = np.random.randint(0, len(cache_array), 1250)  # Same number of accesses
            start = get_high_precision_time()
            for idx in indices:
                cache_array[idx] += 1
            end = get_high_precision_time()
            random_times.append(end - start)
        
        # Test 2: Stride pattern analysis (different cache behaviors)
        stride_results = {}
        strides = [1, 8, 64, 512, 4096]  # Different memory access patterns
        
        for stride in strides:
            stride_times = []
            for _ in range(min(CACHE_ITERATIONS // 5, 1000)):
                start = get_high_precision_time()
                for i in range(0, min(len(cache_array), 10000), stride):
                    cache_array[i] += 1
                end = get_high_precision_time()
                stride_times.append(end - start)
            stride_results[stride] = calculate_statistics(stride_times)
        
        # Calculate statistics
        seq_stats = calculate_statistics(sequential_times)
        rand_stats = calculate_statistics(random_times)
        
        print(f"CACHE_BENCHMARK_NS: {benchmark_time}")
        print(f"CACHE_SEQUENTIAL_MEAN: {seq_stats['mean']:.2f}")
        print(f"CACHE_SEQUENTIAL_CV: {seq_stats['coefficient_variation']:.6f}")
        print(f"CACHE_RANDOM_MEAN: {rand_stats['mean']:.2f}")
        print(f"CACHE_RANDOM_CV: {rand_stats['coefficient_variation']:.6f}")
        print(f"CACHE_ACCESS_RATIO: {rand_stats['mean'] / seq_stats['mean']:.6f}")
        
        # Output stride analysis
        for stride, stats in stride_results.items():
            print(f"CACHE_STRIDE_{stride}_MEAN: {stats['mean']:.2f}")
            print(f"CACHE_STRIDE_{stride}_CV: {stats['coefficient_variation']:.6f}")
        
        print()
        
        self.results.update({
            'cache_ratio': rand_stats['mean'] / seq_stats['mean'],
            'sequential_cv': seq_stats['coefficient_variation'],
            'random_cv': rand_stats['coefficient_variation']
        })

# ============================================================================
# 5. SYSTEM INTROSPECTION AND PLATFORM ANALYSIS
# ============================================================================

class SystemAnalyzer:
    def __init__(self):
        self.results = {}
    
    def analyze_system_characteristics(self):
        """Analyze system-level characteristics that may indicate virtualization"""
        print("=== System Characteristics Analysis ===")
        
        # CPU information
        cpu_count = mp.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # Memory information
        memory = psutil.virtual_memory()
        
        # Platform information
        platform_info = {
            'system': platform.system(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_implementation': platform.python_implementation(),
            'python_version': platform.python_version()
        }
        
        # Performance characteristics
        perf_tests = []
        for _ in range(SYSTEM_ITERATIONS):
            start = get_high_precision_time()
            # Mixed operations that may behave differently in VMs
            _ = os.listdir('.')
            _ = psutil.cpu_percent()
            end = get_high_precision_time()
            perf_tests.append(end - start)
        
        perf_stats = calculate_statistics(perf_tests)
        
        print(f"SYSTEM_CPU_COUNT: {cpu_count}")
        print(f"SYSTEM_CPU_FREQ_CURRENT: {cpu_freq.current if cpu_freq else 0}")
        print(f"SYSTEM_MEMORY_TOTAL: {memory.total}")
        print(f"SYSTEM_MEMORY_AVAILABLE: {memory.available}")
        print(f"SYSTEM_PLATFORM: {platform_info['system']}")
        print(f"SYSTEM_MACHINE: {platform_info['machine']}")
        print(f"SYSTEM_PERF_MEAN: {perf_stats['mean']:.2f}")
        print(f"SYSTEM_PERF_CV: {perf_stats['coefficient_variation']:.6f}")
        print()
        
        self.results.update({
            'cpu_count': cpu_count,
            'memory_total': memory.total,
            'perf_cv': perf_stats['coefficient_variation']
        })

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("=== VM Detection Data Collection - Python Implementation ===")
    print("Test Configuration:")
    print(f"TIMING_ITERATIONS: {TIMING_ITERATIONS}")
    print(f"SCHEDULING_ITERATIONS: {SCHEDULING_ITERATIONS}")
    print(f"PROCESS_COUNT: {PROCESS_COUNT}")
    print(f"THREAD_COUNT: {THREAD_COUNT}")
    print(f"MEMORY_ITERATIONS: {MEMORY_ITERATIONS}")
    print(f"CACHE_ITERATIONS: {CACHE_ITERATIONS}")
    print()
    
    # Initialize analyzers
    timing_analyzer = TimingAnalyzer()
    scheduling_analyzer = SchedulingAnalyzer()
    memory_analyzer = MemoryAnalyzer()
    cache_analyzer = CacheAnalyzer()
    system_analyzer = SystemAnalyzer()
    
    # Run all tests
    timing_analyzer.test_basic_timing()
    scheduling_analyzer.test_multiprocessing_scheduling()
    scheduling_analyzer.test_gil_threading_analysis()
    memory_analyzer.test_garbage_collection_patterns()
    memory_analyzer.test_memory_mapping_patterns()
    cache_analyzer.test_memory_access_patterns()
    system_analyzer.analyze_system_characteristics()
    
    # Combine all results
    all_results = {}
    all_results.update(timing_analyzer.results)
    all_results.update(scheduling_analyzer.results)
    all_results.update(memory_analyzer.results)
    all_results.update(cache_analyzer.results)
    all_results.update(system_analyzer.results)
    
    # Output summary for ML processing
    print("=== SUMMARY FOR ML CLASSIFICATION ===")
    print(f"OVERALL_TIMING_CV: {all_results.get('basic_cv', 0):.6f}")
    print(f"OVERALL_MULTIPROC_CV: {all_results.get('multiproc_cv', 0):.6f}")
    print(f"OVERALL_GIL_CV: {all_results.get('gil_cv', 0):.6f}")
    print(f"OVERALL_MEMORY_CV: {all_results.get('alloc_cv', 0):.6f}")
    print(f"OVERALL_CACHE_RATIO: {all_results.get('cache_ratio', 0):.6f}")
    print(f"OVERALL_SYSCALL_RATIO: {all_results.get('syscall_ratio', 0):.6f}")
    print(f"OVERALL_SYSTEM_PERF_CV: {all_results.get('perf_cv', 0):.6f}")
    
    # Calculate composite detection confidence
    cv_metrics = [
        all_results.get('basic_cv', 0),
        all_results.get('multiproc_cv', 0),
        all_results.get('gil_cv', 0),
        all_results.get('alloc_cv', 0)
    ]
    
    avg_cv = statistics.mean([cv for cv in cv_metrics if cv > 0])
    print(f"DETECTION_CONFIDENCE: {avg_cv:.6f}")
    
    print(f"PYTHON_IMPLEMENTATION: {platform.python_implementation()}")
    print(f"PYTHON_VERSION: {platform.python_version()}")

if __name__ == "__main__":
    main()
