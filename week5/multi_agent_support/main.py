"""
Demo script for the Multi-Agent Support System

This script demonstrates how to use the multi-agent system with example queries.
"""

from multi_agent_system import run_query

def main():
    print("=" * 70)
    print("Multi-Agent Support System - Demo")
    print("=" * 70)
    
    it_queries = [
        "How to set up VPN?",
        "What software is approved for use?",
        "How to request a new laptop?",
    ]
    
    print("\n" + "=" * 70)
    print("IT Agent Queries")
    print("=" * 70)
    
    for i, query in enumerate(it_queries, 1):
        print(f"\n[{i}] Query: {query}")
        print("-" * 70)
        try:
            response = run_query(query)
            print(f"Response:\n{response}")
        except Exception as e:
            print(f"Error: {e}")
        print("=" * 70)
    
    # Example Finance queries
    finance_queries = [
        "How to file a reimbursement?",
        "Where to find last month's budget report?",
        "When is payroll processed?",
    ]
    
    print("\n" + "=" * 70)
    print("Finance Agent Queries")
    print("=" * 70)
    
    for i, query in enumerate(finance_queries, 1):
        print(f"\n[{i}] Query: {query}")
        print("-" * 70)
        try:
            response = run_query(query)
            print(f"Response:\n{response}")
        except Exception as e:
            print(f"Error: {e}")
        print("=" * 70)

if __name__ == "__main__":
    main()
