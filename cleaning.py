import pandas as pd
from datetime import datetime

def remove_syndicus_entries(input_file: str):
    df = pd.read_excel(input_file)

    original_count = len(df)

    df = df[~df['function_title'].str.contains('Syndicus', case=False, na=False)]
    
    removed_count = original_count - len(df)
    
    output_file = f"company_functions_no_syndicus.xlsx"
    
    df.to_excel(output_file, index=True)
    
    print(f"Original rows: {original_count}")
    print(f"Rows removed: {removed_count}")
    print(f"Remaining rows: {len(df)}")
    print(f"Saved to: {output_file}")

if __name__ == "__main__":
    remove_syndicus_entries("company_functions.xlsx") 