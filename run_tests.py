import unittest
import sys
import os
import subprocess

def run_all_tests():
    test_files = [
        os.path.join('tests', 'test_server.py'),
        os.path.join('tests', 'test_client.py')
    ]
    
    success = True
    for test_file in test_files:
        print(f"\n{'='*60}\nRunning {test_file}\n{'='*60}")
        # Run each test in a separate process to avoid import collisions
        result = subprocess.run([sys.executable, "-m", "unittest", test_file])
        if result.returncode != 0:
            success = False
            
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    run_all_tests()
