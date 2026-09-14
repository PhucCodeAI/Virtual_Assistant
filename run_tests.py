"""
File: run_tests.py
Script tập trung kích hoạt toàn bộ test suite nằm trong thư mục tests/
"""

import sys

import pytest


def main():
    print("\n==================================================")
    print("🚀 BẮT ĐẦU KIỂM THỬ TOÀN BỘ SERVICES VÀ REPOSITORIES")
    print("==================================================\n")

    # Kích hoạt pytest quét và thực thi toàn bộ test trong folder 'tests'
    exit_code = pytest.main(["-v", "-s", "tests"])

    if exit_code == 0:
        print("\n✅ TOÀN BỘ HỆ THỐNG TEST ĐÃ PASS!")
    else:
        print(f"\n❌ CÓ LỖI XẢY RA! Exit code: {exit_code}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
