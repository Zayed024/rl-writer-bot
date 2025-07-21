from playwright.async_api import async_playwright
import re
import os
import asyncio
import config
# BASE_URL = "https://en.wikisource.org/wiki/"

logger = config.logger
def book_chapter_info(url:str):
   
    pattern = r"\/([^\/]+)\/Book_(\d+)\/Chapter_(\d+)"
    match = re.search(pattern, url)
    if match:
        # Replacing underscores with spaces and decode URL components 
        book_name_slug = match.group(1)
        book_num = int(match.group(2))
        chap_num = int(match.group(3))
        return book_name_slug, book_num, chap_num
    else:
        print(f"Warning: Could not extract book/chapter info from URL: {url}. Using defaults.")
        return "Unknown Book", 0, 0 
    
def construct_wikisource_url(book_name_slug: str, book_num: int, chap_num: int) -> str:
    """
    Constructs a Wikisource URL for a specific book and chapter.
    Example: 'The_Gates_of_Morning', 1, 1 -> 'https://en.wikisource.org/wiki/The_Gates_of_Morning/Book_1/Chapter_1'
    """
    return f"{config.BASE_URL}{book_name_slug}/Book_{book_num}/Chapter_{chap_num}"    

async def scrape_content(book_name_slug: str, book_num: int, chap_num: int):
    """
    Scrapes content from the constructed Wikisource URL.
    Saves content to a uniquely named text file.
    Returns (scraped_text, metadata_title, screenshot_path, is_valid_chapter).
    is_valid_chapter is True if content was found, False otherwise.
    """
    url = construct_wikisource_url(book_name_slug, book_num, chap_num)
    output_filepath = f"scraped_content_{book_name_slug}_Book{book_num}_Chapter{chap_num}.txt"
    screenshot_path = f"screenshot_{book_name_slug}_Book{book_num}_Chapter{chap_num}.png"

    scraped_text = ""
    metadata_title = ""
    is_valid_chapter = False

    logger.info(f"Attempting to scrape URL: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) # Keep headless=True for background operation
        page =await browser.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000) # Added timeout
            await page.wait_for_load_state('networkidle', timeout=30000)

            # Check for "Page not found" indicator in title 
            page_title_element = page.locator('h1#firstHeading span.mw-page-title-main')
            if not await page_title_element.is_visible():
                logger.warning(f"  [Scraper] Warning: Page title element not found on {url}. Likely invalid page.")
                is_valid_chapter = False
            else:
                metadata_title =await page_title_element.text_content()
                if "Page not found" in metadata_title or "No such page" in metadata_title:
                    logger.info(f"  [Scraper] Page title indicates invalid chapter: '{metadata_title}'")
                    is_valid_chapter = False
                else:
                    # Attempt to scrape paragraphs
                    paragraph_elements =await page.locator('.prp-pages-output p').all()
                    if not paragraph_elements:
                        logger.info(f"  [Scraper] No content paragraphs found on {url}. Possibly invalid chapter or different structure.")
                        is_valid_chapter = False
                    else:
                        
                        paragraph_texts = []
                        for p in paragraph_elements:
                            text_content =await p.text_content()
                            text=text_content.strip()
                        # Check if the text content looks like CSS rules
                            if not text.startswith('.mw-parser-output'):
                                paragraph_texts.append(text)
                        scraped_text = "\n\n".join(paragraph_texts)        
                        if scraped_text.strip(): # Check if actual content was scraped
                            is_valid_chapter = True
                            # Save content to a unique file
                            with open(output_filepath, 'w', encoding='utf-8') as f:
                                f.write(scraped_text)
                            logger.info(f"  [Scraper] Content successfully scraped and saved to {output_filepath}")
                            
                            # Take screenshot only if chapter is valid and content is found
                            await page.screenshot(path=screenshot_path, full_page=True)
                            logger.info(f"  [Scraper] Screenshot saved to {screenshot_path}")
                        else:
                            logger.info(f"  [Scraper] Scraped paragraphs were empty after stripping. Invalid content.")
                            is_valid_chapter = False

        except Exception as e:
            logger.error(f"  [Scraper] Error during scraping {url}: {e}", exc_info=True)
            is_valid_chapter = False # Mark as invalid on error
        finally:
            await browser.close()
    
    return scraped_text, metadata_title, screenshot_path, is_valid_chapter


#Example usage (for testing scrape.py independently)

async def main_scrape_test(): # Define an async test function
    test_book_name_slug = "The_Gates_of_Morning"

    print("\n Testing Valid Chapter (Book 1, Chapter 1) ")
    scraped_text_1_1, title_1_1, screenshot_1_1, is_valid_1_1 = await scrape_content(test_book_name_slug, 1, 1) # ADD 'await'
    print(f"Is Book 1, Chapter 1 Valid? {is_valid_1_1}")
    if is_valid_1_1:
        print(f"Content snippet: {scraped_text_1_1[:200]}...")

    print("\n Testing Invalid Chapter (Book 1, Chapter 99) ")
    scraped_text_1_99, title_1_99, screenshot_1_99, is_valid_1_99 = await scrape_content(test_book_name_slug, 1, 99) # ADD 'await'
    print(f"Is Book 1, Chapter 99 Valid? {is_valid_1_99}")
    if not is_valid_1_99:
        print("  Expected: Invalid chapter detected.")

    print("\n Testing Invalid Book (Book 99, Chapter 1)")
    scraped_text_99_1, title_99_1, screenshot_99_1, is_valid_99_1 = await scrape_content("NonExistent_Book", 99, 1) # ADD 'await'
    print(f"Is NonExistent_Book 99, Chapter 1 Valid? {is_valid_99_1}")
    if not is_valid_99_1:
        print("  Expected: Invalid book detected.")

    # Clean up test files
    for fn in [
        f"scraped_content_{test_book_name_slug}_Book1_Chapter1.txt",
        f"screenshot_{test_book_name_slug}_Book1_Chapter1.png",
        f"scraped_content_{test_book_name_slug}_Book1_Chapter99.txt",
        f"screenshot_{test_book_name_slug}_Book1_Chapter99.png",
        f"scraped_content_NonExistent_Book_Book99_Chapter1.txt",
        f"screenshot_NonExistent_Book_Book99_Chapter1.png"
    ]:
        if os.path.exists(fn):
            os.remove(fn)

if __name__ == "__main__":
    asyncio.run(main_scrape_test())