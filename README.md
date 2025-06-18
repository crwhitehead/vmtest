# VMTEST - Virtual Machine Detection through Performance Analysis

## Project Overview

VMTEST is framework to test performance-based measurements and machine learning classification to distinguish between virtualized and physical environments across interpreted languages. The project implements multiple detection techniques drawn from academic research to create a robust VM detection system that can identify various virtualization platforms through timing, scheduling, memory, and system behavior analysis.

## Goals

- **Develop robust VM detection**: Create reliable methods to detect virtual machine environments that are difficult to circumvent
- **Performance-based approach**: Use timing and performance characteristics rather than easily-spoofable system artifacts
- **Machine learning classification**: Apply statistical analysis and ML techniques to improve detection accuracy
- **Multi-dimensional analysis**: Combine multiple measurement vectors for comprehensive VM fingerprinting
- **Research validation**: Implement and validate techniques from established academic literature

## Project Structure

The VMTEST framework consists of several core components:

### 1. Data Collection Layer
- **C Implementation** (`vmtest.c`)
- **Python Implementation** (`vmtest.py`)
- More interpreted languages to come

### 2. Measurement Modules
Each module captures specific aspects of system behavior that differ between physical and virtual environments:

#### **Timing Analysis**
- RDTSC (Read Time Stamp Counter) precision timing
- Consecutive timing measurements to detect VM exits
- Statistical analysis of timing variance and distribution

#### **Thread/Process Scheduling Analysis** 
- Multiprocessing scheduling behavior measurement
- GIL (Global Interpreter Lock) contention analysis in Python
- Thread execution time distribution analysis
- Detection of two-level scheduling overhead in VMs

#### **Memory Allocation Patterns**
- Memory allocation/deallocation timing
- Address space randomization patterns
- Garbage collection behavior analysis
- Memory fragmentation detection

#### **Cache Behavior Analysis**
- CPU cache miss/hit ratio measurements
- Memory access pattern timing
- Cache line behavior analysis
- Sequential vs. random access patterns

#### **System Characteristics**
- System call timing and behavior
- I/O performance patterns
- Hardware-specific measurements

### 3. Machine Learning Classification
The framework outputs standardized metrics for ML processing:
- **Coefficient of Variation (CV)** for timing measurements
- **Statistical distributions** (variance, skewness, kurtosis)
- **Performance ratios** and composite indices
- **Detection confidence scores**

## VM Detection Measurements

### Core Timing Measurements

#### 1. RDTSC Timing Analysis
**Based on**: Various VM detection research papers including work by Liston & Skoudis and Ferrie

**Measurements**:
- Basic RDTSC timing variance
- Consecutive RDTSC call overhead
- VM-exit detection through timing anomalies
- Statistical distribution analysis (mean, variance, coefficient of variation, skewness, kurtosis)

**Key Insight**: Virtual machines introduce timing overhead due to hypervisor intervention and VM exits

#### 2. Thread Scheduling Analysis
**Based on**: Lin et al. "Detection of Virtual Machines Based on Thread Scheduling" and hypervisor scheduling research

**Measurements**:
- Thread execution time distributions
- Two-level scheduling detection (guest OS + hypervisor)
- Multiprocessing vs. threading behavior differences
- GIL contention patterns in interpreted languages

**Key Insight**: VMs exhibit characteristic scheduling patterns due to dual-level scheduling (guest + host OS)

### Memory and Cache Analysis

#### 3. Memory Allocation Patterns
**Based on**: Memory management research and VM behavior studies

**Measurements**:
- Allocation/deallocation timing consistency
- Address space layout differences
- Memory fragmentation patterns
- Garbage collection timing in managed languages

#### 4. Cache Behavior Analysis
**Based on**: CPU cache research and VM memory virtualization studies

**Measurements**:
- Cache miss/hit ratios
- Memory access timing patterns
- Cache line behavior differences
- Sequential vs. random access performance

### System-Level Detection

#### 5. Hardware-Specific Measurements
**Based on**: Klein's Scoopy tool and various hardware detection methods

**Measurements**:
- System descriptor table analysis (IDT, GDT, LDT locations)
- Hardware instruction timing
- I/O performance characteristics
- System call overhead analysis

## Key Research Papers and Citations

### Primary Research Sources

1. **Lin, Z. et al.** "Detection of Virtual Machines Based on Thread Scheduling"
   - Provides theoretical foundation for scheduling-based VM detection
   - Introduces probability models for two-level scheduling
   - Defines Virtual Machine Index (VMI) and Physical Machine Index (PMI)

2. **Lau, B. & Svajcer, V.** "Measuring virtual machine detection in malware using DSD tracer"
   - Comprehensive analysis of VM detection techniques in malware
   - DSD-Tracer framework for dynamic analysis
   - Case studies with Themida and other packers

3. **Xiao, J. et al.** "Hyperprobe: Towards Virtual Machine Extrospection" (LISA15)
   - Framework for detecting hypervisor versions and features
   - KVM feature detection and fingerprinting
   - Hardware virtualization feature analysis

4. **Liston, T. & Skoudis, E.** "On the cutting edge: thwarting virtual machine detection"
   - Survey of VM detection and evasion techniques
   - Analysis of Red Pill, Scoopy, and other detection tools
   - Countermeasures and mitigation strategies

5. **Klein, T.** Scoopy Doo tool and research
   - IDT, GDT, and LDT location-based detection
   - System descriptor table analysis techniques
   - Hardware-specific VM fingerprinting

6. **Ferrie, P.** "Attacks on virtual machine emulators"
   - Comprehensive catalog of VM detection techniques
   - Timing-based detection methods
   - Anti-emulation techniques

### Supporting Research

7. **Rutkowska, J.** "Red Pill" technique
   - Original IDT-based VM detection
   - Foundation for descriptor table analysis

8. **Methods for Virtual Machine Detection** (S21sec)
   - Practical VM detection implementation
   - Assembly-level detection techniques

9. **VMDE (Virtual Machine Detection Engine)** research
   - Focus on hardware-based detection
   - BIOS and hardware enumeration techniques

## Statistical Analysis Framework

The framework employs sophisticated statistical analysis based on the observation that virtual machines exhibit different performance characteristics:

### Key Metrics
- **Coefficient of Variation (CV)**: Measures timing consistency
- **Variance, Skewness, Kurtosis**: Distribution shape analysis  
- **Performance Ratios**: Comparative timing measurements
- **Composite Indices**: Combined detection confidence scores

### Machine Learning Features
The system outputs structured data suitable for ML classification:
```
OVERALL_TIMING_CV: Timing measurement consistency
OVERALL_MULTIPROC_CV: Multiprocessing scheduling variance  
OVERALL_GIL_CV: Threading behavior variance
OVERALL_MEMORY_CV: Memory allocation consistency
OVERALL_CACHE_RATIO: Cache performance ratios
DETECTION_CONFIDENCE: Composite detection score
```

## Usage

### C Implementation
```bash
# Compile with optimization
gcc -O2 -march=native -pthread -lm vmtest.c -o vmtest

# Run and capture output
./vmtest > vmtest_results.txt
```

### Python Implementation  
```bash
# Run with required dependencies
python3 vmtest.py > vmtest_results.txt
```

## Dependencies

### C Implementation
- GCC with pthread support
- x86/x64 architecture with RDTSC support
- POSIX-compliant system

### Python Implementation
- Python 3.6+
- NumPy
- psutil
- Standard library modules (threading, multiprocessing, statistics, etc.)

## Output Format

Both implementations produce standardized output suitable for machine learning processing, with detailed measurements and summary statistics for VM detection classification.

## License and Academic Use

This research implementation is designed for academic and security research purposes. When using this work, please cite the relevant research papers listed above that provided the theoretical foundation for these detection techniques.
