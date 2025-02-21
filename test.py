import asyncio
import json
import logging
from typing import List, Dict, Any
import pandas as pd
from playwright.async_api import async_playwright, Browser, Page
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BelgianCompanyScraper:
    def __init__(self):
        self.kbo_base_url = "https://kbopub.economie.fgov.be/kbopub"
        self.kbo_search_url = f"{self.kbo_base_url}/zoeknaamfonetischform.html?lang=en"

        self.opencorporates_base_url = "https://opencorporates.com"
        self.opencorporates_url = "https://opencorporates.com/companies/be?action=search_companies&branch=false&commit=Go&controller=searches&inactive=false&mode=best_fields&nonprofit=&order=&q=&search_fields%5B%5D=name&type=companies&utf8=%E2%9C%93"

        self.linkedin_url = "https://www.linkedin.com/company/"
        
        self.company_sizes = ["2-10", "11-50"]
        self.languages = ["en", "nl", "dutch", "english"]

    async def _setup_browser(self) -> Browser:
        """Setup playwright browser with stealth mode"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        return browser
    
    async def scrape_opencorporates(self) -> List[str]:
        """Sign in to opencorporates"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(self.opencorporates_url)

        await page.wait_for_selector('#user_email')
        await page.fill('#user_email', 'matthieu.olislaegers@wedoit.be')
        await page.fill('#user_password', 'Test1234!')
        await page.click('button[type="submit"]')

        await page.wait_for_url("https://opencorporates.com/?logged_in")

        await page.goto(self.opencorporates_url)

        """Scrape companies from opencorporates"""
        await page.goto(self.opencorporates_url)
        
        company_numbers = set()
        i = 0
        
        try:
            while True:
                # 2 pages for testing
                if i >= 2:
                    break

                await page.wait_for_selector('#results')

                links = await page.query_selector_all('.company_search_result')
                logger.info(f"Found {len(links)} links on current page")
                
                for link in links:
                    href = await link.get_attribute('href')
                    if href:
                        match = re.search(r'/companies/be/(\d+)', href)
                        if match:
                            company_numbers.add(match.group(1))
                
                logger.info(f"Total unique company numbers so far: {len(company_numbers)}")
                
                # print(company_numbers)

                next_button = await page.query_selector('.next_page [href]')
                if not next_button:
                    break
                    
                await next_button.click()
                await page.wait_for_load_state('networkidle')

                i += 1
        finally:
            await browser.close()
            await playwright.stop()
        
        return company_numbers
    
    async def search_kbo_numbers(self, filename: str):
        """Search company numbers on KBO website"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        
        try:
            page = await browser.new_page()
            await page.goto(self.kbo_base_url + "/zoeknummerform.html")
            
            with open(filename, 'r') as f:
                company_numbers = [line.strip() for line in f.readlines()]
            
            logger.info(f"Found {len(company_numbers)} numbers to search")
            
            results = []
            for number in company_numbers:
                try:
                    await page.wait_for_selector('#nummer')
                    await page.fill('#nummer', number)
                    await page.click('#actionLu')
                    await page.wait_for_load_state('networkidle')
                    
                    # Scraping coming here
                    
                    logger.info(f"Successfully searched number: {number}")

                    await page.wait_for_timeout(3000)
                    
                    await page.goto(self.kbo_base_url + "/zoeknummerform.html")
                    
                except Exception as e:
                    logger.error(f"Error searching number {number}: {str(e)}")
                    continue
                
            return results
            
        finally:
            await browser.close()
            await playwright.stop()
    

    async def scrape_all(self):
        """Main scraping process"""

        company_numbers = await self.scrape_opencorporates()
        logger.info(f"Found {len(company_numbers)} company numbers")

        filename = f"company_numbers.txt"
        
        with open(filename, 'w') as f:
            for number in company_numbers:
                f.write(f"{number}\n")
        
        logger.info(f"Saved company numbers to {filename}")
        
        logger.info("Starting KBO searches...")
        await self.search_kbo_numbers(filename)

async def main():
    scraper = BelgianCompanyScraper()
    await scraper.scrape_all()

if __name__ == "__main__":
    asyncio.run(main())