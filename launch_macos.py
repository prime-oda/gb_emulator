#!/usr/bin/env python3
"""
macOS specific pygame launcher
"""

import os
import sys
import subprocess

def launch_with_proper_environment():
    """Launch the emulator with proper macOS environment"""
    
    # Set up environment variables for macOS
    env = os.environ.copy()
    env['SDL_VIDEO_WINDOW_POS'] = '400,400'
    env['SDL_VIDEO_CENTERED'] = '1'
    env['SDL_VIDEODRIVER'] = 'cocoa'
    env['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
    
    # Launch in a new process with proper environment
    cmd = [sys.executable, 'main.py', 'roms/test/cpu_instrs.gb']
    
    print("🚀 Launching Game Boy Emulator with macOS optimizations...")
    print("🎮 Window should appear in a few seconds...")
    
    # Launch the process
    process = subprocess.Popen(cmd, env=env)
    
    # Try to activate the window after a brief delay
    try:
        import time
        time.sleep(2)  # Wait for window to be created
        
        # Try to bring Python to front
        subprocess.run([
            'osascript', '-e',
            '''
            tell application "System Events"
                set pythonProcs to every process whose name contains "Python"
                if (count of pythonProcs) > 0 then
                    set frontmost of item 1 of pythonProcs to true
                end if
            end tell
            '''
        ], timeout=3)
        
        print("✅ Window activation attempted")
        
    except Exception as e:
        print(f"⚠️ Window activation failed: {e}")
    
    # Wait for process to complete
    try:
        process.wait()
    except KeyboardInterrupt:
        print("🛑 Interrupted by user")
        process.terminate()
        process.wait()

if __name__ == "__main__":
    launch_with_proper_environment()
