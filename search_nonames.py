import pandas as pd
import asyncio
from test import BelgianCompanyScraper
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_excel_file(file_path: str):
    df = pd.read_excel(file_path)
    
    filtered_df = df[
        (df['first_name'].isna() | (df['first_name'] == '')) &
        (df['last_name'].isna() | (df['last_name'] == '')) &
        df['person_company_number'].notna() &
        (df['person_company_number'] != '')
    ]
    
    unique_companies = filtered_df.drop_duplicates(subset=['person_company_number'])
    company_numbers = unique_companies['person_company_number'].tolist()
    logger.info(f"Found {len(company_numbers)} unique companies to process")

    temp_file = "temp_company_numbers.txt"
    with open(temp_file, 'w') as f:
        for number in company_numbers:
            f.write(f"{number}\n")
    try:
        scraper = BelgianCompanyScraper()
        await scraper.search_kbo_numbers(temp_file)
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

async def main():
    excel_file_path = "company_functions.xlsx"
    await process_excel_file(excel_file_path)

    # Need to add a save to the existing companies with the names

if __name__ == "__main__":
    asyncio.run(main())