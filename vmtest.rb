#!/usr/bin/env ruby

##
# VMTEST Environment Measurements - Ruby Version
# Extracts timing, scheduling, cache, and memory measurements to detect virtualization
# Based on research from Lin et al. (2021) and other VM detection papers
##

require 'json'
require 'thread'
require 'etc'
require 'rbconfig'
require 'benchmark'

class VMTestMeasurements
  ITERATIONS_DEFAULT = 1000
  THREAD_COUNT = 4
  CACHE_SIZE = 1024 * 1024  # 1MB

  def initialize(iterations = ITERATIONS_DEFAULT)
    @iterations = iterations
    @measurements = {}
    @system_info = {}
  end

  # High-resolution timer in nanoseconds
  def get_time_ns
    Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)
  end

  # Statistical calculation methods
  def self.mean(values)
    return 0 if values.nil? || values.empty?
    values.sum.to_f / values.length
  end

  def self.variance(values, mean_val = nil)
    return 0 if values.nil? || values.length < 2
    mean_val ||= mean(values)
    sum_squared_diffs = values.map { |val| (val - mean_val) ** 2 }.sum
    sum_squared_diffs / (values.length - 1).to_f
  end

  def self.standard_deviation(values, mean_val = nil)
    Math.sqrt(variance(values, mean_val))
  end

  def self.coefficient_of_variation(values)
    mean_val = mean(values)
    return 0 if mean_val == 0
    std_dev = standard_deviation(values, mean_val)
    std_dev / mean_val
  end

  def self.skewness(values)
    return 0 if values.nil? || values.length < 3
    mean_val = mean(values)
    std_dev = standard_deviation(values, mean_val)
    return 0 if std_dev <= 0

    sum_cubed_deviations = values.map do |val|
      deviation = (val - mean_val) / std_dev
      deviation ** 3
    end.sum

    skew = sum_cubed_deviations / values.length.to_f

    # Apply bias correction for small samples
    if values.length > 2
      n = values.length
      skew = skew * Math.sqrt(n * (n - 1)) / (n - 2)
    end

    # Bound checking
    [[skew, -100].max, 100].min
  end

  def self.kurtosis(values)
    return 0 if values.nil? || values.length < 4
    mean_val = mean(values)
    std_dev = standard_deviation(values, mean_val)
    return 0 if std_dev <= 0

    sum_quarted_deviations = values.map do |val|
      deviation = (val - mean_val) / std_dev
      deviation ** 4
    end.sum

    kurt = (sum_quarted_deviations / values.length.to_f) - 3.0  # Excess kurtosis

    # Apply bias correction for small samples
    if values.length > 3
      n = values.length
      kurt = ((n - 1) / ((n - 2) * (n - 3)).to_f) * ((n + 1) * kurt + 6)
    end

    # Bound checking
    [[kurt, -100].max, 100].min
  end

  # CPU-bound computation for timing measurements
  def cpu_bound_task
    start_time = get_time_ns
    
    # Computational work similar to C version
    result = 0
    10000.times do |i|
      result += Math.sqrt(i) * Math.sin(i) + Math.cos(i * 0.1)
    end
    
    end_time = get_time_ns
    end_time - start_time
  end

  # Memory-intensive task for cache testing
  def cache_unfriendly_access
    start_time = get_time_ns
    size = CACHE_SIZE
    buffer = "\x00" * size
    
    # Random access pattern (cache-unfriendly)
    1000.times do |i|
      offset = rand(size - 4)
      # Simulate memory write with string manipulation
      buffer[offset, 4] = [i].pack('N')
    end
    
    end_time = get_time_ns
    end_time - start_time
  end

  def cache_friendly_access
    start_time = get_time_ns
    size = CACHE_SIZE
    buffer = "\x00" * size
    
    # Sequential access pattern (cache-friendly)
    (0...size).step(4) do |i|
      buffer[i, 4] = [i].pack('N')
    end
    
    end_time = get_time_ns
    end_time - start_time
  end

  # Memory address entropy calculation
  def calculate_memory_entropy
    addresses = []
    1000.times do
      # Allocate memory and use object_id as address proxy
      buffer = " " * 64
      addresses << buffer.object_id
    end

    # Calculate Shannon entropy using object_id buckets
    address_counts = Hash.new(0)
    addresses.each do |addr|
      bucket_addr = addr / 4096  # 4KB buckets
      address_counts[bucket_addr] += 1
    end

    entropy = 0.0
    total = addresses.length.to_f
    address_counts.values.each do |count|
      probability = count / total
      entropy -= probability * Math.log2(probability) if probability > 0
    end

    entropy
  end

  # Basic timing measurements
  def measure_basic_timing
    puts "Measuring basic timing patterns..."
    times = []
    
    @iterations.times do
      exec_time = cpu_bound_task
      times << exec_time
    end

    mean = self.class.mean(times)
    variance = self.class.variance(times, mean)
    cv = self.class.coefficient_of_variation(times)
    skewness = self.class.skewness(times)
    kurtosis = self.class.kurtosis(times)

    @measurements[:TIMING_BASIC_MEAN] = mean
    @measurements[:TIMING_BASIC_VARIANCE] = variance
    @measurements[:TIMING_BASIC_CV] = cv
    @measurements[:TIMING_BASIC_SKEWNESS] = skewness
    @measurements[:TIMING_BASIC_KURTOSIS] = kurtosis
  end

  # Consecutive timing measurements
  def measure_consecutive_timing
    puts "Measuring consecutive timing patterns..."
    times = []
    
    @iterations.times do
      start_time = get_time_ns
      # Two consecutive operations
      cpu_bound_task
      cpu_bound_task
      end_time = get_time_ns
      times << (end_time - start_time)
    end

    mean = self.class.mean(times)
    variance = self.class.variance(times, mean)
    cv = self.class.coefficient_of_variation(times)
    skewness = self.class.skewness(times)
    kurtosis = self.class.kurtosis(times)

    @measurements[:TIMING_CONSECUTIVE_MEAN] = mean
    @measurements[:TIMING_CONSECUTIVE_VARIANCE] = variance
    @measurements[:TIMING_CONSECUTIVE_CV] = cv
    @measurements[:TIMING_CONSECUTIVE_SKEWNESS] = skewness
    @measurements[:TIMING_CONSECUTIVE_KURTOSIS] = kurtosis
  end

  # Thread scheduling measurements
  def measure_thread_scheduling
    puts "Measuring thread scheduling patterns..."
    times = []
    mutex = Mutex.new
    
    target = @iterations/10
    completed = 0
    
    # Use a queue to manage work
    work_queue = Queue.new
    target.times { work_queue << true }

    # Worker thread function
    worker = proc do
      while work_queue.length > 0
        begin
          work_queue.pop(true)  # non-blocking pop
          exec_time = cpu_bound_task
          
          mutex.synchronize do
            times << exec_time
            completed += 1
          end
        rescue ThreadError
          # Queue is empty
          break
        end
      end
    end

    # Create and start worker threads
    threads = []
    THREAD_COUNT.times do
      threads << Thread.new(&worker)
    end

    # Wait for all threads to complete
    threads.each(&:join)

    # Calculate statistics
    mean = self.class.mean(times)
    variance = self.class.variance(times, mean)
    std_dev = self.class.standard_deviation(times, mean)
    cv = self.class.coefficient_of_variation(times)
    skewness = self.class.skewness(times)
    kurtosis = self.class.kurtosis(times)

    # Physical Machine Index (PMI) calculation
    pmi = (skewness * kurtosis) / (cv * 100)

    @measurements[:SCHEDULING_THREAD_MEAN] = mean
    @measurements[:SCHEDULING_THREAD_VARIANCE] = variance
    @measurements[:SCHEDULING_THREAD_CV] = cv
    @measurements[:SCHEDULING_THREAD_SKEWNESS] = skewness
    @measurements[:SCHEDULING_THREAD_KURTOSIS] = kurtosis
    @measurements[:PHYSICAL_MACHINE_INDEX] = pmi
  end

  # Multiprocessing measurements using fork
  def measure_multiprocessing
    puts "Measuring multiprocessing patterns..."
    times = []
    target = [@iterations, 100].min  # Limit for performance

    target.times do
      start_time = get_time_ns
      
      pid = fork do
        # CPU-bound work in child process
        result = 0
        10000.times do |i|
          result += Math.sqrt(i) * Math.sin(i) + Math.cos(i * 0.1)
        end
        exit(0)
      end
      
      Process.wait(pid)
      end_time = get_time_ns
      times << (end_time - start_time)
    end

    mean = self.class.mean(times)
    variance = self.class.variance(times, mean)
    cv = self.class.coefficient_of_variation(times)
    skewness = self.class.skewness(times)
    kurtosis = self.class.kurtosis(times)

    pmi = (skewness * kurtosis) / (cv * 100)

    @measurements[:SCHEDULING_MULTIPROC_MEAN] = mean
    @measurements[:SCHEDULING_MULTIPROC_VARIANCE] = variance
    @measurements[:SCHEDULING_MULTIPROC_CV] = cv
    @measurements[:SCHEDULING_MULTIPROC_SKEWNESS] = skewness
    @measurements[:SCHEDULING_MULTIPROC_KURTOSIS] = kurtosis
    @measurements[:MULTIPROC_PHYSICAL_MACHINE_INDEX] = pmi
  end

  # Cache behavior measurements
  def measure_cache_behavior
    puts "Measuring cache behavior patterns..."
    unfriendly_times = []
    friendly_times = []

    iterations = [@iterations, 100].min
    iterations.times do
      unfriendly_times << cache_unfriendly_access
      friendly_times << cache_friendly_access
    end

    unfriendly_mean = self.class.mean(unfriendly_times)
    friendly_mean = self.class.mean(friendly_times)

    @measurements[:CACHE_ACCESS_RATIO] = unfriendly_mean / friendly_mean.to_f
    @measurements[:CACHE_MISS_RATIO] = (unfriendly_mean - friendly_mean) / friendly_mean.to_f
  end

  # Memory entropy measurement
  def measure_memory_entropy
    puts "Measuring memory address entropy..."
    @measurements[:MEMORY_ADDRESS_ENTROPY] = calculate_memory_entropy
  end

  # Gather system information
  def gather_system_info
    puts "Gathering system information..."
    
    # Get platform info safely
    platform_info = begin
      "#{RbConfig::CONFIG['host_os']} #{`uname -r`.strip}"
    rescue
      RbConfig::CONFIG['host_os']
    end
    
    # Get hostname safely
    hostname_info = begin
      `hostname`.strip
    rescue
      'Unknown'
    end
    
    @system_info = {
      platform: platform_info,
      hostname: hostname_info,
      architecture: RbConfig::CONFIG['host_cpu'],
      cpu_count: Etc.nprocessors,
      ruby_version: RUBY_VERSION,
      ruby_platform: RUBY_PLATFORM,
      ruby_engine: defined?(RUBY_ENGINE) ? RUBY_ENGINE : 'ruby'
    }

    # Try to get memory information
    begin
      if RbConfig::CONFIG['host_os'] =~ /linux/i
        meminfo = File.read('/proc/meminfo')
        if meminfo =~ /MemTotal:\s+(\d+)\s+kB/
          @system_info[:total_memory] = $1.to_i * 1024  # Convert to bytes
        end
      elsif RbConfig::CONFIG['host_os'] =~ /darwin/i
        # macOS
        begin
          mem_output = `sysctl hw.memsize`.strip
          if mem_output =~ /hw\.memsize:\s+(\d+)/
            @system_info[:total_memory] = $1.to_i
          end
        rescue
          @system_info[:total_memory] = nil
        end
      end
    rescue
      @system_info[:total_memory] = nil
    end

    # Check for VM indicators
    vm_indicators = {}
    
    begin
      # Check CPU information
      if File.exist?('/proc/cpuinfo')
        begin
          cpuinfo = File.read('/proc/cpuinfo')
          vm_indicators[:hypervisor_flag] = cpuinfo.include?('hypervisor')
          vm_indicators[:vm_cpu_model] = /virtual|qemu|kvm|xen|vmware/i.match?(cpuinfo)
        rescue
          # Ignore file read errors
        end
      end
      
      # Check for VM-specific files
      vm_indicators[:openvz_detected] = File.exist?('/proc/vz')
      vm_indicators[:xen_detected] = File.exist?('/proc/xen')
      
      # Check DMI information
      if File.exist?('/sys/devices/virtual/dmi/id/sys_vendor')
        begin
          vendor = File.read('/sys/devices/virtual/dmi/id/sys_vendor').strip
          vm_indicators[:vm_vendor] = /vmware|virtualbox|qemu|xen|microsoft|innotek/i.match?(vendor)
        rescue
          # Ignore file read errors
        end
      end
    rescue
      # Ignore errors on non-Linux systems
    end

    @system_info[:vm_indicators] = vm_indicators
  end

  # Calculate overall VM likelihood
  def calculate_vm_indicators
    indicators = {
      high_scheduling_variance: @measurements[:SCHEDULING_THREAD_CV] > 0.15,
      low_pmi: @measurements[:PHYSICAL_MACHINE_INDEX] < 1.0,
      high_timing_variance: @measurements[:TIMING_BASIC_CV] > 0.1,
      abnormal_cache_ratio: @measurements[:CACHE_ACCESS_RATIO] > 2.0,
      low_memory_entropy: @measurements[:MEMORY_ADDRESS_ENTROPY] < 3.0
    }

    # Calculate likelihood score
    weights = {
      high_scheduling_variance: 0.4,
      low_pmi: 0.3,
      high_timing_variance: 0.15,
      abnormal_cache_ratio: 0.1,
      low_memory_entropy: 0.05
    }

    score = 0.0
    indicators.each do |key, value|
      score += weights[key] || 0 if value
    end

    indicators[:vm_likelihood_score] = score
    indicators[:likely_vm] = score > 0.5

    indicators
  end

  # Run all measurements
  def run_all_measurements
    puts "Starting VMtest measurements..."
    puts "Ruby version: #{RUBY_VERSION}"
    puts "Platform: #{RbConfig::CONFIG['host_os']}"
    puts "CPU count: #{Etc.nprocessors}"
    
    begin
      if @system_info[:total_memory]
        puts "Memory: #{(@system_info[:total_memory] / 1024.0 / 1024.0 / 1024.0).round(2)} GB"
      end
    rescue
      # Memory info not available
    end
    
    puts "Iterations: #{@iterations}"
    puts ""

    gather_system_info

    measure_basic_timing
    measure_consecutive_timing
    measure_thread_scheduling
    
    # Only measure multiprocessing on Unix-like systems
    if RbConfig::CONFIG['host_os'] !~ /mswin|mingw|cygwin/i
      measure_multiprocessing
    else
      puts "Skipping multiprocessing measurements on Windows"
      @measurements[:SCHEDULING_MULTIPROC_MEAN] = 0
      @measurements[:SCHEDULING_MULTIPROC_VARIANCE] = 0
      @measurements[:SCHEDULING_MULTIPROC_CV] = 0
      @measurements[:SCHEDULING_MULTIPROC_SKEWNESS] = 0
      @measurements[:SCHEDULING_MULTIPROC_KURTOSIS] = 0
      @measurements[:MULTIPROC_PHYSICAL_MACHINE_INDEX] = 0
    end
    
    measure_cache_behavior
    measure_memory_entropy

    # Calculate overall coefficients of variation
    timing_cvs = [
      @measurements[:TIMING_BASIC_CV],
      @measurements[:TIMING_CONSECUTIVE_CV]
    ]
    scheduling_cvs = [
      @measurements[:SCHEDULING_THREAD_CV],
      @measurements[:SCHEDULING_MULTIPROC_CV]
    ]

    @measurements[:OVERALL_TIMING_CV] = self.class.mean(timing_cvs)
    @measurements[:OVERALL_SCHEDULING_CV] = self.class.mean(scheduling_cvs)

    vm_indicators = calculate_vm_indicators

    {
      system_info: @system_info,
      measurements: @measurements,
      vm_indicators: vm_indicators,
      timestamp: Time.now.strftime('%Y-%m-%dT%H:%M:%S%z'),
      language: 'Ruby',
      version: '1.0.0'
    }
  end
end

# Main execution
def main
  iterations = ARGV[0] ? ARGV[0].to_i : VMTestMeasurements::ITERATIONS_DEFAULT
  
  if iterations < 1
    puts "Usage: ruby vmtest.rb [iterations]"
    puts "Example: ruby vmtest.rb 1000"
    exit 1
  end

  vmtest = VMTestMeasurements.new(iterations)
  
  begin
    results = vmtest.run_all_measurements
    
    puts "\n" + "=" * 50
    puts "VMTEST RESULTS"
    puts "=" * 50
    
    # Print formatted results
    puts JSON.pretty_generate(results)
    
    puts "\n" + "=" * 50
    puts "VM DETECTION SUMMARY"
    puts "=" * 50
    
    vm_indicators = results[:vm_indicators]
    puts "VM Likelihood Score: #{(vm_indicators[:vm_likelihood_score] * 100).round(1)}%"
    puts "Likely Virtual Machine: #{vm_indicators[:likely_vm] ? 'YES' : 'NO'}"
    
    if vm_indicators[:likely_vm]
      puts "\nVM Indicators Detected:"
      vm_indicators.each do |key, value|
        if value == true && key != :likely_vm
          puts "  - #{key.to_s.gsub('_', ' ')}"
        end
      end
    end
    
  rescue => error
    puts "Error running VMtest: #{error}"
    puts error.backtrace
    exit 1
  end
end

# Only run main if this file is executed directly
if __FILE__ == $0
  main
end
