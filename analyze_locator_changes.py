#!/usr/bin/env python3
"""
Identify and analyze false positive locator changes.

False positives are changes where the actual selector stays the same,
but method chains, assertions, or parameters change.

Examples:
- cy.get('#id') → cy.get('#id').within() [added method chain]
- cy.get('#id').first() → cy.get('#id') [removed method]
- cy.get('#id').contains('text1') → cy.get('#id').contains('text2') [assertion change]
"""

import sqlite3
import re
import pandas as pd

DB_PATH = "data/locator_break.db"

def strip_assertions(locator_str):
    """
    Remove assertion-only parts from a locator string.
    
    Keeps the locator traversal chain but removes/normalizes:
    - .should(...) assertions
    - .contains(...) with JUST text (but keeps .contains('selector', 'text') as it's part of locator)
    - .click(), .type(), etc. (actions, not locators)
    
    But KEEPS:
    - .get(), .locator() - base selectors
    - .find(), .closest(), .parent(), .children() - traversal
    - .contains('selector', 'text') - when there are 2 args, first is selector
    - .within() - scoping
    - .first(), .last() - filtering
    - .eq() - indexing
    
    Examples:
        'cy.get("#id").should("be.visible")' → 'cy.get("#id")'
        'cy.get("#id").first().should("exist")' → 'cy.get("#id").first()'
        'cy.get("#id").parent(".unread").should("be.visible")' → 'cy.get("#id").parent(".unread")'
        'cy.get("#id").contains("text1").click()' → 'cy.get("#id")'  # single arg, just assertion
        'cy.get("#id").contains(".class", "text").should()' → 'cy.get("#id").contains(".class")' # 2 args, first is selector
    """
    # Remove .should(...) completely
    s = re.sub(r'\.should\s*\([^)]*\)', '', locator_str)
    
    # Remove .click(), .type(), .clear(), etc. (action methods)
    s = re.sub(r'\.(click|type|clear|hover|focus|blur|check|uncheck|select|trigger|submit)\s*\(\s*[^)]*\s*\)', '', s)
    
    # For .contains(), need to be careful:
    # .contains('selector', 'text') - keep the selector, remove the text
    # .contains('text') - remove entire method
    # Try to extract and preserve selector argument if present
    
    # First, try to find .contains with two string arguments where first looks like a selector
    # Pattern: .contains('selector', 'text') or .contains("selector", "text")
    def replace_contains(match):
        full_match = match.group(0)
        # Check if this looks like it has a selector (first arg contains . # [ or :)
        # vs just plain text
        content = match.group(1)
        
        # Split by comma, but be careful with nested quotes/parens
        # Simple heuristic: if there's a comma and first part looks like CSS selector
        if ',' in content:
            parts = [p.strip() for p in content.split(',', 1)]
            selector_candidate = parts[0]
            # Remove quotes
            selector_candidate = re.sub(r'^["\']|["\']$', '', selector_candidate)
            # If it looks like a selector (has . # [ or : or is valid CSS-like)
            if any(c in selector_candidate for c in ['.', '#', '[', ':']):
                return f'.contains({selector_candidate})'
        
        # Single argument or can't determine - just remove it
        return ''
    
    s = re.sub(r'\.contains\s*\(([^)]+)\)', replace_contains, s)
    
    # Clean up trailing dots and spaces
    s = re.sub(r'\.\s+', '.', s)
    s = s.rstrip('.')
    
    return s


def extract_locator_chain(locator_str):
    """
    Extract the full locator chain (traversal path) without assertions.
    
    Examples:
        'cy.get("#id").parent(".unread").should("be.visible")' 
            → 'cy.get("#id").parent(".unread")'
        
        'cy.get("#id").children(".unread").should("be.visible")'
            → 'cy.get("#id").children(".unread")'
        
        'cy.get("#renderCount").contains("34")' 
            → 'cy.get("#renderCount")'
    """
    return strip_assertions(locator_str)


def categorize_change(old_locator, new_locator):
    """
    Categorize a locator change based on structural DOM navigation changes.
    
    Returns:
        'structural_break': Locator traversal/selectors changed (REAL BREAK)
        'assertion_change': Same locator chain, only assertion changed
        'unclear': Could not determine
    
    Focuses on STRUCTURAL CHANGES per the paper's definition.
    """
    
    old_chain = extract_locator_chain(old_locator)
    new_chain = extract_locator_chain(new_locator)
    
    # If we couldn't extract chains, it's unclear
    if not old_chain or not new_chain:
        return 'unclear'
    
    # If chains are identical, it's just an assertion change
    if old_chain == new_chain:
        return 'assertion_change'
    
    # Different chains = structural change (real break)
    return 'structural_break'


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    # Get all locator changes with repository info
    query = """
        SELECT id, old_locator, new_locator, repository_name
        FROM locator_change
        ORDER BY id
    """
    df = pd.read_sql_query(query, con)
    con.close()
    
    print(f"🔍 Analyzing {len(df):,} locator changes...\n")
    
    # Categorize each change
    categories = {
        'structural_break': [],
        'assertion_change': [],
        'unclear': []
    }
    
    results = []
    
    for idx, row in df.iterrows():
        old_locator = row['old_locator']
        new_locator = row['new_locator']
        
        category = categorize_change(old_locator, new_locator)
        
        change_data = {
            'id': row['id'],
            'repository': row['repository_name'],
            'old_locator': old_locator,
            'new_locator': new_locator,
            'category': category
        }
        
        categories[category].append(change_data)
        results.append(change_data)
    
    # Print summary
    print("\n" + "="*80)
    print("LOCATOR CHANGE CATEGORIZATION SUMMARY (Structural Changes Focus)")
    print("="*80)
    print(f"\nTotal Changes: {len(df):,}")
    print(f"\n✓ Structural Breaks (Real DOM changes):     {len(categories['structural_break']):6,} ({len(categories['structural_break'])/len(df)*100:5.2f}%)")
    print(f"✗ Assertion Changes (Same locator):         {len(categories['assertion_change']):6,} ({len(categories['assertion_change'])/len(df)*100:5.2f}%)")
    print(f"? Unclear:                                   {len(categories['unclear']):6,} ({len(categories['unclear'])/len(df)*100:5.2f}%)")
    print("\n" + "="*80)
    
    # Export to CSV for analysis
    results_df = pd.DataFrame(results)
    results_df.to_csv('locator_analysis.csv', index=False)
    print(f"\n✓ Exported detailed analysis to: locator_analysis.csv")
    
    # Show examples of each category
    print("\n" + "="*80)
    print("EXAMPLES FROM EACH CATEGORY")
    print("="*80)
    
    for category_name in ['structural_break', 'assertion_change', 'unclear']:
        examples = [item for item in categories[category_name][:10]]
        if len(examples) > 0:
            print(f"\n--- {category_name.upper()} (showing {min(10, len(examples))} of {len(categories[category_name])}) ---")
            for item in examples:
                print(f"\nID: {item['id']}")
                if item['repository']:
                    print(f"  Repo: {item['repository']}")
                print(f"  OLD: {item['old_locator']}")
                print(f"  NEW: {item['new_locator']}")


if __name__ == "__main__":
    main()
