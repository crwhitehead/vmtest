#!/usr/bin/env python3
"""
VMTEST Environment Measurements Script
Extracts timing, scheduling, cache, and memory measurements to detect virtualization
Based on research from Lin et al. (2021) and other VM detection papers
"""

import time
import threading
import multiprocessing
import json
import platform
import os
import sys
import ctypes
import math
import random
from collections import defaultdict

# Try to import psutil, but make it optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class VMTestMeasurements:
    def __init__(self, iterations=1000):
        self.iterations = iterations
        self.measurements = {}
    
    @staticmethod
    def mean(values):
        """Calculate mean of a list of values"""
        if not values:
            return 0
        return sum(values) / len(values)
    
    @staticmethod
    def variance(values, mean_val=None):
        """Calculate variance of a list of values"""
        if not values or len(values) < 2:
            return 0
        if mean_val is None:
            mean_val = VMTestMeasurements.mean(values)
        return sum((x - mean_val) ** 2 for x in values) / (len(values) - 1)
    
    @staticmethod
    def std_dev(values, mean_val=None):
        """Calculate standard deviation"""
        return math.sqrt(VMTestMeasurements.variance(values, mean_val))
    
    @staticmethod
    def coefficient_of_variation(values):
        """Calculate coefficient of variation (CV)"""
        mean_val = VMTestMeasurements.mean(values)
        if mean_val == 0:
            return 0
        std = VMTestMeasurements.std_dev(values, mean_val)
        return std / mean_val
    
    @staticmethod
    def skewness(values):
        """
        Calculate sample skewness with proper bias correction
        Uses the adjusted Fisher-Pearson standardized moment coefficient
        """
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
        # Formula: G1 = [(n)/(n-1)(n-2)] * [(Σ(xi-x̄)³/n) / s³]
        if n > 2:
            adjustment = math.sqrt(n * (n - 1)) / (n - 2)
            skew_corrected = skew_biased * adjustment
        else:
            skew_corrected = skew_biased
        
        return skew_corrected
    
    @staticmethod
    def kurtosis(values):
        """
        Calculate sample excess kurtosis with proper bias correction
        Uses the adjusted Fisher coefficient
        """
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
        # Formula: G2 = [(n-1)/((n-2)(n-3))] * [(n+1)*K + 6]
        # where K is the biased kurtosis
        if n > 3:
            factor1 = (n - 1) / ((n - 2) * (n - 3))
            factor2 = (n + 1) * kurt_biased + 6
            kurt_corrected = factor1 * factor2
        else:
            kurt_corrected = kurt_biased
        
        return kurt_corrected    
    
    @staticmethod
    def shannon_entropy(values, bins=20):
        """Calculate Shannon entropy of a distribution"""
        if not values:
            return 0
        
        # Create histogram
        min_val = min(values)
        max_val = max(values)
        if min_val == max_val:
            return 0
        
        bin_width = (max_val - min_val) / bins
        hist = [0] * bins
        
        for val in values:
            bin_idx = int((val - min_val) / bin_width)
            if bin_idx >= bins:
                bin_idx = bins - 1
            hist[bin_idx] += 1
        
        # Calculate probabilities and entropy
        total = sum(hist)
        entropy = 0
        for count in hist:
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        
        return entropy
        
    def measure_timing_basic(self):
        """Basic timing measurements with statistical analysis"""
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
    
    def measure_thread_scheduling(self):
        """Thread scheduling measurements based on Lin et al. research"""
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
            
            # Calculate Physical Machine Index (PMI) from Lin et al.
            # PMI = log(Kurtosis * Skewness / Variance)
            if self.measurements['SCHEDULING_THREAD_VARIANCE'] > 0:
                numerator = self.measurements['SCHEDULING_THREAD_KURTOSIS'] * self.measurements['SCHEDULING_THREAD_SKEWNESS']
                if numerator > 0:
                    pmi = math.log10(numerator / self.measurements['SCHEDULING_THREAD_VARIANCE'])
                    self.measurements['PHYSICAL_MACHINE_INDEX'] = float(pmi)
                else:
                    self.measurements['PHYSICAL_MACHINE_INDEX'] = -10.0  # Very low value indicates VM
            
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
        try:
            proc_timings = []
            
            def process_workload(queue):
                result = 0
                for i in range(10000):
                    result += i * i
                queue.put(result)
            
            # Run multiprocessing tests
            for _ in range(self.iterations // 20):  # Even fewer iterations
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
            
            # Calculate Physical Machine Index (PMI) for multiprocessing
            # PMI = log(Kurtosis * Skewness / Variance)
            if self.measurements['SCHEDULING_MULTIPROC_VARIANCE'] > 0:
                numerator = self.measurements['SCHEDULING_MULTIPROC_KURTOSIS'] * self.measurements['SCHEDULING_MULTIPROC_SKEWNESS']
                if numerator > 0:
                    pmi = math.log10(numerator / self.measurements['SCHEDULING_MULTIPROC_VARIANCE'])
                    self.measurements['MULTIPROC_PHYSICAL_MACHINE_INDEX'] = float(pmi)
                else:
                    self.measurements['MULTIPROC_PHYSICAL_MACHINE_INDEX'] = -10.0  # Very low value indicates VM
            else:
                self.measurements['MULTIPROC_PHYSICAL_MACHINE_INDEX'] = 0.0
            
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
    
    def measure_consecutive_timing(self):
        """Consecutive operation timing measurements"""
        try:
            consecutive_timings = []
            
            # Measure timing of consecutive operations
            for _ in range(self.iterations // 2):
                times = []
                for _ in range(10):  # 10 consecutive operations
                    start = time.perf_counter_ns()
                    # Simple operation
                    _ = sum(range(1000))
                    end = time.perf_counter_ns()
                    times.append(end - start)
                
                # Calculate mean of consecutive operations
                consecutive_timings.append(self.mean(times))
            
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
            return []
    
    def measure_cache_behavior(self):
        """Cache-related measurements"""
        try:
            cache_timings = []
            cache_miss_indicators = []
            
            # Large array to stress cache (using list instead of numpy array)
            array_size = 1024 * 1024  # 1M elements
            data = [random.random() for _ in range(array_size)]
            
            # Cache-friendly access pattern
            for _ in range(100):
                start = time.perf_counter_ns()
                # Sequential access
                total = sum(data)
                end = time.perf_counter_ns()
                cache_timings.append(end - start)
            
            # Cache-unfriendly access pattern
            indices = list(range(len(data)))
            random.shuffle(indices)
            
            for _ in range(100):
                start = time.perf_counter_ns()
                # Random access
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
    
    def calculate_overall_metrics(self):
        """Calculate overall/composite metrics"""
        # Overall timing CV (average of all timing CVs)
        timing_cvs = [
            self.measurements.get('TIMING_BASIC_CV', 0),
            self.measurements.get('TIMING_CONSECUTIVE_CV', 0)
        ]
        valid_timing_cvs = [cv for cv in timing_cvs if cv > 0]
        self.measurements['OVERALL_TIMING_CV'] = float(self.mean(valid_timing_cvs)) if valid_timing_cvs else 0.0
        
        # Overall scheduling CV (average of scheduling CVs)
        scheduling_cvs = [
            self.measurements.get('SCHEDULING_THREAD_CV', 0),
            self.measurements.get('SCHEDULING_MULTIPROC_CV', 0)
        ]
        valid_scheduling_cvs = [cv for cv in scheduling_cvs if cv > 0]
        self.measurements['OVERALL_SCHEDULING_CV'] = float(self.mean(valid_scheduling_cvs)) if valid_scheduling_cvs else 0.0
    
    def get_system_info(self):
        """Collect system information"""
        info = {
            'platform': platform.platform(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'cpu_count': multiprocessing.cpu_count(),
            'timestamp': time.time()
        }
        
        # Add psutil information if available
        if PSUTIL_AVAILABLE:
            try:
                info['cpu_freq'] = psutil.cpu_freq().current if psutil.cpu_freq() else 0
                info['memory_total'] = psutil.virtual_memory().total
            except Exception as e:
                print(f"Warning: Could not get psutil info: {e}")
                info['cpu_freq'] = 0
                info['memory_total'] = 0
        else:
            info['cpu_freq'] = 0
            info['memory_total'] = 0
            info['psutil_available'] = False
        
        return info
    
    def run_all_measurements(self):
        """Run all measurement tests"""
        print("Starting VMTEST measurements...")
        
        print("1. Basic timing measurements...")
        self.measure_timing_basic()
        
        print("2. Thread scheduling measurements...")
        self.measure_thread_scheduling()
        
        print("3. Multiprocessing scheduling measurements...")
        self.measure_multiprocessing_scheduling()
        
        print("4. Consecutive timing measurements...")
        self.measure_consecutive_timing()
        
        print("5. Cache behavior measurements...")
        self.measure_cache_behavior()
        
        print("6. Memory entropy measurements...")
        self.measure_memory_entropy()
        
        print("7. Calculating overall metrics...")
        self.calculate_overall_metrics()
        
        print("Measurements complete!")
    
    def export_results(self):
        """Export results in standardized format"""
        results = {
            'system_info': self.get_system_info(),
            'measurements': self.measurements,
            'vm_indicators': self.analyze_vm_indicators()
        }
        return results
    
    def analyze_vm_indicators(self):
        """Analyze measurements for VM indicators"""
        indicators = {}
        
        # High scheduling variance indicates VM (Lin et al.)
        if 'SCHEDULING_THREAD_CV' in self.measurements:
            indicators['high_scheduling_variance'] = self.measurements['SCHEDULING_THREAD_CV'] > 0.15
        
        # Low PMI indicates VM
        if 'PHYSICAL_MACHINE_INDEX' in self.measurements:
            indicators['low_pmi'] = self.measurements['PHYSICAL_MACHINE_INDEX'] < 1.0
        
        # Low multiproc PMI indicates VM
        if 'MULTIPROC_PHYSICAL_MACHINE_INDEX' in self.measurements:
            indicators['low_multiproc_pmi'] = self.measurements['MULTIPROC_PHYSICAL_MACHINE_INDEX'] < 1.0
        
        # High cache miss ratio indicates VM
        if 'CACHE_MISS_RATIO' in self.measurements:
            indicators['high_cache_miss'] = self.measurements['CACHE_MISS_RATIO'] > 0.5
        
        # Low memory entropy indicates VM
        if 'MEMORY_ADDRESS_ENTROPY' in self.measurements:
            indicators['low_memory_entropy'] = self.measurements['MEMORY_ADDRESS_ENTROPY'] < 2.0
        
        # Overall VM likelihood
        vm_score = sum(1 for v in indicators.values() if v) / len(indicators) if indicators else 0
        indicators['vm_likelihood_score'] = vm_score
        indicators['likely_vm'] = vm_score > 0.5
        
        return indicators

def main():
    # Parse command line arguments
    iterations = 1000
    if len(sys.argv) > 1:
        try:
            iterations = int(sys.argv[1])
        except ValueError:
            print(f"Invalid iterations: {sys.argv[1]}, using default: 1000")
    
    # Create measurement instance
    vmtest = VMTestMeasurements(iterations=iterations)
    
    # Run measurements
    vmtest.run_all_measurements()
    
    # Export results
    results = vmtest.export_results()
    
    # Print results in JSON format
    print("\n" + "="*60)
    print("VMTEST MEASUREMENT RESULTS")
    print("="*60)
    print(json.dumps(results, indent=2))
    
    # Save to file
    filename = f"vmtest_results_{int(time.time())}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {filename}")

if __name__ == "__main__":
    main()
