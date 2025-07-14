import argparse
import importlib

def main():
    parser = argparse.ArgumentParser(description="SHADOW AI Trading System")
    parser.add_argument('module', choices=['scale', 'grim', 'flare', 'phantom', 'spectre', 'veil', 'echo'], help='The module to run')
    args = parser.parse_args()

    try:
        module = importlib.import_module(f"src.{args.module}.{args.module}")
        module.main()
    except ImportError as e:
        print(f"Error importing module {args.module}: {e}")
    except AttributeError:
        print(f"Module {args.module} does not have a main() function.")

if __name__ == "__main__":
    main()
