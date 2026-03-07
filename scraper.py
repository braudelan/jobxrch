from playwright.sync_api import sync_playwright
import pandas as pd
import time
import random # NEW: Added for jitter delays

def extract_metadata_from_card(card):
    try:
        link_elements = card.locator('a[href*="/jobs/view/"]').all()
        link = link_elements[0].get_attribute("href") if link_elements else "N/A"
        link = link.split('?')[0] if link != "N/A" else link 
        
        text_content = card.inner_text().strip().split('\n')
        text_lines = [line.strip() for line in text_content if line.strip()]
        
        # CHANGED: Expanded noise list to prevent column shifting
        noise_words = [
            ", Verified", "Verified", "Promoted", 
            "Actively recruiting", "Applied", "Be an early applicant"
        ]
        clean_lines = [line for line in text_lines if line not in noise_words]
        
        title = clean_lines[0] if len(clean_lines) > 0 else "N/A"
        company = clean_lines[1] if len(clean_lines) > 1 else "N/A"
        location = clean_lines[2] if len(clean_lines) > 2 else "N/A"
        
        return {
            "Job Title": title, 
            "Company": company, 
            "Location": location,
            "Link": link
        }

    except Exception as e:
        print(f"Error extracting data from card: {e}")
        return None
    
def export_saved_jobs(li_at_cookie):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context()
        
        context.add_cookies([{
            "name": "li_at",
            "value": li_at_cookie,
            "domain": ".linkedin.com",
            "path": "/"
        }])
        
        page = context.new_page()
        print("Navigating to Saved Jobs...")
        page.goto("https://www.linkedin.com/my-items/saved-jobs/")
        
        jobs_data = []
        page_num = 1 # NEW: Track pages

        # Handle pagination
        while True:
            print(f"--- Processing Page {page_num} ---")
            card_selector = 'div[data-view-name="search-entity-result-universal-template"]'
            
            try:
                # Wait for cards to load on the new page
                page.wait_for_selector(card_selector, timeout=10000)
            except Exception:
                print("No more job cards found or list ended.")
                break
            
            # Scrape current page
            job_cards = page.locator(card_selector).all()
            for card in job_cards:
                job_data = extract_metadata_from_card(card)
                if job_data:
                    jobs_data.append(job_data)

            # Targeting the 'Next' button specifically
            next_button = page.locator('button[aria-label*="Next"]').first
            
            if next_button.is_visible() and next_button.is_enabled():
                print(f"Page {page_num} done. Clicking Next...")
                next_button.click()
                page_num += 1
                # Small human-like delay for the next page to load
                time.sleep(random.uniform(3, 6))
            else:
                print("Reached the end of the saved jobs list.")
                break


        browser.close()
        
        df = pd.DataFrame(jobs_data)
        df.to_csv("linkedin_saved_jobs.csv", index=False)
        print(f"Successfully exported {len(df)} jobs from {page_num} pages.")

if __name__ == "__main__":
    YOUR_COOKIE = "AQEDAQxRbL4AoPL7AAABnK3CNbEAAAGc0c65sU0AtsV2C3dB8HBAXIMy7DJoCcTQ3p4ZhnI2aTS4Wzrrq0-okNI-cWalHGOeRYgtIhUFqyKmVqvzgf7erSXFRYhABwYAv0gDPvE4ZYAHSqeAl4OoN-So"
    export_saved_jobs(YOUR_COOKIE)