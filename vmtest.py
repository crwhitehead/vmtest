#!/usr/bin/env python3
"""
VMtest - System Measurements Tool (Pure Measurements Only)
Extracts timing, scheduling, cache, and memory measurements
Based on research from Lin et al. (2021) and other academic sources

This version collects only raw measurements without VM detection logic
"""

import os
import sys
import time
import math
import json
import ctypes
import threading
import multiprocessing
import platform
from datetime import datetime

class VMTest:
    def __init__(self, iterations=1000):
        self.iterations = iterations
        self.measurements = {}
        self.system_info = {}
        
    def gather_system_info(self):
        """Gather system information"""
        try:
            self.system_info = {
                'platform': platform.platform(),
                'processor': platform.processor(),
                'python_version': platform.python_version(),
                'cpu_count': os.cpu_count(),
                'timestamp': time.time(),
                'hostname': platform.node(),
                'machine': platform.machine(),
                'system': platform.system()
            }
            
            # Try to get memory info
            try:
                import psutil
                self.system_info['memory_total'] = psutil.virtual_memory().total
                self.system_info['memory_available'] = psutil.virtual_memory().available
                self.system_info['cpu_freq'] = psutil.cpu_freq().current if psutil.cpu_freq() else 0
            except ImportError:
                # Fallback without psutil
                try:
                    # Linux-specific memory info
                    with open('/proc/meminfo', 'r') as f:
                        for line in f:
                            if line.startswith('MemTotal:'):
                                # Convert KB to bytes
                                self.system_info['memory_total'] = int(line.split()[1]) * 1024
                                break
                except:
                    pass
                    
                # Try to get CPU frequency on Linux
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if line.startswith('cpu MHz'):
                                self.system_info['cpu_freq'] = float(line.split(':')[1].strip())
                                break
                except:
                    pass
                    
        except Exception as e:
            print(f"Error gathering system info: {e}")
            
    # Statistical calculation methods
    @staticmethod
    def mean(values):
        """Calculate mean"""
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    @staticmethod
    def variance(values):
        """Calculate sample variance"""
        if len(values) <= 1:
            return 0.0
        
        mean_val = sum(values) / len(values)
        return sum((x - mean_val) ** 2 for x in values) / (len(values) - 1)
    
    @staticmethod
    def coefficient_of_variation(values):
        """Calculate coefficient of variation"""
        if not values:
            return 0.0
        
        mean_val = sum(values) / len(values)
        if mean_val == 0:
            return 0.0
        
        variance = sum((x - mean_val) ** 2 for x in values) / (len(values) - 1) if len(values) > 1 else 0
        std_dev = math.sqrt(variance)
        
        return std_dev / mean_val
    
    @staticmethod
    def skewness(values):
        """Calculate sample skewness with proper bias correction"""
        if not values or len(values) < 3:
            return 0.0
        
        n = len(values)
        mean_val = sum(values) / n
        
        # Calculate sample variance (with n-1 denominator)
        variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
        if variance <= 0:
            return 0.0
        
        std_dev = math.sqrt(variance)
        
        # Calculate third moment about the mean
        m3 = sum((x - mean_val) ** 3 for x in values) / n
        
        # Sample skewness (biased)
        skew_biased = m3 / (std_dev ** 3)
        
        # Apply bias correction for sample skewness
        if n > 2:
            adjustment = math.sqrt(n * (n - 1)) / (n - 2)
            skew_corrected = skew_biased * adjustment
        else:
            skew_corrected = skew_biased
        
        return skew_corrected
    
    @staticmethod
    def kurtosis(values):
        """Calculate sample excess kurtosis with proper bias correction"""
        if not values or len(values) < 4:
            return 0.0
        
        n = len(values)
        mean_val = sum(values) / n
        
        # Calculate sample variance (with n-1 denominator)
        variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
        if variance <= 0:
            return 0.0
        
        std_dev = math.sqrt(variance)
        
        # Calculate fourth moment about the mean
        m4 = sum((x - mean_val) ** 4 for x in values) / n
        
        # Sample kurtosis (biased)
        kurt_biased = m4 / (variance ** 2) - 3.0  # Excess kurtosis
        
        # Apply bias correction for sample kurtosis
        if n > 3:
            adjustment = ((n - 1) * ((n + 1) * kurt_biased + 6)) / ((n - 2) * (n - 3))
            kurt_corrected = adjustment
        else:
            kurt_corrected = kurt_biased
        
        return kurt_corrected
    
    def calculate_raw_pmi(self, kurtosis, skewness, variance):
        """Calculate raw Physical Machine Index (no logarithm)"""
        if variance <= 0:
            return 0.0
        return (kurtosis * skewness) / variance
    
    def shannon_entropy(self, values):
        """Calculate Shannon entropy of values"""
        if not values:
            return 0.0
        
        # Find min and max
        min_val = min(values)
        max_val = max(values)
        
        if min_val == max_val:
            return 0.0
        
        # Create histogram with 20 bins
        bins = 20
        bin_width = (max_val - min_val) / bins
        histogram = [0] * bins
        
        # Fill histogram
        for val in values:
            bin_idx = int((val - min_val) / bin_width)
            if bin_idx >= bins:
                bin_idx = bins - 1
            histogram[bin_idx] += 1
        
        # Calculate entropy
        entropy = 0.0
        total = len(values)
        for count in histogram:
            if count > 0:
                probability = count / total
                entropy -= probability * math.log2(probability)
        
        return entropy
    
    def measure_basic_timing(self):
        """Basic timing measurements"""
        print("Measuring basic timing patterns...")
        
        try:
            timings = []
            
            # CPU-bound workload
            def cpu_workload():
                result = 0
                for i in range(10000):
                    result += i * i
                return result
            
            # Collect timing samples
            for _ in range(self.iterations):
                start = time.perf_counter_ns()
                cpu_workload()
                end = time.perf_counter_ns()
                timings.append(end - start)
            
            # Calculate statistics
            self.measurements['TIMING_BASIC_MEAN'] = float(self.mean(timings))
            self.measurements['TIMING_BASIC_VARIANCE'] = float(self.variance(timings))
            self.measurements['TIMING_BASIC_CV'] = float(self.coefficient_of_variation(timings))
            self.measurements['TIMING_BASIC_SKEWNESS'] = float(self.skewness(timings))
            self.measurements['TIMING_BASIC_KURTOSIS'] = float(self.kurtosis(timings))
            
            return timings
        except Exception as e:
            print(f"Error in timing basic measurements: {e}")
            # Set default values if measurement fails
            self.measurements['TIMING_BASIC_MEAN'] = 0.0
            self.measurements['TIMING_BASIC_VARIANCE'] = 0.0
            self.measurements['TIMING_BASIC_CV'] = 0.0
            self.measurements['TIMING_BASIC_SKEWNESS'] = 0.0
            self.measurements['TIMING_BASIC_KURTOSIS'] = 0.0
            return []
    
    def measure_consecutive_timing(self):
        """Consecutive operation timing measurements"""
        print("Measuring consecutive timing patterns...")
        
        try:
            consecutive_timings = []
            
            # CPU-bound workload
            def cpu_workload():
                result = 0
                for i in range(10000):
                    result += i * i
                return result
            
            # Measure timing of consecutive operations
            for _ in range(self.iterations):
                start = time.perf_counter_ns()
                cpu_workload()
                cpu_workload()  # Two consecutive operations
                end = time.perf_counter_ns()
                consecutive_timings.append(end - start)
            
            # Calculate all statistics (including missing ones)
            self.measurements['TIMING_CONSECUTIVE_MEAN'] = float(self.mean(consecutive_timings))
            self.measurements['TIMING_CONSECUTIVE_VARIANCE'] = float(self.variance(consecutive_timings))
            self.measurements['TIMING_CONSECUTIVE_CV'] = float(self.coefficient_of_variation(consecutive_timings))
            self.measurements['TIMING_CONSECUTIVE_SKEWNESS'] = float(self.skewness(consecutive_timings))
            self.measurements['TIMING_CONSECUTIVE_KURTOSIS'] = float(self.kurtosis(consecutive_timings))
            
            return consecutive_timings
        except Exception as e:
            print(f"Error in consecutive timing measurements: {e}")
            # Set default values if measurement fails
            self.measurements['TIMING_CONSECUTIVE_MEAN'] = 0.0
            self.measurements['TIMING_CONSECUTIVE_VARIANCE'] = 0.0
            self.measurements['TIMING_CONSECUTIVE_CV'] = 0.0
            self.measurements['TIMING_CONSECUTIVE_SKEWNESS'] = 0.0
            self.measurements['TIMING_CONSECUTIVE_KURTOSIS'] = 0.0
            return []
    
    def measure_thread_scheduling(self):
        """Thread scheduling measurements based on Lin et al. research"""
        print("Measuring thread scheduling patterns...")
        
        try:
            thread_timings = []
            
            # Shared variable for thread synchronization
            counter = 0
            lock = threading.Lock()
            
            def thread_workload():
                nonlocal counter
                result = 0
                # CPU-bound work
                for i in range(5000):
                    result += i * i
                
                # Brief synchronization to simulate scheduling
                with lock:
                    counter += 1
                
                return result
            
            # Run multiple thread tests
            for _ in range(self.iterations // 10):  # Fewer iterations for thread tests
                threads = []
                start = time.perf_counter_ns()
                
                # Create and start threads
                for _ in range(4):  # 4 threads
                    t = threading.Thread(target=thread_workload)
                    threads.append(t)
                    t.start()
                
                # Wait for all threads
                for t in threads:
                    t.join()
                
                end = time.perf_counter_ns()
                thread_timings.append(end - start)
            
            # Calculate thread scheduling statistics
            self.measurements['SCHEDULING_THREAD_MEAN'] = float(self.mean(thread_timings))
            self.measurements['SCHEDULING_THREAD_VARIANCE'] = float(self.variance(thread_timings))
            self.measurements['SCHEDULING_THREAD_CV'] = float(self.coefficient_of_variation(thread_timings))
            self.measurements['SCHEDULING_THREAD_SKEWNESS'] = float(self.skewness(thread_timings))
            self.measurements['SCHEDULING_THREAD_KURTOSIS'] = float(self.kurtosis(thread_timings))
            
            # Calculate raw PMI (no logarithm)
            raw_pmi = self.calculate_raw_pmi(
                self.measurements['SCHEDULING_THREAD_KURTOSIS'],
                self.measurements['SCHEDULING_THREAD_SKEWNESS'],
                self.measurements['SCHEDULING_THREAD_VARIANCE']
            )
            self.measurements['PHYSICAL_MACHINE_INDEX'] = float(raw_pmi)
            
            return thread_timings
        except Exception as e:
            print(f"Error in thread scheduling measurements: {e}")
            # Set default values if measurement fails
            self.measurements['SCHEDULING_THREAD_MEAN'] = 0.0
            self.measurements['SCHEDULING_THREAD_VARIANCE'] = 0.0
            self.measurements['SCHEDULING_THREAD_CV'] = 0.0
            self.measurements['SCHEDULING_THREAD_SKEWNESS'] = 0.0
            self.measurements['SCHEDULING_THREAD_KURTOSIS'] = 0.0
            self.measurements['PHYSICAL_MACHINE_INDEX'] = 0.0
            return []
    
    def measure_multiprocessing_scheduling(self):
        """Multiprocessing scheduling measurements"""
        print("Measuring multiprocessing scheduling patterns...")
        
        try:
            proc_timings = []
            
            def process_workload(queue):
                result = 0
                for i in range(10000):
                    result += i * i
                queue.put(result)
            
            # Run multiprocessing tests
            for _ in range(self.iterations // 20):  # Even fewer iterations for multiprocessing
                queue = multiprocessing.Queue()
                processes = []
                
                start = time.perf_counter_ns()
                
                # Create and start processes
                for _ in range(4):
                    p = multiprocessing.Process(target=process_workload, args=(queue,))
                    processes.append(p)
                    p.start()
                
                # Wait for all processes
                for p in processes:
                    p.join()
                
                end = time.perf_counter_ns()
                proc_timings.append(end - start)
            
            # Calculate multiprocessing statistics
            self.measurements['SCHEDULING_MULTIPROC_MEAN'] = float(self.mean(proc_timings))
            self.measurements['SCHEDULING_MULTIPROC_VARIANCE'] = float(self.variance(proc_timings))
            self.measurements['SCHEDULING_MULTIPROC_CV'] = float(self.coefficient_of_variation(proc_timings))
            self.measurements['SCHEDULING_MULTIPROC_SKEWNESS'] = float(self.skewness(proc_timings))
            self.measurements['SCHEDULING_MULTIPROC_KURTOSIS'] = float(self.kurtosis(proc_timings))
            
            # Calculate raw PMI for multiprocessing (no logarithm)
            raw_pmi = self.calculate_raw_pmi(
                self.measurements['SCHEDULING_MULTIPROC_KURTOSIS'],
                self.measurements['SCHEDULING_MULTIPROC_SKEWNESS'],
                self.measurements['SCHEDULING_MULTIPROC_VARIANCE']
            )
            self.measurements['MULTIPROC_PHYSICAL_MACHINE_INDEX'] = float(raw_pmi)
            
            return proc_timings
        except Exception as e:
            print(f"Error in multiprocessing measurements: {e}")
            # Set default values if measurement fails
            self.measurements['SCHEDULING_MULTIPROC_MEAN'] = 0.0
            self.measurements['SCHEDULING_MULTIPROC_VARIANCE'] = 0.0
            self.measurements['SCHEDULING_MULTIPROC_CV'] = 0.0
            self.measurements['SCHEDULING_MULTIPROC_SKEWNESS'] = 0.0
            self.measurements['SCHEDULING_MULTIPROC_KURTOSIS'] = 0.0
            self.measurements['MULTIPROC_PHYSICAL_MACHINE_INDEX'] = 0.0
            return []
    
    def measure_cache_behavior(self):
        """Cache behavior measurements"""
        print("Measuring cache behavior patterns...")
        
        try:
            cache_timings = []
            cache_miss_indicators = []
            
            # Create large data array
            cache_size = 1024 * 1024  # 1MB
            data = [i * 0.1 for i in range(cache_size)]
            
            # Cache-friendly access (sequential)
            for _ in range(min(self.iterations, 100)):  # Limit iterations for cache tests
                start = time.perf_counter_ns()
                total = sum(data[i] for i in range(0, len(data), 1000))
                end = time.perf_counter_ns()
                cache_timings.append(end - start)
            
            # Cache-unfriendly access (random)
            import random
            indices = list(range(len(data)))
            random.shuffle(indices)
            
            for _ in range(min(self.iterations, 100)):
                start = time.perf_counter_ns()
                total = 0
                for i in range(0, len(indices), 1000):
                    total += data[indices[i]]
                end = time.perf_counter_ns()
                cache_miss_indicators.append(end - start)
            
            # Calculate cache metrics
            cache_friendly_mean = self.mean(cache_timings)
            cache_unfriendly_mean = self.mean(cache_miss_indicators)
            
            if cache_friendly_mean > 0:
                self.measurements['CACHE_ACCESS_RATIO'] = float(cache_unfriendly_mean / cache_friendly_mean)
                self.measurements['CACHE_MISS_RATIO'] = float((cache_unfriendly_mean - cache_friendly_mean) / cache_friendly_mean)
            else:
                self.measurements['CACHE_ACCESS_RATIO'] = 1.0
                self.measurements['CACHE_MISS_RATIO'] = 0.0
            
            return cache_timings, cache_miss_indicators
        except Exception as e:
            print(f"Error in cache behavior measurements: {e}")
            # Set default values if measurement fails
            self.measurements['CACHE_ACCESS_RATIO'] = 1.0
            self.measurements['CACHE_MISS_RATIO'] = 0.0
            return [], []
    
    def measure_memory_entropy(self):
        """Memory address entropy measurements"""
        print("Measuring memory entropy patterns...")
        
        try:
            addresses = []
            
            # Allocate multiple memory regions and check their addresses
            for _ in range(100):
                # Allocate a buffer
                buffer = ctypes.create_string_buffer(4096)
                addr = ctypes.addressof(buffer)
                addresses.append(addr)
            
            # Calculate entropy-related metrics
            # Use differences between consecutive allocations
            if len(addresses) > 1:
                diffs = [addresses[i+1] - addresses[i] for i in range(len(addresses)-1)]
                
                # Shannon entropy of address differences
                if diffs:
                    entropy = self.shannon_entropy(diffs)
                    self.measurements['MEMORY_ADDRESS_ENTROPY'] = float(entropy)
                else:
                    self.measurements['MEMORY_ADDRESS_ENTROPY'] = 0.0
            else:
                self.measurements['MEMORY_ADDRESS_ENTROPY'] = 0.0
            
            return addresses
        except Exception as e:
            print(f"Error in memory entropy measurements: {e}")
            # Set default value if measurement fails
            self.measurements['MEMORY_ADDRESS_ENTROPY'] = 0.0
            return []
    
    def calculate_composite_measurements(self):
        """Calculate composite measurements"""
        print("Calculating composite measurements...")
        
        # Overall timing CV
        timing_cvs = []
        if self.measurements.get('TIMING_BASIC_CV', 0) > 0:
            timing_cvs.append(self.measurements['TIMING_BASIC_CV'])
        if self.measurements.get('TIMING_CONSECUTIVE_CV', 0) > 0:
            timing_cvs.append(self.measurements['TIMING_CONSECUTIVE_CV'])
        
        self.measurements['OVERALL_TIMING_CV'] = float(self.mean(timing_cvs) if timing_cvs else 0.0)
        
        # Overall scheduling CV
        scheduling_cvs = []
        if self.measurements.get('SCHEDULING_THREAD_CV', 0) > 0:
            scheduling_cvs.append(self.measurements['SCHEDULING_THREAD_CV'])
        if self.measurements.get('SCHEDULING_MULTIPROC_CV', 0) > 0:
            scheduling_cvs.append(self.measurements['SCHEDULING_MULTIPROC_CV'])
        
        self.measurements['OVERALL_SCHEDULING_CV'] = float(self.mean(scheduling_cvs) if scheduling_cvs else 0.0)
    
    def run_all_measurements(self):
        """Run all measurements without any VM detection logic"""
        print("Starting system measurements...")
        print(f"Platform: {platform.system()}")
        print(f"Python version: {platform.python_version()}")
        print(f"CPU count: {os.cpu_count()}")
        print(f"Iterations: {self.iterations}")
        print()

        self.gather_system_info()
        self.measure_basic_timing()
        self.measure_consecutive_timing()
        self.measure_thread_scheduling()
        self.measure_multiprocessing_scheduling()
        self.measure_cache_behavior()
        self.measure_memory_entropy()
        self.calculate_composite_measurements()

        print("\nMeasurements complete!")
    
    def get_results(self):
        """Get results as dictionary"""
        return {
            "system_info": self.system_info,
            "measurements": self.measurements,
            "timestamp": datetime.now().isoformat(),
            "language": "python",
            "version": "1.0.0"
        }
    
    def save_results_json(self, filename=None):
        """Save pure measurements to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"measurements_{timestamp}.json"
        
        results = self.get_results()
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Measurements saved to: {filename}")
        return filename
    
    def print_results_json(self):
        """Print results in JSON format"""
        results = self.get_results()
        print(json.dumps(results, indent=2))


def main():
    """Main function"""
    # Parse command line arguments
    iterations = 1000
    if len(sys.argv) > 1:
        try:
            iterations = int(sys.argv[1])
            if iterations <= 0:
                iterations = 1000
        except ValueError:
            print("Invalid iterations argument, using default 1000")
            iterations = 1000
    
    # Create and run VMTest
    vmtest = VMTest(iterations=iterations)
    vmtest.run_all_measurements()
    
    # Output results
    print("\nResults:")
    print("=" * 50)
    vmtest.print_results_json()


if __name__ == "__main__":
    main()
