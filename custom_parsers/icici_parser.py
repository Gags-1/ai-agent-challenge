
import pandas as pd
import PyPDF2
import re
import numpy as np

def parse(pdf_path):
    """
    Parses a 2-page PDF bank statement and returns a pandas DataFrame.

    Args:
        pdf_path (str): The file path to the PDF.

    Returns:
        pd.DataFrame: A DataFrame containing the transaction data with columns
                      ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'].
    """
    
    full_text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text
    except FileNotFoundError:
        return pd.DataFrame(columns=['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'])

    # Regex to capture transaction lines
    # Captures: Date, Description (non-greedy), Amount, Balance
    transaction_pattern = re.compile(
        r"^(\d{2}-\d{2}-\d{4})\s+(.*?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$", 
        re.MULTILINE
    )

    matches = transaction_pattern.findall(full_text)

    transactions = []
    for match in matches:
        date_str, description, amount_str, balance_str = match
        
        description = description.strip()
        amount = float(amount_str.replace(',', ''))
        balance = float(balance_str.replace(',', ''))

        # Heuristic to determine Debit vs. Credit based on keywords
        credit_keywords = ['credit', 'deposit']
        
        is_credit = any(keyword in description.lower() for keyword in credit_keywords)

        if is_credit:
            debit_amt = np.nan
            credit_amt = amount
        else:
            debit_amt = amount
            credit_amt = np.nan
            
        transactions.append({
            'Date': date_str,
            'Description': description,
            'Debit Amt': debit_amt,
            'Credit Amt': credit_amt,
            'Balance': balance
        })

    if not transactions:
        return pd.DataFrame(columns=['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'])

    df = pd.DataFrame(transactions)

    final_columns = ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance']
    df = df[final_columns]

    return df
