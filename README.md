# VMTEST - System Measurements Tool

A comprehensive toolkit for extracting timing, scheduling, cache, and memory measurements from computing systems based on peer-reviewed academic research.

## Overview

VMTEST is a **pure measurements tool** that extracts raw statistical data from various system behaviors without making any judgments or interpretations about the underlying environment. The tool implements measurement techniques validated by academic research to collect comprehensive timing and performance data that can be used for system analysis, performance profiling, or research purposes.

## Key Features

- **Pure Measurements Only**: Extracts raw data without VM detection logic or interpretations
- **Research-Based Techniques**: Implements measurement methods from peer-reviewed academic papers
- **Comprehensive Statistical Analysis**: Calculates mean, variance, coefficient of variation, skewness, and kurtosis
- **Cross-Platform**: Available in Python, C, JavaScript (Node.js), and Ruby implementations
- **No External Dependencies**: All implementations use only standard libraries
- **Standardized Output**: JSON format for easy integration and further analysis
- **Academic Foundation**: Based on established research methodologies

## Measurement Categories

### 1. Thread Scheduling Measurements
Based on **Lin, Z., Yang, X., & Zhang, D. (2021)**. "Detection of Virtual Machines Based on Thread Scheduling"

**Collected measurements:**
- `SCHEDULING_THREAD_MEAN`: Average thread execution time
- `SCHEDULING_THREAD_VARIANCE`: Thread timing variance
- `SCHEDULING_THREAD_CV`: Coefficient of variation for thread timing
- `SCHEDULING_THREAD_SKEWNESS`: Distribution asymmetry of thread timing
- `SCHEDULING_THREAD_KURTOSIS`: Distribution tail behavior of thread timing
- `PHYSICAL_MACHINE_INDEX`: Raw PMI calculation (kurtosis × skewness / variance)

### 2. Basic Timing Measurements
Based on **Franklin, J., et al. (2008)**. "Remote detection of virtual machine monitors with fuzzy benchmarking"

**Collected measurements:**
- `TIMING_BASIC_MEAN`: Average execution time for CPU-bound operations
- `TIMING_BASIC_VARIANCE`: Variance in basic timing measurements
- `TIMING_BASIC_CV`: Coefficient of variation for basic timing
- `TIMING_BASIC_SKEWNESS`: Distribution asymmetry of basic timing
- `TIMING_BASIC_KURTOSIS`: Distribution tail behavior of basic timing

### 3. Extended Timing Measurements
**Implementation Note**: The following measurements are implementation extensions without specific academic validation, included for comprehensive timing analysis:

**Collected measurements:**
- `TIMING_CONSECUTIVE_MEAN`: Average time for two consecutive CPU-bound operations
- `TIMING_CONSECUTIVE_VARIANCE`: Variance in consecutive operation timing
- `TIMING_CONSECUTIVE_CV`: Coefficient of variation for consecutive timing
- `TIMING_CONSECUTIVE_SKEWNESS`: Distribution asymmetry of consecutive timing
- `TIMING_CONSECUTIVE_KURTOSIS`: Distribution tail behavior of consecutive timing

**Note**: These measure the timing of running two identical CPU-bound tasks back-to-back, compared to single operations. While not based on specific research, they may reveal different scheduling or caching behaviors.

### 4. Multiprocessing Measurements
Extension of scheduling analysis to process-level operations:

**Collected measurements:**
- `SCHEDULING_MULTIPROC_MEAN`: Average multiprocess execution time
- `SCHEDULING_MULTIPROC_VARIANCE`: Multiprocess timing variance
- `SCHEDULING_MULTIPROC_CV`: Coefficient of variation for multiprocess timing
- `SCHEDULING_MULTIPROC_SKEWNESS`: Distribution asymmetry of multiprocess timing
- `SCHEDULING_MULTIPROC_KURTOSIS`: Distribution tail behavior of multiprocess timing
- `MULTIPROC_PHYSICAL_MACHINE_INDEX`: Raw PMI for multiprocess scheduling

### 5. Cache Behavior Measurements
Based on **Zhang, N., et al. (2020)**. "Detecting hardware-assisted virtualization with inconspicuous features"

**Collected measurements:**
- `CACHE_ACCESS_RATIO`: Ratio of cache-unfriendly to cache-friendly access times
- `CACHE_MISS_RATIO`: Normalized difference indicating cache behavior patterns

### 6. Memory Address Measurements
Based on **Shacham, H., et al. (2004)**. "On the effectiveness of address-space randomization"

**Collected measurements:**
- `MEMORY_ADDRESS_ENTROPY`: Shannon entropy of memory allocation patterns

### 7. Composite Measurements
**Collected measurements:**
- `OVERALL_TIMING_CV`: Combined coefficient of variation across timing measurements
- `OVERALL_SCHEDULING_CV`: Combined coefficient of variation across scheduling measurements

## Installation and Usage

### Python Version

**Requirements:**
- Python 3.6+
- psutil (optional, for enhanced system information)

**Usage:**
```bash
# Run with default 1000 iterations
python3 vmtest.py

# Run with custom iterations
python3 vmtest.py 5000
```

### C Version

**Compilation:**
```bash
# Linux
gcc -o vmtest vmtest.c -lpthread -lm -lrt -O2

# macOS
gcc -o vmtest vmtest.c -lpthread -lm -O2

# If -lrt causes issues, omit it
gcc -o vmtest vmtest.c -lpthread -lm -O2
```

**Usage:**
```bash
./vmtest
```

### JavaScript (Node.js) Version

**Requirements:**
- Node.js 12+

**Usage:**
```bash
# Run with default iterations
node vmtest.js

# Run with custom iterations
node vmtest.js 2000
```

### Ruby Version

**Requirements:**
- Ruby 2.5+

**Usage:**
```bash
# Run with default iterations
ruby vmtest.rb

# Run with custom iterations
ruby vmtest.rb 2000
```

## Output Format

All implementations produce JSON output with two main sections:

```json
{
  "system_info": {
    "platform": "Linux 5.15.0",
    "hostname": "measurement-host",
    "cpu_count": 8,
    "memory_total": 17179869184,
    "timestamp": 1641234567
  },
  "measurements": {
    "TIMING_BASIC_MEAN": 0.0234,
    "TIMING_BASIC_VARIANCE": 0.0012,
    "TIMING_BASIC_CV": 0.148,
    "TIMING_BASIC_SKEWNESS": 1.23,
    "TIMING_BASIC_KURTOSIS": 4.56,
    "TIMING_CONSECUTIVE_MEAN": 0.0245,
    "TIMING_CONSECUTIVE_VARIANCE": 0.0015,
    "TIMING_CONSECUTIVE_CV": 0.155,
    "TIMING_CONSECUTIVE_SKEWNESS": 1.18,
    "TIMING_CONSECUTIVE_KURTOSIS": 4.78,
    "SCHEDULING_THREAD_MEAN": 0.0456,
    "SCHEDULING_THREAD_VARIANCE": 0.0023,
    "SCHEDULING_THREAD_CV": 0.165,
    "SCHEDULING_THREAD_SKEWNESS": 1.15,
    "SCHEDULING_THREAD_KURTOSIS": 5.09,
    "PHYSICAL_MACHINE_INDEX": 2.34,
    "SCHEDULING_MULTIPROC_MEAN": 0.0523,
    "SCHEDULING_MULTIPROC_VARIANCE": 0.0028,
    "SCHEDULING_MULTIPROC_CV": 0.171,
    "SCHEDULING_MULTIPROC_SKEWNESS": 1.12,
    "SCHEDULING_MULTIPROC_KURTOSIS": 5.23,
    "MULTIPROC_PHYSICAL_MACHINE_INDEX": 2.67,
    "CACHE_ACCESS_RATIO": 1.45,
    "CACHE_MISS_RATIO": 0.23,
    "MEMORY_ADDRESS_ENTROPY": 3.45,
    "OVERALL_TIMING_CV": 0.151,
    "OVERALL_SCHEDULING_CV": 0.168
  }
}
```

## Understanding the Measurements

### Statistical Metrics

Each measurement category includes five key statistical metrics:

1. **Mean**: Average value of the measurements
2. **Variance**: Measure of how spread out the measurements are
3. **Coefficient of Variation (CV)**: Normalized measure of variability (standard deviation / mean)
4. **Skewness**: Measure of asymmetry in the distribution
5. **Kurtosis**: Measure of tail behavior in the distribution

### Physical Machine Index (PMI)

The PMI is calculated as: **PMI = (kurtosis × skewness) / variance**

This is a raw mathematical calculation without any threshold-based interpretations.

### Entropy Calculations

Memory address entropy uses Shannon entropy to measure the randomness in memory allocation patterns.

## Use Cases

- **System Performance Analysis**: Baseline measurements for system characterization
- **Research**: Academic studies requiring detailed timing and scheduling data
- **Benchmarking**: Comparative analysis between different systems or configurations
- **System Monitoring**: Long-term performance trend analysis
- **Academic Validation**: Reproducing results from published research papers

## Implementation Notes

### Statistical Accuracy

All implementations use bias-corrected formulas for skewness and kurtosis calculations to ensure statistical accuracy with finite sample sizes.

### Cross-Platform Compatibility

The tool is designed to work across different operating systems and architectures while maintaining measurement consistency.

### Performance Considerations

- Default iteration count is 1000 for balance between accuracy and execution time
- Multiprocessing measurements use reduced iteration counts for performance
- Cache measurements limit array sizes to prevent excessive memory usage

## Data Interpretation

**Important**: This tool provides raw measurements only. Any interpretation, analysis, or decision-making based on these measurements should be performed by separate analysis tools or frameworks.

The measurements can be used for:
- Statistical analysis and modeling
- Machine learning feature extraction
- System comparison studies
- Performance baseline establishment
- Research validation and reproduction

## Research Foundation

This tool implements measurement techniques from multiple peer-reviewed academic papers, ensuring that the collected data follows established scientific methodologies. The measurements are designed to be reproducible and consistent across different implementations and platforms.

## Future Development

Areas for potential enhancement:
- Additional measurement techniques from recent research
- Performance optimizations for high-frequency measurements
- Support for more specialized hardware measurements
- Enhanced statistical analysis methods
- Integration with analysis frameworks

## License

This project implements techniques from academic research. Please cite the relevant papers when using this tool in academic work.

## Disclaimer

This tool is designed for legitimate system analysis, research, and performance measurement purposes. The measurements collected are statistical in nature and should be interpreted appropriately within the context of your specific use case.
