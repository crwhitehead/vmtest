#!/usr/bin/env python3

"""
Integrated VMtest Portable Builder
Combines static_builder.py and unified_runner.py into a single portable solution.
Creates a PyInstaller executable that contains all portable language implementations.
"""

import os
import sys
import shutil
import subprocess
import tempfile
import platform
import urllib.request
import tarfile
import zipfile
import json
from pathlib import Path
from datetime import datetime
import argparse
import time

class IntegratedPortableBuilder:
    def __init__(self, output_dir="vmtest_complete_portable"):
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vmtest_integrated_build_"))
        self.platform = platform.system().lower()
        self.arch = self._normalize_arch(platform.machine().lower())
        
        # Configuration
        self.node_version = "18.17.0"
        self.build_artifacts = {}
        self.build_start_time = time.time()
        
        print(f"🏗️  VMtest Integrated Portable Builder")
        print(f"Platform: {self.platform}-{self.arch}")
        print(f"Output: {self.output_dir}")
        print(f"Temp: {self.temp_dir}")

    def _normalize_arch(self, arch):
        """Normalize architecture names"""
        arch_map = {
            'x86_64': 'x64', 'amd64': 'x64', 'x64': 'x64',
            'i386': 'x32', 'i686': 'x32', 'x86': 'x32',
            'arm64': 'arm64', 'aarch64': 'arm64',
            'armv7l': 'arm32', 'arm': 'arm32'
        }
        return arch_map.get(arch, arch)

    def log(self, message, level="INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {message}")

    def run_command(self, cmd, cwd=None):
        """Run command and return success"""
        try:
            if isinstance(cmd, str):
                cmd = cmd.split()
            
            result = subprocess.run(
                cmd, 
                cwd=cwd or self.temp_dir,
                capture_output=True, 
                text=True, 
                timeout=300
            )
            
            if result.returncode == 0:
                return True
            else:
                self.log(f"Command failed: {' '.join(cmd)}", "ERROR")
                if result.stderr:
                    self.log(f"Error: {result.stderr}", "ERROR")
                return False
                
        except subprocess.TimeoutExpired:
            self.log(f"Command timed out: {' '.join(cmd)}", "ERROR")
            return False
        except Exception as e:
            self.log(f"Command error: {e}", "ERROR")
            return False

    def build_c_executable(self):
        """Build C executable"""
        self.log("🔨 Building C executable...")
        
        if not Path("vmtest.c").exists():
            self.log("⚠️  vmtest.c not found - skipping C build")
            return None
        
        # Copy source
        shutil.copy2("vmtest.c", self.temp_dir / "vmtest.c")
        
        # Compile
        output_name = "vmtest" + (".exe" if self.platform == "windows" else "")
        compile_args = ["gcc", "-static", "-O2", "vmtest.c", "-o", output_name, "-lpthread", "-lm"]
        
        if self.platform == "linux":
            compile_args.append("-lrt")
        
        result = self.run_command(compile_args)
        if not result:
            # Try without static linking
            self.log("Trying compilation without static linking...")
            compile_args = [arg for arg in compile_args if arg != "-static"]
            result = self.run_command(compile_args)
        
        if result:
            executable_path = self.temp_dir / output_name
            if executable_path.exists():
                self.build_artifacts['c'] = executable_path
                self.log(f"✅ C executable: {executable_path}")
                return executable_path
        
        self.log("❌ C build failed")
        return None

    def build_python_executable(self):
        """Build Python executable with PyInstaller"""
        self.log("🐍 Building Python executable...")
        
        if not Path("vmtest.py").exists():
            self.log("⚠️  vmtest.py not found - skipping Python build")
            return None
        
        # Install PyInstaller if needed
        try:
            subprocess.run([sys.executable, "-c", "import PyInstaller"], 
                         capture_output=True, check=True)
        except:
            self.log("📦 Installing PyInstaller...")
            result = self.run_command([
                sys.executable, "-m", "pip", "install", "pyinstaller"
            ])
            if not result:
                self.log("❌ Failed to install PyInstaller")
                return None
        
        # Copy source
        shutil.copy2("vmtest.py", self.temp_dir / "vmtest.py")
        
        # Build
        exe_name = "vmtest_python" + (".exe" if self.platform == "windows" else "")
        
        build_args = [
            "pyinstaller",
            "--onefile",
            "--clean",
            "--noconfirm",
            "--name", exe_name.replace('.exe', ''),
            "--distpath", str(self.temp_dir),
            "vmtest.py"
        ]
        
        result = self.run_command(build_args)
        if result:
            exe_path = self.temp_dir / exe_name
            if exe_path.exists():
                self.build_artifacts['python'] = exe_path
                self.log(f"✅ Python executable ready")
                return exe_path
        
        self.log("❌ Python build failed")
        return None

    def download_nodejs(self):
        """Download portable Node.js"""
        self.log("📦 Getting portable Node.js...")
        
        version = self.node_version
        node_dir = self.temp_dir / "nodejs"
        node_dir.mkdir(exist_ok=True)
        
        # Determine download URL
        if self.platform == "windows":
            if self.arch == "x64":
                url = f"https://nodejs.org/dist/v{version}/node-v{version}-win-x64.zip"
                archive_name = f"node-v{version}-win-x64.zip"
                binary_path = f"node-v{version}-win-x64/node.exe"
            else:
                url = f"https://nodejs.org/dist/v{version}/node-v{version}-win-x86.zip"
                archive_name = f"node-v{version}-win-x86.zip"
                binary_path = f"node-v{version}-win-x86/node.exe"
        elif self.platform == "darwin":
            url = f"https://nodejs.org/dist/v{version}/node-v{version}-darwin-x64.tar.gz"
            archive_name = f"node-v{version}-darwin-x64.tar.gz"
            binary_path = f"node-v{version}-darwin-x64/bin/node"
        else:  # Linux
            if self.arch == "x64":
                url = f"https://nodejs.org/dist/v{version}/node-v{version}-linux-x64.tar.xz"
                archive_name = f"node-v{version}-linux-x64.tar.xz"
                binary_path = f"node-v{version}-linux-x64/bin/node"
            else:
                url = f"https://nodejs.org/dist/v{version}/node-v{version}-linux-x86.tar.xz"
                archive_name = f"node-v{version}-linux-x86.tar.xz"
                binary_path = f"node-v{version}-linux-x86/bin/node"
        
        try:
            self.log(f"Downloading from: {url}")
            archive_path = node_dir / archive_name
            urllib.request.urlretrieve(url, archive_path)
            
            # Extract archive
            if archive_name.endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(node_dir)
            elif archive_name.endswith('.tar.gz'):
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(node_dir)
            elif archive_name.endswith('.tar.xz'):
                with tarfile.open(archive_path, 'r:xz') as tar_ref:
                    tar_ref.extractall(node_dir)
            
            # Copy binary to temp directory
            source_binary = node_dir / binary_path
            dest_binary = self.temp_dir / ("node.exe" if self.platform == "windows" else "node")
            
            if source_binary.exists():
                shutil.copy2(source_binary, dest_binary)
                os.chmod(dest_binary, 0o755)
                
                # Also copy vmtest.js if it exists
                if Path("vmtest.js").exists():
                    shutil.copy2("vmtest.js", self.temp_dir / "vmtest.js")
                
                self.build_artifacts['nodejs'] = dest_binary
                self.log(f"✅ Node.js ready: {dest_binary}")
                return dest_binary
            else:
                self.log(f"Node.js binary not found at: {source_binary}")
                return None
                
        except Exception as e:
            self.log(f"Node.js download failed: {e}")
            return None

    def create_ruby_wrapper(self):
        """Create Ruby wrapper (since portable Ruby is complex)"""
        self.log("💎 Creating Ruby wrapper...")
        
        if not Path("vmtest.rb").exists():
            self.log("⚠️  vmtest.rb not found - skipping Ruby")
            return None
        
        # Copy Ruby source
        shutil.copy2("vmtest.rb", self.temp_dir / "vmtest.rb")
        
        # Create wrapper script
        if self.platform == "windows":
            wrapper_name = "vmtest_ruby.bat"
            wrapper_content = """@echo off
if not exist ruby.exe (
    echo Ruby not found. Please install Ruby.
    exit /b 1
)
ruby "%~dp0vmtest.rb" %*
"""
        else:
            wrapper_name = "vmtest_ruby"
            wrapper_content = """#!/bin/bash
if ! command -v ruby >/dev/null 2>&1; then
    echo "Ruby not found. Please install Ruby."
    exit 1
fi
ruby "$(dirname "$0")/vmtest.rb" "$@"
"""
        
        wrapper_path = self.temp_dir / wrapper_name
        with open(wrapper_path, 'w') as f:
            f.write(wrapper_content)
        
        if self.platform != "windows":
            os.chmod(wrapper_path, 0o755)
        
        self.build_artifacts['ruby'] = wrapper_path
        self.log(f"✅ Ruby wrapper ready")
        return wrapper_path

    def create_unified_runner_executable(self):
        """Create the unified runner as a PyInstaller executable"""
        self.log("🚀 Building unified runner executable...")
        
        # Create the portable unified runner script
        runner_script = self.temp_dir / "portable_unified_runner.py"
        
        # Read the portable_unified_runner.py content from the artifact we created
        runner_content = open("portable_unified_runner.py", "r").read()
        
        with open(runner_script, 'w') as f:
            f.write(runner_content)
        
        # Create PyInstaller spec
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

# Collect all built artifacts
datas = []

# Add source files
source_files = ['vmtest.c', 'vmtest.py', 'vmtest.js', 'vmtest.rb']
for src in source_files:
    if Path(src).exists():
        datas.append((src, '.'))

# Add built executables
artifacts = {repr(dict((k, str(v)) for k, v in self.build_artifacts.items()))}
for name, path in artifacts.items():
    if Path(path).exists():
        # Get the filename for the destination
        dest_name = Path(path).name
        datas.append((str(path), '.'))

a = Analysis(
    ['{runner_script}'],
    pathex=['{self.temp_dir}'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'json', 'os', 'sys', 'time', 'subprocess', 'platform', 
        'shutil', 'tempfile', 'datetime', 'pathlib', 'argparse'
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='vmtest_portable',
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
'''
        
        spec_file = self.temp_dir / "vmtest_portable.spec"
        with open(spec_file, 'w') as f:
            f.write(spec_content)
        
        # Build with PyInstaller
        self.log("Running PyInstaller...")
        result = self.run_command([
            'pyinstaller',
            '--clean',
            '--noconfirm',
            str(spec_file)
        ])
        
        if result:
            # Find the built executable
            exe_name = "vmtest_portable" + (".exe" if self.platform == "windows" else "")
            exe_path = self.temp_dir / "dist" / exe_name
            
            if exe_path.exists():
                self.log(f"✅ Unified executable created: {exe_path}")
                return exe_path
            else:
                self.log("❌ Executable not found after build")
                return None
        else:
            self.log("❌ PyInstaller build failed")
            return None

    def create_final_package(self, unified_exe):
        """Create final package"""
        self.log("📦 Creating final package...")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy the unified executable
        final_exe_name = "vmtest_portable" + (".exe" if self.platform == "windows" else "")
        final_exe_path = self.output_dir / final_exe_name
        shutil.copy2(unified_exe, final_exe_path)
        
        if self.platform != "windows":
            os.chmod(final_exe_path, 0o755)
        
        # Create README
        readme_content = f"""# VMtest Portable Suite

This is a complete, self-contained VMtest suite that includes:

## What's Inside
- C implementation (statically compiled)
- Python implementation (PyInstaller executable)
- Node.js implementation (embedded runtime + script)
- Ruby implementation (wrapper script)
- Unified runner that orchestrates all implementations

## Usage

Simply run the executable:

```bash
# Basic usage
./{final_exe_name}

# With custom iterations
./{final_exe_name} --iterations 2000

# Verbose output
./{final_exe_name} --verbose

# Custom output directory
./{final_exe_name} --output ./my_results
```

## Output

The tool will:
1. Detect which implementations are available
2. Run all available implementations
3. Cross-validate results between languages
4. Generate comprehensive JSON and text reports
5. Provide VM detection consensus

## Features

- **Zero Dependencies**: Everything is self-contained
- **Cross-Platform**: Works on Windows, Linux, and macOS
- **Multiple Languages**: Tests VM detection across different runtime environments
- **Portable**: Single executable, no installation required
- **Comprehensive**: Detailed analysis and reporting

## Built Information

- Build Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Platform: {platform.platform()}
- Included Implementations: {list(self.build_artifacts.keys())}

## Notes

- If Ruby is not installed on the target system, Ruby tests will be skipped
- All other implementations are fully self-contained
- Results are saved in JSON format for further analysis
- The tool automatically handles platform-specific differences

Enjoy your portable VM detection toolkit! 🚀
"""
        
        readme_path = self.output_dir / "README.md"
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        
        # Create run script for convenience
        if self.platform == "windows":
            run_script = self.output_dir / "run.bat"
            with open(run_script, 'w') as f:
                f.write(f'@echo off\n"{final_exe_name}" %*\npause\n')
        else:
            run_script = self.output_dir / "run.sh"
            with open(run_script, 'w') as f:
                f.write(f'#!/bin/bash\n"./{final_exe_name}" "$@"\n')
            os.chmod(run_script, 0o755)
        
        self.log(f"✅ Package created: {self.output_dir}")
        return self.output_dir

    def build_all(self):
        """Build everything"""
        self.log("🚀 Starting integrated build process...")
        
        try:
            # Step 1: Build individual language implementations
            self.log("Phase 1: Building language implementations...")
            self.build_c_executable()
            self.build_python_executable()
            self.download_nodejs()
            self.create_ruby_wrapper()
            
            if not self.build_artifacts:
                self.log("❌ No implementations built successfully!")
                return None
            
            self.log(f"Built implementations: {list(self.build_artifacts.keys())}")
            
            # Step 2: Build unified runner executable
            self.log("Phase 2: Creating unified portable executable...")
            unified_exe = self.create_unified_runner_executable()
            
            if not unified_exe:
                self.log("❌ Failed to create unified executable!")
                return None
            
            # Step 3: Create final package
            self.log("Phase 3: Creating final package...")
            final_package = self.create_final_package(unified_exe)
            
            # Calculate build time
            build_time = time.time() - self.build_start_time
            
            # Success summary
            self.log("=" * 60)
            self.log("🎉 BUILD SUCCESSFUL!")
            self.log("=" * 60)
            self.log(f"⏱️  Build time: {build_time:.1f} seconds")
            self.log(f"📁 Package: {final_package}")
            self.log(f"🚀 Executable: {final_package / ('vmtest_portable' + ('.exe' if self.platform == 'windows' else ''))}")
            self.log("")
            self.log("Built components:")
            for name in self.build_artifacts:
                self.log(f"  ✅ {name.upper()}")
            self.log("")
            self.log("🚀 TO USE:")
            self.log(f"  cd {final_package.name}")
            self.log(f"  ./vmtest_portable{'(.exe' if self.platform == 'windows' else ''}")
            self.log("")
            self.log("💡 This is a completely portable, self-contained VM detection suite!")
            
            return final_package
            
        except Exception as e:
            self.log(f"❌ Build failed: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # Cleanup temp directory
            try:
                shutil.rmtree(self.temp_dir)
                self.log(f"🧹 Cleaned up temp directory: {self.temp_dir}")
            except:
                pass


def main():
    parser = argparse.ArgumentParser(
        description='Integrated VMtest Portable Builder - Creates a single executable containing all implementations'
    )
    parser.add_argument('--output', '-o', default='vmtest_complete_portable',
                        help='Output directory (default: vmtest_complete_portable)')
    parser.add_argument('--clean', action='store_true',
                        help='Clean output directory first')
    
    args = parser.parse_args()
    
    if args.clean and Path(args.output).exists():
        print(f"🧹 Cleaning {args.output}...")
        shutil.rmtree(args.output)
    
    try:
        builder = IntegratedPortableBuilder(args.output)
        package_dir = builder.build_all()
        
        if package_dir:
            print(f"\n🎉 Success! Your complete portable VMtest suite is ready!")
            print(f"📍 Location: {package_dir}")
            exe_name = "vmtest_portable" + (".exe" if platform.system() == "Windows" else "")
            print(f"🚀 Run with: cd {package_dir.name} && ./{exe_name}")
            return 0
        else:
            print("❌ Build failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n🛑 Build interrupted by user")
        return 1
    except Exception as e:
        print(f"💥 Build error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
