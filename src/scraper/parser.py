# src/scraper/parser.py
"""
Parses raw text from LinkedIn job cards into structured data. Cleans noise like "Promoted" badges and extracts job title, company, location, and link. 
Designed to handle variations in card formats and ensure consistent output for downstream processing.
"""

def clean_job_card_data(raw_text, raw_link):
    """
    Takes raw text from a LinkedIn card and cleans it into a dict.
    """
    # Split and strip lines
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    
    # Noise filter - add any new badges here
    noise = {
        ", Verified", "Verified", "Promoted", 
        "Actively recruiting", "Applied", "Be an early applicant"
    }
    
    # Filter lines
    clean = [l for l in lines if l not in noise]
    
    return {
        "job_title": clean[0] if len(clean) > 0 else "N/A",
        "company": clean[1] if len(clean) > 1 else "N/A",
        "location": clean[2] if len(clean) > 2 else "N/A",
        "link": raw_link.split('?')[0] if raw_link else "N/A"
    }