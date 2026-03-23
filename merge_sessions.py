import argparse
import sys


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file {path}: {e}", file=sys.stderr)
        sys.exit(1)


def sample_text(text: str, sample_len: int = 20) -> str:
    if len(text) <= sample_len * 2:
        return text
    prefix = text[:sample_len]
    suffix = text[-sample_len:]
    return f"{prefix}...[{len(text)} chars]...{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge two session file contents by reading both files.")
    parser.add_argument("file1", help="First input file")
    parser.add_argument("file2", help="Second input file")

    args = parser.parse_args()

    content1 = read_file(args.file1)
    content2 = read_file(args.file2)

    print("=== CONTENT FROM", args.file1, "===")
    print(sample_text(content1))
    print("\n=== CONTENT FROM", args.file2, "===")
    print(sample_text(content2))


if __name__ == "__main__":
    main()
