import os
import pandas as pd
import importlib.util
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
import argparse
import PyPDF2
from dotenv import load_dotenv

load_dotenv()

class AgentState(BaseModel):
    target_bank: str = Field(...)
    pdf_path: str = Field(...)
    csv_path: str = Field(...)
    code: str = Field(default="")
    error: str = Field(default="")
    attempts: int = Field(default=0)
    next_node: str = Field(default="")

def generate_code(state):
    print(f"Attempt {state.attempts + 1} to generate parser...")
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables")
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.1, google_api_key=api_key)
    
    with open(state.pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        num_pages = len(reader.pages)
        pdf_text = reader.pages[0].extract_text()[:1000]
    
    expected_df = pd.read_csv(state.csv_path)
    columns = list(expected_df.columns)
    
    error_info = f" Previous error: {state.error}" if state.error else ""
    
    prompt = f"""
    Create a Python function parse(pdf_path) that returns a pandas DataFrame.
    
    The PDF has {num_pages} pages. Read through the entire length of the PDF.
    
    CSV path: {state.csv_path}
    PDF path: {state.pdf_path}
    
    Columns: {columns}
    
    PDF content preview:
    {pdf_text}
    
    Use only PyPDF2. Function: parse(pdf_path) -> pd.DataFrame
    Return only the Python code without any explanations.
    Read all 100 rows of the pdf.
    {error_info}
    """
    
    response = llm.invoke(prompt)
    state.code = response.content.strip()
    state.attempts += 1
    
    if state.code.startswith("```python"):
        state.code = state.code[9:]
    if state.code.endswith("```"):
        state.code = state.code[:-3]
    
    state.next_node = "save_code"
    return state

def save_code(state):
    os.makedirs("custom_parsers", exist_ok=True)
    parser_path = f"custom_parsers/{state.target_bank}_parser.py"
    
    with open(parser_path, "w") as f:
        f.write(state.code)
    
    state.next_node = "test_code"
    return state

def test_code(state):
    try:
        parser_path = f"custom_parsers/{state.target_bank}_parser.py"
        
        spec = importlib.util.spec_from_file_location("parser", parser_path)
        parser = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parser)
        
        result_df = parser.parse(state.pdf_path)
        expected_df = pd.read_csv(state.csv_path)
        
        if result_df.equals(expected_df):
            print("Success! Parser works perfectly!")
            state.next_node = END
        else:
            print("Output doesn't match CSV")
            state.error = "Output doesn't match CSV"
            state.next_node = "generate_code"
            
    except Exception as e:
        print(f"Error: {str(e)}")
        state.error = str(e)
        state.next_node = "generate_code"
    
    return state

def route_state(state):
    if state.attempts >= 3:
        print("Failed after 3 attempts")
        return END
    return state.next_node

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    
    target_bank = args.target.lower()
    pdf_path = f"data/{target_bank}/{target_bank} sample.pdf"
    csv_path = f"data/{target_bank}/result.csv"
    
    print(f"Target: {target_bank}")
    print(f"PDF path: {pdf_path}")
    
    workflow = StateGraph(AgentState)
    workflow.add_node("generate_code", generate_code)
    workflow.add_node("save_code", save_code)
    workflow.add_node("test_code", test_code)
    
    workflow.set_entry_point("generate_code")
    workflow.add_conditional_edges("generate_code", route_state)
    workflow.add_conditional_edges("save_code", route_state)
    workflow.add_conditional_edges("test_code", route_state)
    
    compiled = workflow.compile()
    
    initial_state = AgentState(
        target_bank=target_bank,
        pdf_path=pdf_path,
        csv_path=csv_path,
        next_node="save_code"
    )
    
    compiled.invoke(initial_state)

if __name__ == "__main__":
    main()