#!/usr/bin/env python3

"""
Unified VMtest Runner
Orchestrates execution of VMtest across multiple language implementations
and provides consolidated analysis and reporting.
"""

import json
import os
import sys
import time
import subprocess
import platform
import shutil
import argparse
from datetime import datetime
from pathlib import Path
import tempfile
import zipfile

class UnifiedVMTestRunner:
    def __init__(self, iterations=1000, output_dir=None, verbose=False):
        self.iterations = iterations
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="vmtest_")
        self.verbose = verbose
        self.results = {}
        self.implementations = {
            'c': {
                'binary': 'vmtest',
                'source': 'vmtest.c',
                'compile_cmd': self._get_c_compile_cmd(),
                'run_cmd': './vmtest'
            },
            'python': {
                'binary': 'vmtest.py',
                'source': 'vmtest.py',
                'run_cmd': f'python3 vmtest.py {iterations}'
            },
            'nodejs': {
                'binary': 'vmtest.js',
                'source': 'vmtest.js', 
                'run_cmd': f'node vmtest.js {iterations}'
            },
            'ruby': {
                'binary': 'vmtest.rb',
                'source': 'vmtest.rb',
                'run_cmd': f'ruby vmtest.rb {iterations}'
            }
        }
        
    def _get_c_compile_cmd(self):
        """Get appropriate C compilation command for the platform"""
        if platform.system() == 'Darwin':  # macOS
            return 'gcc -o vmtest vmtest.c -lpthread -lm -O2'
        elif platform.system() == 'Linux':
            return 'gcc -o vmtest vmtest.c -lpthread -lm -lrt -O2'
        else:  # Windows or other
            return 'gcc -o vmtest.exe vmtest.c -lpthread -lm -O2'

    def _log(self, message, level='INFO'):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prefix = f"[{timestamp}] [{level}]"
        print(f"{prefix} {message}")
        
        if self.verbose or level in ['ERROR', 'WARNING']:
            sys.stdout.flush()

    def _check_dependencies(self):
        """Check if required interpreters/compilers are available"""
        dependencies = {
            'c': ['gcc', '--version'],
            'python': ['python3', '--version'],
            'nodejs': ['node', '--version'],
            'ruby': ['ruby', '--version']
        }
        
        available = {}
        for lang, cmd in dependencies.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version = result.stdout.strip().split('\n')[0]
                    available[lang] = version
                    self._log(f"{lang.upper()} available: {version}")
                else:
                    self._log(f"{lang.upper()} not available", 'WARNING')
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self._log(f"{lang.upper()} not available", 'WARNING')
                
        return available

    def _compile_c_implementation(self):
        """Compile the C implementation if source exists"""
        if not os.path.exists('vmtest.c'):
            self._log("vmtest.c not found, skipping C compilation", 'WARNING')
            return False
            
        try:
            cmd = self.implementations['c']['compile_cmd']
            self._log(f"Compiling C implementation: {cmd}")
            
            result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self._log("C compilation successful")
                return True
            else:
                self._log(f"C compilation failed: {result.stderr}", 'ERROR')
                return False
                
        except subprocess.TimeoutExpired:
            self._log("C compilation timed out", 'ERROR')
            return False
        except Exception as e:
            self._log(f"C compilation error: {e}", 'ERROR')
            return False

    def _run_implementation(self, lang, available_deps):
        """Run a specific language implementation"""
        if lang not in available_deps:
            self._log(f"Skipping {lang.upper()}: interpreter/compiler not available", 'WARNING')
            return None
            
        impl = self.implementations[lang]
        
        # Check if source file exists
        if not os.path.exists(impl['source']):
            self._log(f"Skipping {lang.upper()}: source file {impl['source']} not found", 'WARNING')
            return None
            
        # Special handling for C - need to compile first
        if lang == 'c':
            if not self._compile_c_implementation():
                return None
                
        try:
            self._log(f"Running {lang.upper()} implementation...")
            start_time = time.time()
            
            # Execute the implementation
            cmd = impl['run_cmd']
            if isinstance(cmd, str):
                cmd = cmd.split()
                
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=os.getcwd()
            )
            
            execution_time = time.time() - start_time
            
            if result.returncode != 0:
                self._log(f"{lang.upper()} execution failed: {result.stderr}", 'ERROR')
                return None
                
            # Parse JSON output
            try:
                # Extract JSON from output (might have other text before/after)
                output_lines = result.stdout.strip().split('\n')
                json_start = -1
                json_end = -1
                
                for i, line in enumerate(output_lines):
                    if line.strip().startswith('{'):
                        json_start = i
                        break
                        
                if json_start >= 0:
                    for i in range(len(output_lines) - 1, json_start - 1, -1):
                        if output_lines[i].strip().endswith('}'):
                            json_end = i
                            break
                            
                if json_start >= 0 and json_end >= 0:
                    json_text = '\n'.join(output_lines[json_start:json_end + 1])
                    data = json.loads(json_text)
                    
                    # Add execution metadata
                    data['execution_time_seconds'] = execution_time
                    data['language'] = lang
                    
                    self._log(f"{lang.upper()} completed in {execution_time:.2f}s")
                    return data
                else:
                    self._log(f"{lang.upper()}: Could not find JSON output", 'ERROR')
                    if self.verbose:
                        self._log(f"Output was: {result.stdout[:500]}...")
                    return None
                    
            except json.JSONDecodeError as e:
                self._log(f"{lang.upper()}: JSON parsing failed: {e}", 'ERROR')
                if self.verbose:
                    self._log(f"Output was: {result.stdout[:500]}...")
                return None
                
        except subprocess.TimeoutExpired:
            self._log(f"{lang.upper()} execution timed out", 'ERROR')
            return None
        except Exception as e:
            self._log(f"{lang.upper()} execution error: {e}", 'ERROR')
            return None

    def _analyze_cross_language_results(self):
        """Perform cross-language analysis of results"""
        if not self.results:
            return {}
            
        analysis = {
            'languages_tested': list(self.results.keys()),
            'consistent_vm_detection': True,
            'measurement_consistency': {},
            'performance_comparison': {},
            'consensus': {}
        }
        
        # Extract VM detection results
        vm_detections = {}
        for lang, result in self.results.items():
            if result and 'vm_indicators' in result:
                vm_detections[lang] = result['vm_indicators'].get('likely_vm', False)
                
        # Check consensus on VM detection
        if vm_detections:
            vm_votes = list(vm_detections.values())
            vm_consensus = sum(vm_votes) / len(vm_votes)
            analysis['consensus']['vm_detection_rate'] = vm_consensus
            analysis['consensus']['likely_vm'] = vm_consensus > 0.5
            
            # Check if all implementations agree
            analysis['consistent_vm_detection'] = len(set(vm_votes)) <= 1
            analysis['vm_detection_by_language'] = vm_detections
            
        # Compare key measurements across languages
        key_measurements = [
            'SCHEDULING_THREAD_CV',
            'PHYSICAL_MACHINE_INDEX', 
            'TIMING_BASIC_CV',
            'CACHE_ACCESS_RATIO',
            'MEMORY_ADDRESS_ENTROPY'
        ]
        
        for measurement in key_measurements:
            values = {}
            for lang, result in self.results.items():
                if result and 'measurements' in result:
                    if measurement in result['measurements']:
                        values[lang] = result['measurements'][measurement]
                        
            if len(values) > 1:
                # Calculate coefficient of variation across implementations
                vals_list = list(values.values())
                mean_val = sum(vals_list) / len(vals_list)
                variance = sum((x - mean_val) ** 2 for x in vals_list) / len(vals_list)
                cv = (variance ** 0.5) / mean_val if mean_val != 0 else 0
                
                analysis['measurement_consistency'][measurement] = {
                    'values_by_language': values,
                    'mean': mean_val,
                    'coefficient_of_variation': cv,
                    'consistent': cv < 0.2  # Less than 20% variation
                }
                
        # Performance comparison
        for lang, result in self.results.items():
            if result and 'execution_time_seconds' in result:
                analysis['performance_comparison'][lang] = result['execution_time_seconds']
                
        return analysis

    def _generate_report(self, analysis):
        """Generate comprehensive report"""
        report = {
            'unified_vmtest_report': {
                'timestamp': datetime.now().isoformat(),
                'test_parameters': {
                    'iterations': self.iterations,
                    'languages_attempted': list(self.implementations.keys()),
                    'languages_successful': list(self.results.keys())
                },
                'individual_results': self.results,
                'cross_language_analysis': analysis,
                'summary': {
                    'total_languages_tested': len(self.results),
                    'consensus_vm_detection': analysis.get('consensus', {}).get('likely_vm', None),
                    'detection_confidence': analysis.get('consensus', {}).get('vm_detection_rate', 0),
                    'measurements_consistent': all(
                        m.get('consistent', False) 
                        for m in analysis.get('measurement_consistency', {}).values()
                    ),
                    'fastest_implementation': min(
                        analysis.get('performance_comparison', {}).items(),
                        key=lambda x: x[1],
                        default=(None, None)
                    )[0]
                }
            }
        }
        
        return report

    def _save_results(self, report):
        """Save results to files"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Save main report
        report_file = os.path.join(self.output_dir, 'unified_vmtest_report.json')
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        self._log(f"Report saved to: {report_file}")
        
        # Save individual results
        for lang, result in self.results.items():
            if result:
                individual_file = os.path.join(self.output_dir, f'vmtest_{lang}_result.json')
                with open(individual_file, 'w') as f:
                    json.dump(result, f, indent=2)
                    
        # Create summary text file
        summary_file = os.path.join(self.output_dir, 'summary.txt')
        with open(summary_file, 'w') as f:
            summary = report['unified_vmtest_report']['summary']
            analysis = report['unified_vmtest_report']['cross_language_analysis']
            
            f.write("VMtest Unified Results Summary\n")
            f.write("=" * 40 + "\n\n")
            
            f.write(f"Languages tested: {summary['total_languages_tested']}\n")
            f.write(f"Consensus VM detection: {summary['consensus_vm_detection']}\n")
            f.write(f"Detection confidence: {summary['detection_confidence']:.1%}\n")
            f.write(f"Measurements consistent: {summary['measurements_consistent']}\n")
            
            if summary['fastest_implementation']:
                f.write(f"Fastest implementation: {summary['fastest_implementation']}\n")
                
            f.write(f"\nDetection by language:\n")
            for lang, detected in analysis.get('vm_detection_by_language', {}).items():
                f.write(f"  {lang}: {'VM detected' if detected else 'Physical machine'}\n")
                
        self._log(f"Summary saved to: {summary_file}")
        return report_file

    def run_all_tests(self):
        """Run VMtest across all available language implementations"""
        self._log("Starting unified VMtest execution")
        self._log(f"Output directory: {self.output_dir}")
        self._log(f"Iterations per test: {self.iterations}")
        
        # Check dependencies
        available_deps = self._check_dependencies()
        
        if not available_deps:
            self._log("No language implementations available!", 'ERROR')
            return None
            
        # Run each implementation
        for lang in ['c', 'python', 'nodejs', 'ruby']:
            if lang in available_deps:
                result = self._run_implementation(lang, available_deps)
                if result:
                    self.results[lang] = result
                    
        if not self.results:
            self._log("No implementations completed successfully!", 'ERROR')
            return None
            
        # Analyze results
        self._log("Performing cross-language analysis...")
        analysis = self._analyze_cross_language_results()
        
        # Generate and save report
        report = self._generate_report(analysis)
        report_file = self._save_results(report)
        
        # Print summary
        summary = report['unified_vmtest_report']['summary']
        self._log("=" * 50)
        self._log("UNIFIED VMTEST SUMMARY")
        self._log("=" * 50)
        self._log(f"Languages tested: {summary['total_languages_tested']}")
        self._log(f"Consensus: {'VM DETECTED' if summary['consensus_vm_detection'] else 'PHYSICAL MACHINE'}")
        self._log(f"Confidence: {summary['detection_confidence']:.1%}")
        
        return report_file

def create_static_bundle():
    """Create a static bundle with all implementations and runner"""
    bundle_dir = "vmtest_bundle"
    if os.path.exists(bundle_dir):
        shutil.rmtree(bundle_dir)
    os.makedirs(bundle_dir)
    
    # Files to include in bundle
    files_to_bundle = [
        'vmtest.c',
        'vmtest.py', 
        'vmtest.js',
        'vmtest.rb',
        'unified_runner.py',
        'README.md'
    ]
    
    print("Creating static bundle...")
    
    # Copy existing files
    for filename in files_to_bundle:
        if os.path.exists(filename):
            shutil.copy2(filename, bundle_dir)
            print(f"Added {filename}")
        else:
            print(f"Warning: {filename} not found")
    
    # Create run script
    run_script = os.path.join(bundle_dir, 'run_vmtest.py')
    with open(run_script, 'w') as f:
        f.write("""#!/usr/bin/env python3
# Unified VMtest Runner - Bundled Version
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unified_runner import UnifiedVMTestRunner, create_static_bundle
import argparse

def main():
    parser = argparse.ArgumentParser(description='Run VMtest across multiple languages')
    parser.add_argument('--iterations', '-i', type=int, default=1000, 
                        help='Number of iterations per test (default: 1000)')
    parser.add_argument('--output', '-o', type=str, 
                        help='Output directory for results')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    runner = UnifiedVMTestRunner(
        iterations=args.iterations,
        output_dir=args.output,
        verbose=args.verbose
    )
    
    report_file = runner.run_all_tests()
    if report_file:
        print(f"\\nComplete report available at: {report_file}")
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
""")
    
    # Make run script executable
    os.chmod(run_script, 0o755)
    
    # Create bundle README
    bundle_readme = os.path.join(bundle_dir, 'BUNDLE_README.md')
    with open(bundle_readme, 'w') as f:
        f.write("""# VMtest Bundle

This bundle contains VMtest implementations in multiple languages and a unified runner.

## Contents

- `vmtest.c` - C implementation
- `vmtest.py` - Python implementation  
- `vmtest.js` - Node.js implementation
- `vmtest.rb` - Ruby implementation
- `unified_runner.py` - Unified test runner
- `run_vmtest.py` - Simple execution script

## Quick Start

```bash
# Run all available implementations
python3 run_vmtest.py

# Run with custom iterations
python3 run_vmtest.py --iterations 2000

# Run with verbose output
python3 run_vmtest.py --verbose

# Specify output directory
python3 run_vmtest.py --output ./results
```

## Requirements

Install the languages you want to test:

- **C**: GCC compiler
- **Python**: Python 3.6+
- **Node.js**: Node.js 12+
- **Ruby**: Ruby 2.5+

The runner will automatically detect available languages and skip unavailable ones.

## Individual Execution

You can also run implementations individually:

```bash
# C (compile first)
gcc -o vmtest vmtest.c -lpthread -lm -O2
./vmtest

# Python
python3 vmtest.py 1000

# Node.js
node vmtest.js 1000

# Ruby
ruby vmtest.rb 1000
```

## Output

The unified runner produces:
- `unified_vmtest_report.json` - Complete results and analysis
- `vmtest_<lang>_result.json` - Individual language results
- `summary.txt` - Human-readable summary

## Cross-Language Analysis

The unified runner provides:
- Consensus VM detection across languages
- Measurement consistency analysis
- Performance comparison
- Statistical validation

This helps validate results and identify potential implementation-specific issues.
""")
    
    # Create ZIP archive
    zip_filename = f"vmtest_bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(bundle_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, bundle_dir)
                zipf.write(file_path, arcname)
    
    print(f"Bundle created: {bundle_dir}/")
    print(f"Archive created: {zip_filename}")
    
    return bundle_dir, zip_filename

def main():
    parser = argparse.ArgumentParser(description='Unified VMtest Runner')
    parser.add_argument('--iterations', '-i', type=int, default=1000,
                        help='Number of iterations per test (default: 1000)')
    parser.add_argument('--output', '-o', type=str,
                        help='Output directory for results')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--bundle', action='store_true',
                        help='Create static bundle instead of running tests')
    
    args = parser.parse_args()
    
    if args.bundle:
        create_static_bundle()
        return
    
    runner = UnifiedVMTestRunner(
        iterations=args.iterations,
        output_dir=args.output,
        verbose=args.verbose
    )
    
    report_file = runner.run_all_tests()
    if report_file:
        print(f"\nComplete report available at: {report_file}")
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
