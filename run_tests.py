#!/usr/bin/env python3
"""
Test runner for the RAMSES RF Prometheus Exporter

This script runs all tests for the exporter module.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ SUCCESS")
        if result.stdout:
            print("Output:")
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("✗ FAILED")
        print(f"Exit code: {e.returncode}")
        if e.stdout:
            print("Stdout:")
            print(e.stdout)
        if e.stderr:
            print("Stderr:")
            print(e.stderr)
        return False

def main():
    """Main test runner function."""
    print("RAMSES RF Prometheus Exporter - Test Runner")
    print("=" * 50)
    
    # Get the project root directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Test commands to run
    tests = [
        (["python", "-m", "pytest", "tests/", "-v"], "Unit Tests"),
        (["python", "-m", "pylint", "honeywell_radio_exporter/"], "Pylint"),
        (["python", "-m", "flake8", "honeywell_radio_exporter/"], "Flake8"),
        (["python", "-m", "black", "--check", "honeywell_radio_exporter/"], "Black Format Check"),
        (["python", "-m", "isort", "--check-only", "honeywell_radio_exporter/"], "Import Sort Check"),
        (["python", "-m", "mypy", "honeywell_radio_exporter/"], "Type Checking"),
        (["python", "-m", "bandit", "-r", "honeywell_radio_exporter/"], "Security Check"),
    ]
    
    # Run all tests
    results = []
    for cmd, description in tests:
        success = run_command(cmd, description)
        results.append((description, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    
    passed = 0
    failed = 0
    
    for description, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {description}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\nSome tests failed. Please fix the issues before proceeding.")
        sys.exit(1)
    else:
        print("\nAll tests passed! ✓")

if __name__ == "__main__":
    import os
    main()
