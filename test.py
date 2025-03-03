import asyncio
import json
import logging
from typing import List, Dict, Any
import pandas as pd
from playwright.async_api import async_playwright, Browser, Page
from datetime import datetime
import re
import unicodedata

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
                # 1 page for testing
                if i >= 5:
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

                    is_active = await page.is_visible('.pageactief')
                    if not is_active:
                        logger.info(f"Company {number} is not active, skipping...")
                        await page.wait_for_timeout(3000)
                        await page.goto(self.kbo_base_url + "/zoeknummerform.html")
                        continue

                    # Get company name when active
                    company_name = ""
                    company_name_element = await page.query_selector('//tr[7]/td[2]')
                    if company_name_element:
                        company_name = await company_name_element.evaluate('node => node.firstChild.textContent')
                        if company_name:
                            company_name = company_name.strip('" ')  

                                        # Try to get email
                    email = ""
                    try:
                        email_element = await page.query_selector("//tr[12]/td[2]/table//a")
                        if email_element:
                            email_text = await email_element.text_content()
                            if '@' in email_text:
                                email = email_text.strip()
                    except Exception as e:
                        logger.debug(f"No email found for company {number}")

                    function_load = await page.is_visible('#klikfctie a')
                    if function_load:
                        print("FUNCTIONS LOADING")
                        await page.click('#klikfctie a')
                        await page.wait_for_load_state('networkidle')
                        await page.wait_for_timeout(1000)

                        await page.wait_for_selector('#toonfctie')

                        function_rows = await page.query_selector_all('#toonfctie tr')
                        for row in function_rows:
                            cells = await row.query_selector_all('td')
                            if len(cells) >= 2:
                                function_title = await cells[0].text_content()
                                function_name = await cells[1].text_content()
                                logger.info(f"Found function: {function_title.strip()} - {function_name.strip()}")
                                results.append({
                                    'company_number': number,
                                    'company_name': company_name,
                                    'email': email,
                                    'function_title': function_title.strip(),
                                    'function_name': function_name.strip()
                                })
                    else:
                        function_rows = await page.query_selector_all('tr:has(td:nth-child(3))')
                        if len(function_rows) > 0:
                            print("FUNCTIONS DETECTED!!!")
                            for row in function_rows:
                                cells = await row.query_selector_all('td')
                                if len(cells) == 3:
                                    function_title = await cells[0].text_content()
                                    second_cell_class = await cells[1].get_attribute('class')
                                    if second_cell_class in ['QL', 'RL']:
                                        function_name = await cells[1].text_content()
                                        print(f"Found function: {function_title.strip()} - {function_name.strip()}")
                                        results.append({
                                            'company_number': number,
                                            'company_name': company_name,
                                            'email': email,
                                            'function_title': function_title.strip(),
                                            'function_name': function_name.strip()
                                        })
                        else:
                            logger.info(f"Company {number} has no functions visible, skipping...")
                            await page.wait_for_timeout(3000)
                            await page.goto(self.kbo_base_url + "/zoeknummerform.html")
                            continue

                    print(results)
                    logger.info(f"Successfully searched number: {number}")
                    await page.wait_for_timeout(3000)
                    await page.goto(self.kbo_base_url + "/zoeknummerform.html")
                    
                except Exception as e:
                    logger.error(f"Error searching number {number}: {str(e)}")
                    continue

            if len(results) > 0:
                df = pd.DataFrame(results)
                
                df['function_title'] = df['function_title'].apply(lambda x: unicodedata.normalize('NFKD', x.strip()).encode('ASCII', 'ignore').decode())
                
                def process_name(text):
                    text = text.strip()
                    first_name = ""
                    last_name = ""
                    company_number = ""
                    
                    if all(c.isdigit() or c in '().,' for c in text.replace(' ', '')):
                        company_number = text.strip('() ')
                    else:
                        if '(' in text and ')' in text:
                            company_number = text[text.find('(')+1:text.find(')')].strip()
                            text = text.split('(')[0].strip()
                        
                        if text:
                            parts = text.split(',', 1)
                            if len(parts) > 1:
                                last_name = parts[0].strip()
                                first_name = parts[1].strip()
                            else:
                                parts = text.strip().split()
                                last_name = parts[0] if parts else ""
                                first_name = ' '.join(parts[1:]) if len(parts) > 1 else ""
                    
                    return pd.Series([first_name, last_name, company_number])
                
                df[['first_name', 'last_name', 'person_company_number']] = df['function_name'].apply(process_name)
                
                df = df.drop('function_name', axis=1)
                
                df = df[['company_number', 'company_name', 'email', 'function_title', 'first_name', 'last_name', 'person_company_number']]
                
                excel_filename = f"company_functions.xlsx"
                
                df.to_excel(excel_filename, index=False)
                logger.info(f"Results saved to {excel_filename}")
            else:
                logger.info("No results to save")
            
        finally:
            await browser.close()
            await playwright.stop()
    

    async def scrape_all(self):
        """Main scraping process"""

        # company_numbers = await self.scrape_opencorporates()
        # logger.info(f"Found {len(company_numbers)} company numbers")

        filename = f"company_numbers.txt"
        
        # with open(filename, 'w') as f:
        #     for number in company_numbers:
        #         f.write(f"{number}\n")
        
        # logger.info(f"Saved company numbers to {filename}")
        
        logger.info("Starting KBO searches...")
        await self.search_kbo_numbers(filename)

async def main():
    scraper = BelgianCompanyScraper()
    await scraper.scrape_all()

if __name__ == "__main__":
    asyncio.run(main())