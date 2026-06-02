import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.stderr.write('pandas library is required. Install it via pip install pandas\n')
    sys.exit(1)

def convert_excel_to_csv(excel_path: Path) -> None:
    """Convert a single Excel file to CSV.

    Args:
        excel_path (Path): Path to the .xlsx file.
    """
    if not excel_path.is_file():
        print(f'Skipping {excel_path}: file does not exist.')
        return
    try:
        df = pd.read_excel(excel_path)
        csv_path = excel_path.with_suffix('.csv')
        df.to_csv(csv_path, index=False)
        print(f'Converted {excel_path} -> {csv_path}')
    except Exception as e:
        print(f'Error converting {excel_path}: {e}')

def main():
    # Expected arguments are Excel file paths after the script name.
    if len(sys.argv) < 2:
        print('Usage: python convert_excel_to_csv.py <excel1.xlsx> [<excel2.xlsx> ...]')
        sys.exit(0)
    for path_str in sys.argv[1:]:
        convert_excel_to_csv(Path(path_str))

if __name__ == '__main__':
    main()
