#!/bin/bash
# Minimal VMtest Build Script
# Target: x86_64 Linux only
# Zero configuration, maximum reliability

set -e

BUILD_DIR="vmtest_build"
ARCHIVE="vmtest-linux-x86_64.tar.gz"

echo "VMtest Minimal Builder"
echo "====================="

# Clean build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Build C (static if possible)
echo "Building C..."
if [ -f "vmtest.c" ]; then
    gcc -static -O2 vmtest.c -o "$BUILD_DIR/vmtest" -lpthread -lm -lrt 2>/dev/null || \
    gcc -O2 vmtest.c -o "$BUILD_DIR/vmtest" -lpthread -lm -lrt
    echo "✓ C executable"
fi

# Build Python
echo "Building Python..."
if [ -f "vmtest.py" ]; then
    if command -v pyinstaller >/dev/null 2>&1; then
        pyinstaller --onefile --name vmtest_python vmtest.py --distpath "$BUILD_DIR" --clean >/dev/null 2>&1
        rm -rf build dist *.spec
        echo "✓ Python standalone"
    else
        cp vmtest.py "$BUILD_DIR/"
        echo '#!/bin/bash' > "$BUILD_DIR/vmtest_python"
        echo 'exec python3 "$(dirname "$0")/vmtest.py" "$@"' >> "$BUILD_DIR/vmtest_python"
        chmod +x "$BUILD_DIR/vmtest_python"
        echo "✓ Python wrapper"
    fi
fi

# Build Node.js
echo "Building Node.js..."
if [ -f "vmtest.js" ]; then
    # Download Node.js binary
    NODE_URL="https://nodejs.org/dist/v18.17.0/node-v18.17.0-linux-x64.tar.xz"
    if curl -s "$NODE_URL" | tar -xJ -C /tmp 2>/dev/null; then
        cp /tmp/node-v18.17.0-linux-x64/bin/node "$BUILD_DIR/"
        cp vmtest.js "$BUILD_DIR/"
        rm -rf /tmp/node-v18.17.0-linux-x64
        echo "✓ Node.js embedded"
    else
        echo "✗ Node.js download failed"
    fi
fi

# Build Ruby (FIXED - using most reliable method)
echo "Building Ruby..."
if [ -f "vmtest.rb" ]; then
    echo "  Found vmtest.rb"
    
    # Use Traveling Ruby - most reliable portable Ruby solution
    RUBY_URL="http://d6r77u77i8pq3.cloudfront.net/releases/traveling-ruby-20150715-2.2.2-linux-x86_64.tar.gz"
    
    echo "  Downloading Traveling Ruby..."
    if curl -s "$RUBY_URL" -o /tmp/traveling-ruby.tar.gz; then
        echo "  ✓ Downloaded successfully"
        
        echo "  Extracting..."
        if tar -xzf /tmp/traveling-ruby.tar.gz -C "$BUILD_DIR"; then
            echo "  ✓ Extracted successfully"
            
            # Check if Ruby files are directly in BUILD_DIR or in a subdirectory
            if [ -d "$BUILD_DIR/bin" ] && [ -d "$BUILD_DIR/lib" ]; then
                # Ruby extracted directly to BUILD_DIR
                echo "  ✓ Ruby runtime ready (extracted directly)"
                
                # Copy our script
                cp vmtest.rb "$BUILD_DIR/"
                echo "  ✓ Copied vmtest.rb"
                
                # Create launcher that uses the Ruby in the same directory
                cat > "$BUILD_DIR/vmtest_ruby" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$DIR/bin:$PATH"
exec "$DIR/bin/ruby" "$DIR/vmtest.rb" "$@"
EOF
                chmod +x "$BUILD_DIR/vmtest_ruby"
                echo "  ✓ Created launcher"
                
                # Cleanup
                rm -f /tmp/traveling-ruby.tar.gz
                echo "✓ Ruby portable"
            else
                # Look for traveling-ruby subdirectory
                RUBY_DIR=$(find "$BUILD_DIR" -name "traveling-ruby-*" -type d | head -1)
                if [ -n "$RUBY_DIR" ]; then
                    mv "$RUBY_DIR" "$BUILD_DIR/ruby"
                    echo "  ✓ Renamed to ruby/"
                    
                    # Copy our script
                    cp vmtest.rb "$BUILD_DIR/"
                    echo "  ✓ Copied vmtest.rb"
                    
                    # Create launcher
                    cat > "$BUILD_DIR/vmtest_ruby" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$DIR/ruby/bin:$PATH"
exec "$DIR/ruby/bin/ruby" "$DIR/vmtest.rb" "$@"
EOF
                    chmod +x "$BUILD_DIR/vmtest_ruby"
                    echo "  ✓ Created launcher"
                    
                    # Cleanup
                    rm -f /tmp/traveling-ruby.tar.gz
                    echo "✓ Ruby portable"
                else
                    echo "  ✗ No traveling-ruby directory found after extraction"
                    echo "  Available directories:"
                    ls -la "$BUILD_DIR/"
                    echo "  Falling back to wrapper..."
                    # Fallback to wrapper
                    cp vmtest.rb "$BUILD_DIR/"
                    cat > "$BUILD_DIR/vmtest_ruby" << 'EOF'
#!/bin/bash
ruby "$(dirname "$0")/vmtest.rb" "$@"
EOF
                    chmod +x "$BUILD_DIR/vmtest_ruby"
                    echo "✓ Ruby wrapper"
                fi
            fi
        else
            echo "  ✗ Extraction failed"
            echo "  Error details:"
            tar -tzf /tmp/traveling-ruby.tar.gz | head -5
            rm -f /tmp/traveling-ruby.tar.gz
            
            # Fallback to wrapper
            echo "  Falling back to wrapper..."
            cp vmtest.rb "$BUILD_DIR/"
            cat > "$BUILD_DIR/vmtest_ruby" << 'EOF'
#!/bin/bash
ruby "$(dirname "$0")/vmtest.rb" "$@"
EOF
            chmod +x "$BUILD_DIR/vmtest_ruby"
            echo "✓ Ruby wrapper"
        fi
    else
        echo "  ✗ Download failed"
        echo "  Trying wget as fallback..."
        
        if command -v wget >/dev/null 2>&1; then
            if wget -q "$RUBY_URL" -O /tmp/traveling-ruby.tar.gz; then
                echo "  ✓ Downloaded with wget"
                # Repeat extraction logic
                if tar -xzf /tmp/traveling-ruby.tar.gz -C "$BUILD_DIR"; then
                    RUBY_DIR=$(find "$BUILD_DIR" -name "traveling-ruby-*" -type d | head -1)
                    if [ -n "$RUBY_DIR" ]; then
                        mv "$RUBY_DIR" "$BUILD_DIR/ruby"
                        cp vmtest.rb "$BUILD_DIR/"
                        cat > "$BUILD_DIR/vmtest_ruby" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$DIR/ruby/bin:$PATH"
exec "$DIR/ruby/bin/ruby" "$DIR/vmtest.rb" "$@"
EOF
                        chmod +x "$BUILD_DIR/vmtest_ruby"
                        rm -f /tmp/traveling-ruby.tar.gz
                        echo "✓ Ruby portable (via wget)"
                    else
                        echo "  ✗ Directory not found after wget extraction"
                        # Fallback to wrapper
                        cp vmtest.rb "$BUILD_DIR/"
                        cat > "$BUILD_DIR/vmtest_ruby" << 'EOF'
#!/bin/bash
ruby "$(dirname "$0")/vmtest.rb" "$@"
EOF
                        chmod +x "$BUILD_DIR/vmtest_ruby"
                        echo "✓ Ruby wrapper"
                    fi
                else
                    echo "  ✗ Extraction failed with wget"
                    rm -f /tmp/traveling-ruby.tar.gz
                    # Fallback to wrapper
                    cp vmtest.rb "$BUILD_DIR/"
                    cat > "$BUILD_DIR/vmtest_ruby" << 'EOF'
#!/bin/bash
ruby "$(dirname "$0")/vmtest.rb" "$@"
EOF
                    chmod +x "$BUILD_DIR/vmtest_ruby"
                    echo "✓ Ruby wrapper"
                fi
            else
                echo "  ✗ wget also failed"
                # Fallback to wrapper
                cp vmtest.rb "$BUILD_DIR/"
                cat > "$BUILD_DIR/vmtest_ruby" << 'EOF'
#!/bin/bash
ruby "$(dirname "$0")/vmtest.rb" "$@"
EOF
                chmod +x "$BUILD_DIR/vmtest_ruby"
                echo "✓ Ruby wrapper"
            fi
        else
            echo "  ✗ No wget available"
            # Fallback to wrapper
            cp vmtest.rb "$BUILD_DIR/"
            cat > "$BUILD_DIR/vmtest_ruby" << 'EOF'
#!/bin/bash
ruby "$(dirname "$0")/vmtest.rb" "$@"
EOF
            chmod +x "$BUILD_DIR/vmtest_ruby"
            echo "✓ Ruby wrapper"
        fi
    fi
else
    echo "  ✗ vmtest.rb not found"
fi

# Create main runner
echo "Creating runner..."
cat > "$BUILD_DIR/run" << 'EOF'
#!/bin/bash
# VMtest Runner - Drop and Run

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITER="${1:-1000}"

echo "VMtest - VM Detection Suite"
echo "=========================="
echo "Platform: $(uname -s) $(uname -m)"
echo "Iterations: $ITER"
echo ""

# Run available implementations
[ -x "$DIR/vmtest" ] && echo "C:" && "$DIR/vmtest" --json
[ -x "$DIR/vmtest_python" ] && echo "Python:" && "$DIR/vmtest_python" "$ITER"
[ -x "$DIR/node" ] && [ -f "$DIR/vmtest.js" ] && echo "Node.js:" && "$DIR/node" "$DIR/vmtest.js" "$ITER"
[ -x "$DIR/vmtest_ruby" ] && echo "Ruby:" && "$DIR/vmtest_ruby" "$ITER"

echo ""
echo "Analysis complete."
EOF

chmod +x "$BUILD_DIR/run"

# Copy docs
for f in README.md LICENSE *.txt; do
    [ -f "$f" ] && cp "$f" "$BUILD_DIR/"
done

# Create archive
echo "Creating archive..."
tar -czf "$ARCHIVE" -C "$BUILD_DIR" .

echo ""
echo "✓ Build complete: $ARCHIVE"
echo "Size: $(du -h "$ARCHIVE" | cut -f1)"
echo ""
echo "Usage:"
echo "  tar -xzf $ARCHIVE"
echo "  ./run"
