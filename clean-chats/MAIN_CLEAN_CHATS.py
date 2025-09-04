# The Snowpark package is required for Python Worksheets. 
# You can add more packages by selecting them using the Packages control and then importing them.

import snowflake.snowpark as snowpark
from snowflake.snowpark.functions import col
from clean_chats_integration import (
    main_clean_chats_analysis,
    main_clean_chats_test,
    main_clean_chats_report,
    run_single_department_clean_chats
)

def main(session: snowpark.Session):
    """
    Main Clean Chats Analysis Function
    
    This function runs the complete clean chats analysis pipeline:
    1. Uses same filtering methods as LLM_JUDGE
    2. Checks each conversation against flagging criteria
    3. Identifies "clean" conversations (no issues flagged)
    4. Saves results to database tables
    
    Clean Chat Definition:
    - Conversation passed through all department prompts
    - NOT flagged by SA_prompt (NPS score != 1)  
    - NOT flagged by specialized prompts (LLM response doesn't contain "YES")
    """
    
    # Option 1: Run complete analysis for all departments
    result = main_clean_chats_analysis(session, '2025-08-04')
    
    # Option 2: Run for single department
    result = run_single_department_clean_chats(session, 'MV_Resolvers', '2025-08-04')
    
    # Option 3: Test setup
    # result = main_clean_chats_test(session, 'CC_Resolvers')
    
    # Option 4: Generate report
    # result = main_clean_chats_report(session, '2025-08-04')
    
    if result.get('success', True):
        return f"✅ Clean Chats Analysis Complete!\n{result.get('summary', 'Analysis completed successfully.')}"
    else:
        return f"❌ Clean Chats Analysis Failed: {result.get('error', 'Unknown error')}"
